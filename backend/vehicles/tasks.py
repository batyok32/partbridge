"""Celery tasks for vehicles."""
from __future__ import annotations

import logging
import threading

from celery import shared_task
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

# Global semaphore: at most 50 listing-pipeline tasks run concurrently in this worker process.
_PIPELINE_SEMAPHORE = threading.Semaphore(50)


@shared_task
def expire_buy_now_listings() -> dict:
    """Revert expired Buy Now listings to draft."""
    close_old_connections()
    from vehicles.models import VehiclePart

    now = timezone.now()
    n = VehiclePart.objects.filter(
        listing_state=VehiclePart.ListingState.BUY_NOW,
        buy_now_expires_at__isnull=False,
        buy_now_expires_at__lt=now,
    ).update(
        listing_state=VehiclePart.ListingState.DRAFT,
        buy_now_expires_at=None,
        updated_at=now,
    )
    if n:
        logger.info("expire_buy_now_listings: reverted %s rows", n)
    return {"expired": n}


@shared_task
def analyze_vehicle_images(vehicle_id: int) -> dict:
    """
    Send all uploaded vehicle photos to Claude for a full damage/condition description.
    Saves result to Vehicle.ai_image_description.
    """
    close_old_connections()
    from vehicles.models import Vehicle
    from vehicles.part_ai_service import describe_vehicle_from_images

    try:
        vehicle = Vehicle.objects.select_related("owner").prefetch_related("photos").get(pk=vehicle_id)
    except Vehicle.DoesNotExist:
        return {"error": "vehicle not found"}

    image_urls = []
    for ph in vehicle.photos.order_by("sort_order", "id")[:12]:
        if ph.image:
            try:
                image_urls.append(ph.image.url)
            except Exception:
                pass

    if not image_urls:
        return {"skipped": "no images"}

    vehicle_info = {
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
        "trim": vehicle.trim,
        "engine": vehicle.engine,
        "color": vehicle.color,
    }
    description = describe_vehicle_from_images(image_urls, vehicle_info)
    if description:
        Vehicle.objects.filter(pk=vehicle_id).update(
            ai_image_description=description,
            updated_at=timezone.now(),
        )
    return {"vehicle_id": vehicle_id, "description_length": len(description)}


@shared_task
def run_part_listing_pipeline(vehicle_part_id: int) -> dict:
    """
    Full async pipeline for a newly listed part:
    1. AI image analysis (if not already done on vehicle)
    2. car-part.com option scraping
    3. AI option selection
    4. Package size estimation
    5. Perplexity compatibility lookup (per option)
    6. Grade assignment

    Respects global semaphore of 50 concurrent tasks.
    """
    close_old_connections()

    acquired = _PIPELINE_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        logger.warning("run_part_listing_pipeline: semaphore full, re-queuing part_id=%s", vehicle_part_id)
        run_part_listing_pipeline.apply_async(args=[vehicle_part_id], countdown=30)
        return {"status": "requeued"}

    try:
        return _run_pipeline(vehicle_part_id)
    finally:
        _PIPELINE_SEMAPHORE.release()


