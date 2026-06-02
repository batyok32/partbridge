"""Celery tasks for Lookmypart market analytics (ScrapingBee + eBay + embeddings)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


def _missing_analytics_credentials() -> list[str]:
    """Keys required by ``bee_ai_scraper.ScrapingBeeAIScraper`` / ``EmbeddingCategoryMatcher``."""
    missing: list[str] = []
    if not (getattr(settings, "SCRAPING_BEE_API_KEY", "") or "").strip():
        missing.append("SCRAPING_BEE_API_KEY")
    if not (getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip():
        missing.append("DEEPSEEK_API_KEY")
    if not (getattr(settings, "OPENAI_API_KEY", "") or "").strip():
        missing.append("OPENAI_API_KEY")
    return missing


@shared_task
def run_vehicle_market_analysis(vehicle_id: int) -> dict:
    """
    Scrape eBay sold/active for Y/M/M, classify listings, build part-out summary.
    Creates a PartAnalysis row and updates Vehicle analytics fields.
    """
    close_old_connections()

    from vehicles.models import Vehicle

    vehicle = Vehicle.objects.select_related("owner").get(pk=vehicle_id)

    if not vehicle.year or not (vehicle.make or "").strip() or not (vehicle.model or "").strip():
        _mark_failed(
            vehicle,
            "Vehicle needs year, make, and model before market analytics can run.",
        )
        return {"status": "skipped", "reason": "incomplete_vehicle"}

    missing = _missing_analytics_credentials()
    if missing:
        msg = (
            "Market analytics is not configured on the server. "
            "Add these to backend/.env (see .env.example): "
            + ", ".join(missing)
        )
        logger.warning("run_vehicle_market_analysis: %s", msg)
        _mark_failed(vehicle, msg)
        _send_failed_email(vehicle, msg, analysis=None)
        return {"status": "failed", "missing_keys": missing}

    from analytics.models import PartAnalysis
    from analytics.services.bee_ai_scraper import ScrapingBeeAIScraper

    analysis = PartAnalysis.objects.create(
        user=vehicle.owner,
        vehicle=vehicle,
        is_multi_part=True,
        vehicle_year=vehicle.year,
        vehicle_make=(vehicle.make or "").strip(),
        vehicle_model=(vehicle.model or "").strip(),
        part_name="",
        status="processing",
    )

    query = f"{vehicle.year} {vehicle.make} {vehicle.model}"
    max_pages = int(getattr(settings, "VEHICLE_MARKET_ANALYTICS_MAX_PAGES", 5))

    try:
        scraper = ScrapingBeeAIScraper(
            query=query,
            max_pages=max_pages,
            items_per_page=240,
            claude_batch_size=10,
            vehicle_year=vehicle.year,
            vehicle_make=(vehicle.make or "").strip(),
            vehicle_model=(vehicle.model or "").strip(),
            part_name=None,
        )
        report = asyncio.run(scraper.scrape())
        time.sleep(0.2)

        analysis.analysis_data = report
        analysis.status = "completed"
        analysis.completed_at = timezone.now()
        analysis.save(
            update_fields=["analysis_data", "status", "completed_at"]
        )

        now = timezone.now()
        refresh_days = int(getattr(settings, "VEHICLE_MARKET_ANALYTICS_REFRESH_DAYS", 30))
        vehicle.analytics_status = Vehicle.AnalyticsStatus.READY
        vehicle.analytics_last_completed_at = now
        vehicle.analytics_next_refresh_at = now + timedelta(days=refresh_days)
        vehicle.save(
            update_fields=[
                "analytics_status",
                "analytics_last_completed_at",
                "analytics_next_refresh_at",
                "updated_at",
            ]
        )

        _send_ready_email(vehicle, analysis)
        return {"status": "success", "analysis_id": str(analysis.id)}

    except Exception as exc:
        logger.exception("run_vehicle_market_analysis failed for vehicle %s", vehicle_id)
        err = str(exc)
        analysis.status = "failed"
        analysis.error_message = err
        analysis.save(update_fields=["status", "error_message"])

        vehicle.analytics_status = Vehicle.AnalyticsStatus.FAILED
        vehicle.save(update_fields=["analytics_status", "updated_at"])

        _send_failed_email(vehicle, err, analysis=analysis)

        return {"status": "failed", "error": err}


def _mark_failed(vehicle, message: str) -> None:
    from vehicles.models import Vehicle

    vehicle.analytics_status = Vehicle.AnalyticsStatus.FAILED
    vehicle.save(update_fields=["analytics_status", "updated_at"])
    logger.warning("vehicle %s analytics skipped: %s", vehicle.pk, message)


def _send_ready_email(vehicle, analysis) -> None:
    owner = vehicle.owner
    front = getattr(settings, "FRONTEND_URL", None) or getattr(
        settings, "FRONTEND_BASE_URL", "http://localhost:3000"
    ).rstrip("/")
    link = f"{front}/vehicles/{vehicle.pk}"
    subject = f"Lookmypart: market data ready for {vehicle.vin}"
    body = (
        f"Hi {owner.name},\n\n"
        f"eBay market analytics for your {vehicle.year} {vehicle.make} {vehicle.model} "
        f"are ready.\n\n"
        f"Open your vehicle dashboard:\n{link}\n\n"
        f"— Lookmypart\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [owner.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("ready email failed for vehicle %s", vehicle.pk)


def _send_failed_email(vehicle, error_message: str, analysis=None) -> None:
    owner = vehicle.owner
    front = getattr(settings, "FRONTEND_URL", None) or getattr(
        settings, "FRONTEND_BASE_URL", "http://localhost:3000"
    ).rstrip("/")
    link = f"{front}/vehicles/{vehicle.pk}"
    subject = f"Lookmypart: market analytics failed for {vehicle.vin}"
    body = (
        f"Hi {owner.name},\n\n"
        f"We could not finish eBay market analytics for your vehicle.\n\n"
        f"Details: {error_message}\n\n"
        f"You can retry from the dashboard when ready:\n{link}\n\n"
        f"— Lookmypart\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [owner.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("failure email failed for vehicle %s", vehicle.pk)


@shared_task
def cleanup_old_analyses(days: int = 90) -> dict:
    """Delete completed/failed analyses older than ``days`` (Celery Beat)."""
    from analytics.models import PartAnalysis

    try:
        cutoff = timezone.now() - timedelta(days=days)
        deleted = PartAnalysis.objects.filter(
            created_at__lt=cutoff,
            status__in=["completed", "failed"],
        ).delete()[0]
        logger.info("cleaned up %s old PartAnalysis rows", deleted)
        return {"status": "success", "deleted": deleted}
    except Exception as exc:
        logger.exception("cleanup_old_analyses: %s", exc)
        return {"status": "error", "message": str(exc)}