def _run_pipeline(vehicle_part_id: int) -> dict:
    from vehicles.models import (
        PartCompatibility,
        PartOption,
        PartOptionSet,
        VehiclePart,
        primary_section_for_part_label,
    )
    from vehicles.car_part_scraper import scrape_part_options
    from vehicles.part_ai_service import (
        describe_vehicle_from_images,
        estimate_part_size,
        get_option_compatibility,
        grade_part,
        headlight_type_from_google,
        select_part_options,
    )

    try:
        part = VehiclePart.objects.select_related(
            "vehicle", "part_family", "part_family__category"
        ).get(pk=vehicle_part_id)
    except VehiclePart.DoesNotExist:
        return {"error": "part not found"}

    # Mark as processing
    VehiclePart.objects.filter(pk=vehicle_part_id).update(
        listing_pipeline_status="processing",
        listing_pipeline_started_at=timezone.now(),
        listing_pipeline_error="",
        updated_at=timezone.now(),
    )

    vehicle = part.vehicle
    vehicle_info = {
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
        "trim": vehicle.trim,
        "engine": vehicle.engine,
        "transmission": vehicle.transmission,
        "color": vehicle.color,
    }

    try:
        # ------------------------------------------------------------------
        # Step 1: AI image description (re-use vehicle's if already done)
        # ------------------------------------------------------------------
        ai_description = vehicle.ai_image_description or ""
        if not ai_description:
            image_urls = []
            for ph in vehicle.photos.order_by("sort_order", "id")[:12]:
                if ph.image:
                    try:
                        image_urls.append(ph.image.url)
                    except Exception:
                        pass
            if image_urls:
                ai_description = describe_vehicle_from_images(image_urls, vehicle_info)
                if ai_description:
                    from vehicles.models import Vehicle
                    Vehicle.objects.filter(pk=vehicle.pk).update(
                        ai_image_description=ai_description,
                        updated_at=timezone.now(),
                    )

        # ------------------------------------------------------------------
        # Step 2: Grade the part
        # ------------------------------------------------------------------
        mileage = vehicle.odometer_miles if not vehicle.mileage_unavailable else None
        grade = grade_part(
            mileage=mileage,
            ai_description=ai_description,
            part_name=part.label,
        )

        # ------------------------------------------------------------------
        # Step 3: Estimate package size
        # ------------------------------------------------------------------
        size_info = estimate_part_size(part.label, vehicle_info)

        # ------------------------------------------------------------------
        # Step 4: Assign primary photo section
        # ------------------------------------------------------------------
        primary_section = primary_section_for_part_label(part.label)

        # ------------------------------------------------------------------
        # Step 5: car-part.com options
        # ------------------------------------------------------------------
        zip_code = vehicle.location_zip or "90210"
        option_set, _ = PartOptionSet.objects.get_or_create(
            vehicle=vehicle,
            part_family=part.part_family,
            defaults={"status": PartOptionSet.Status.PENDING},
        )

        scrape_result = scrape_part_options(
            year=vehicle.year or 2000,
            make=vehicle.make or "",
            model=vehicle.model or "",
            part_name=part.part_family.name,
            zip_code=zip_code,
        )
        carpart_status = scrape_result["status"]
        raw_options = scrape_result.get("options") or []

        # Map scrape status to PartOptionSet.Status
        status_map = {
            "found": PartOptionSet.Status.FOUND,
            "no_options": PartOptionSet.Status.NO_OPTIONS,
            "year_range": PartOptionSet.Status.YEAR_RANGE,
            "undefined": PartOptionSet.Status.UNDEFINED,
            "failed": PartOptionSet.Status.FAILED,
        }
        option_set.status = status_map.get(carpart_status, PartOptionSet.Status.FAILED)
        option_set.raw_options = raw_options
        option_set.processed_at = timezone.now()
        option_set.save(update_fields=["status", "raw_options", "processed_at"])

        # ------------------------------------------------------------------
        # Step 6: AI option selection
        # ------------------------------------------------------------------
        final_options = []

        if carpart_status == "no_options":
            # Single "All" option — just save compatibility
            opt, _ = PartOption.objects.update_or_create(
                option_set=option_set,
                option_key="all",
                defaults={
                    "option_label": "All",
                    "confidence": 1.0,
                    "needs_manual_check": False,
                    "is_applicable": True,
                    "source": "all",
                },
            )
            final_options.append(opt)

        elif carpart_status in ("year_range", "undefined"):
            # Use Perplexity to discover options if available
            perp_result = get_option_compatibility(
                vehicle_info=vehicle_info,
                part_name=part.label,
                option_label="standard",
            )
            opt, _ = PartOption.objects.update_or_create(
                option_set=option_set,
                option_key="all",
                defaults={
                    "option_label": "All",
                    "confidence": 1.0,
                    "needs_manual_check": False,
                    "is_applicable": True,
                    "source": "perplexity",
                },
            )
            final_options.append(opt)
            if perp_result:
                for comp in perp_result:
                    PartCompatibility.objects.update_or_create(
                        option=opt,
                        make=comp["make"],
                        model=comp["model"],
                        year_range_start=comp["year_range_start"],
                        year_range_end=comp["year_range_end"],
                        defaults={"trim": comp.get("trim", ""), "notes": comp.get("notes", "")},
                    )

        elif carpart_status == "found" and raw_options:
            # Special handling for headlight options (LED/Halogen ambiguity)
            part_lower = part.label.lower()
            is_headlight = "headlight" in part_lower or "headlamp" in part_lower
            google_result = {}
            if is_headlight:
                google_result = headlight_type_from_google(
                    year=vehicle.year or 2000,
                    make=vehicle.make or "",
                    model=vehicle.model or "",
                    engine=vehicle.engine or "",
                )

            selected = select_part_options(
                vehicle_info=vehicle_info,
                part_name=part.label,
                raw_options=raw_options,
                ai_description=ai_description,
            )

            for sel in selected:
                if not sel.get("is_applicable"):
                    continue
                confidence = sel["confidence"]
                needs_check = sel["needs_manual_check"]

                # Override with Google AI result for headlights
                if is_headlight and google_result.get("option_label"):
                    if google_result["option_label"].lower() in sel["label"].lower():
                        confidence = max(confidence, google_result["confidence"])
                        needs_check = google_result["needs_manual_check"]

                opt, _ = PartOption.objects.update_or_create(
                    option_set=option_set,
                    option_key=sel["key"],
                    defaults={
                        "option_label": sel["label"],
                        "confidence": confidence,
                        "needs_manual_check": needs_check,
                        "is_applicable": True,
                        "source": "car_part_com",
                    },
                )
                final_options.append(opt)

                # Get compatibility for each applicable option
                if confidence >= 0.9 or not needs_check:
                    compat_list = get_option_compatibility(
                        vehicle_info=vehicle_info,
                        part_name=part.label,
                        option_label=sel["label"],
                    )
                    for comp in compat_list:
                        PartCompatibility.objects.update_or_create(
                            option=opt,
                            make=comp["make"],
                            model=comp["model"],
                            year_range_start=comp["year_range_start"],
                            year_range_end=comp["year_range_end"],
                            defaults={"trim": comp.get("trim", ""), "notes": comp.get("notes", "")},
                        )

        # ------------------------------------------------------------------
        # Step 7: Assign primary option to the part (first applicable high-confidence)
        # ------------------------------------------------------------------
        best_option = next(
            (o for o in final_options if not o.needs_manual_check and o.is_applicable),
            final_options[0] if final_options else None,
        )

        # ------------------------------------------------------------------
        # Step 8: Save all updates to the part
        # ------------------------------------------------------------------
        VehiclePart.objects.filter(pk=vehicle_part_id).update(
            grade=grade,
            ai_description=ai_description[:5000] if ai_description else "",
            package_size_category=size_info.get("size_category", "small"),
            size_packaged_length_cm=size_info.get("packaged_length_cm"),
            size_packaged_width_cm=size_info.get("packaged_width_cm"),
            size_packaged_height_cm=size_info.get("packaged_height_cm"),
            size_packaged_weight_kg=size_info.get("packaged_weight_kg"),
            primary_photo_section=primary_section,
            selected_option=best_option,
            listing_pipeline_status="done",
            listing_pipeline_completed_at=timezone.now(),
            listing_pipeline_error="",
            updated_at=timezone.now(),
        )

        return {
            "vehicle_part_id": vehicle_part_id,
            "grade": grade,
            "package_size": size_info.get("size_category"),
            "options_count": len(final_options),
            "options_status": carpart_status,
            "primary_section": primary_section,
        }

    except Exception as exc:
        logger.exception("run_part_listing_pipeline failed part_id=%s", vehicle_part_id)
        VehiclePart.objects.filter(pk=vehicle_part_id).update(
            listing_pipeline_status="failed",
            listing_pipeline_error=str(exc)[:500],
            updated_at=timezone.now(),
        )
        return {"error": str(exc), "vehicle_part_id": vehicle_part_id}
