import logging
import re
import traceback
import uuid
from decimal import Decimal
from datetime import timedelta

import httpx
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import CharField, DictField, IntegerField, ListField, Serializer
from rest_framework.views import APIView

from .ai_assist import deepseek_refine_part_phrase, suggest_cars_and_part_phrase
from .analytics_pipeline import attach_analytics_after_commit
from .catalog_seed import seed_parts_for_vehicle
from .damage_stub import apply_damage_notes_stub
from .models import (
    BrowseErrorReport,
    PartCategory,
    PartCompatibility,
    PartFamily,
    PartOption,
    PartOptionSet,
    ReturnPolicy,
    Vehicle,
    VehiclePart,
    VehiclePartPhoto,
    VehiclePhoto,
)
from .nhtsa import decode_vin
from .permissions import IsVehicleOwner, IsVehiclePartOwner
from .seller_permissions import IsApprovedSeller
from .serializers import (
    BrowseErrorReportSerializer,
    CustomPartCreateSerializer,
    PartCategorySerializer,
    PartFamilySerializer,
    PartOptionSetSerializer,
    VehicleCreateUpdateSerializer,
    VehicleDetailSerializer,
    VehicleListSerializer,
    VehiclePartPhotoSerializer,
    VehiclePartSerializer,
    VehiclePhotoSerializer,
    VinDecodeSerializer,
    PublicVehiclePartSerializer,
)
from .shipping_preview import mask_zip, shipping_preview_stub
from .variant_utils import label_for_part, variant_key_from_dict

# Optional expiry for price-template imports (default is evergreen Buy Now).
BUY_NOW_DURATION_TO_DELTA = {
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "1w": timedelta(weeks=1),
    "1m": timedelta(days=30),
}

logger = logging.getLogger(__name__)


def _vehicle_primary_photo_url(vehicle, request):
    ph = (
        VehiclePhoto.objects.filter(vehicle=vehicle)
        .order_by("sort_order", "id")
        .first()
    )
    if not ph or not ph.image:
        return None
    try:
        url = ph.image.url
    except ValueError:
        return None
    if request:
        return request.build_absolute_uri(url)
    return url


def _vehicle_public_photos_payload(vehicle, request, max_photos: int = 12):
    """Ordered gallery URLs for anonymous browse (donor cards + detail)."""
    out = []
    for ph in vehicle.photos.all()[:max_photos]:
        if not ph.image:
            continue
        try:
            url = ph.image.url
        except ValueError:
            continue
        abs_url = request.build_absolute_uri(url) if request else url
        out.append({"id": ph.id, "kind": ph.kind, "url": abs_url})
    return out


def _build_potential_donor_payloads(qs, _buyer_zip: str, request):
    """Rich donor-vehicle rows for browse assist (not just Y/M/M chips)."""
    from orders.models import Order

    buckets = (
        qs.values("vehicle_id")
        .annotate(match_count=Count("id"))
        .order_by("-match_count", "-vehicle_id")[:18]
    )
    vehicle_ids = [row["vehicle_id"] for row in buckets]
    if not vehicle_ids:
        return []
    count_by_vid = {row["vehicle_id"]: row["match_count"] for row in buckets}

    vehicles = (
        Vehicle.objects.filter(id__in=vehicle_ids)
        .select_related("owner")
        .prefetch_related(
            Prefetch(
                "photos",
                queryset=VehiclePhoto.objects.order_by("sort_order", "id"),
            )
        )
    )
    vehicles_by_id = {v.id: v for v in vehicles}

    seller_ids = list({v.owner_id for v in vehicles_by_id.values()})
    delivered_stats = {
        row["seller_id"]: row["c"]
        for row in Order.objects.filter(seller_id__in=seller_ids, state=Order.State.DELIVERED)
        .values("seller_id")
        .annotate(c=Count("id"))
    }

    out = []
    for vid in vehicle_ids:
        v = vehicles_by_id.get(vid)
        if not v:
            continue
        owner = v.owner
        display_name = (owner.get_full_name() or "").strip() or owner.username
        completed = int(delivered_stats.get(owner.id, 0))
        sample_part_id = qs.filter(vehicle_id=vid).order_by("id").values_list("id", flat=True).first()
        gallery = _vehicle_public_photos_payload(v, request, max_photos=12)
        primary = gallery[0]["url"] if gallery else _vehicle_primary_photo_url(v, request)
        out.append(
            {
                "vehicle_id": v.id,
                "year": v.year,
                "make": v.make,
                "model": v.model,
                "trim": (v.trim or "").strip(),
                "engine": (v.engine or "").strip(),
                "transmission": (v.transmission or "").strip(),
                "drivetrain": (v.drivetrain or "").strip(),
                "body_style": (v.body_style or "").strip(),
                "color": (v.color or "").strip(),
                "vin_masked": (v.vin[-4:] if v.vin and len(v.vin) >= 4 else None),
                "location_state": (v.location_state or "").strip(),
                "location_zip_masked": mask_zip(v.location_zip),
                "has_damage": bool(v.has_damage),
                "primary_photo_url": primary,
                "photo_urls": gallery,
                "matching_parts_count": count_by_vid.get(vid, 0),
                "sample_vehicle_part_id": sample_part_id,
                "seller": {
                    "id": owner.id,
                    "display_name": display_name,
                    "member_since": owner.date_joined.isoformat() if owner.date_joined else None,
                    "completed_sales": completed,
                    "rating_avg": None,
                    "rating_count": 0,
                    "trust_note": (
                        f"{completed} completed sales on PartBridge"
                        if completed
                        else "New seller — no completed sales yet"
                    ),
                },
            }
        )
    return out


class DecodeVinView(APIView):
    """POST /vin/decode/ — NHTSA vPIC decode (no vehicle row created)."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def post(self, request):
        ser = VinDecodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        include_raw = ser.validated_data.get("include_raw") or False
        try:
            result = decode_vin(ser.validated_data["vin"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not include_raw:
            result = {k: v for k, v in result.items() if k != "raw"}
        return Response(result)


class PartCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = PartCategory.objects.all()
    serializer_class = PartCategorySerializer


class PartFamilyListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PartFamilySerializer

    def get_queryset(self):
        qs = PartFamily.objects.select_related("category").all()
        if self.request.query_params.get("sellable") == "1":
            qs = qs.filter(buy_new_only=False)
        return qs


class PartsPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 200


class VehicleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsApprovedSeller, IsVehicleOwner]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Vehicle.objects.filter(owner=self.request.user)
        if self.action == "retrieve":
            qs = qs.prefetch_related("photos")
        if self.action == "list":
            qs = qs.annotate(
                parts_count=Count("parts", distinct=True),
                photos_count=Count("photos", distinct=True),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return VehicleListSerializer
        if self.action in ("create", "update", "partial_update"):
            return VehicleCreateUpdateSerializer
        return VehicleDetailSerializer

    def perform_create(self, serializer):
        vehicle = serializer.save(
            owner=self.request.user,
            analytics_status=Vehicle.AnalyticsStatus.PROCESSING,
        )
        attach_analytics_after_commit(vehicle.id)
        # Kick off image analysis for the new vehicle (photos may not exist yet,
        # but this runs after any batch photo upload via upload_photo action)
        from .tasks import analyze_vehicle_images
        analyze_vehicle_images.apply_async(args=[vehicle.id], countdown=10)

    @action(detail=True, methods=["post"])
    def refresh_market_analysis(self, request, pk=None):
        vehicle = self.get_object()
        if vehicle.analytics_status == Vehicle.AnalyticsStatus.PROCESSING:
            return Response(
                {"detail": "Market analytics are already running for this vehicle."},
                status=status.HTTP_409_CONFLICT,
            )
        if not vehicle.can_refresh_market_analytics():
            return Response(
                {
                    "detail": "Manual refresh is limited to once per 30 days per vehicle.",
                    "analytics_next_refresh_at": vehicle.analytics_next_refresh_at,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        Vehicle.objects.filter(pk=vehicle.pk).update(
            analytics_status=Vehicle.AnalyticsStatus.PROCESSING,
        )
        attach_analytics_after_commit(vehicle.pk)
        return Response(
            {
                "detail": "Market analytics queued.",
                "analytics_status": Vehicle.AnalyticsStatus.PROCESSING,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def seed_parts(self, request, pk=None):
        vehicle = self.get_object()
        created = seed_parts_for_vehicle(vehicle)
        return Response(
            {"created": created, "parts_total": vehicle.parts.count()},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def infer_damage(self, request, pk=None):
        vehicle = self.get_object()
        notes = request.data.get("damage_notes")
        if notes is None:
            return Response({"detail": "damage_notes is required (list of strings)."}, status=400)
        if not isinstance(notes, list):
            return Response({"detail": "damage_notes must be a list."}, status=400)
        marked = apply_damage_notes_stub(vehicle, [str(x) for x in notes])
        return Response({"marked": marked})

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_photo(self, request, pk=None):
        vehicle = self.get_object()
        ser = VehiclePhotoSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save(vehicle=vehicle)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    class _PriceTemplateInputSerializer(Serializer):
        # Large templates can be 400+ lines; keep this generous.
        template_text = CharField(allow_blank=False, max_length=500000)
        condition_draft = CharField(required=False, allow_blank=True, max_length=32)
        buy_now_duration = CharField(required=False, allow_blank=True, max_length=8)

    @staticmethod
    def _normalize_part_name(s: str) -> str:
        s = (s or "").strip().upper()
        s = re.sub(r"\s+", " ", s)
        return s

    @staticmethod
    def _normalize_match_key(s: str) -> str:
        """Normalization for fuzzy-ish matching against catalog names."""
        s = (s or "").strip().upper()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"[^A-Z0-9 ]+", "", s)  # drop punctuation like ()-/ etc
        return s.strip()

    @staticmethod
    def _tokenize(s: str) -> set[str]:
        toks = {t for t in re.split(r"\s+", (s or "").strip().upper()) if t}
        # drop very short tokens that add noise
        return {t for t in toks if len(t) >= 3}

    @classmethod
    def _best_part_family_match_id(cls, part_name: str, pf_index: dict) -> int | None:
        """
        Try multiple matching strategies to map template part lines to catalog PartFamily.
        pf_index: {"exact": {norm->id}, "keys": [(id, match_key, tokens)]}
        """
        exact = pf_index["exact"].get(cls._normalize_part_name(part_name))
        if exact:
            return exact

        key = cls._normalize_match_key(part_name)
        # Fast exact on cleaned key as well
        if (mid := pf_index["exact_key"].get(key)):
            return mid

        # Heuristic: best token overlap (Jaccard-ish), then length proximity.
        name_tokens = cls._tokenize(key)
        if not name_tokens:
            return None
        best_id = None
        best_score = 0.0
        best_len_delta = 10**9
        for pf_id, pf_key, pf_tokens in pf_index["keys"]:
            inter = len(name_tokens & pf_tokens)
            if inter == 0:
                continue
            union = len(name_tokens | pf_tokens) or 1
            score = inter / union
            len_delta = abs(len(pf_key) - len(key))
            if score > best_score or (score == best_score and len_delta < best_len_delta):
                best_score = score
                best_len_delta = len_delta
                best_id = pf_id
        # Require a minimal match quality so we don't map random names.
        if best_score >= 0.55:
            return best_id
        return None

    @staticmethod
    def _parse_template_line(line: str) -> tuple[str, Decimal] | None:
        """
        Accepts lines like:
          ENGINE COMPLETE $519.99
          MOTOR MOUNT 24.69
          CRANKSHAFT $1,200.00
        Returns (part_name, Decimal(price)) or None for blank/unparseable lines.
        """
        raw = (line or "").strip()
        if not raw:
            return None

        # Split on last " $price" or " price"
        m = re.match(r"^(?P<name>.+?)\s+\$?(?P<price>\d[\d,]*\.\d{2})\s*$", raw)
        if not m:
            return None
        name = (m.group("name") or "").strip()
        price_s = (m.group("price") or "").strip().replace(",", "")
        if not name:
            return None
        try:
            price = Decimal(price_s)
        except Exception:
            return None
        return (name, price)

    @action(detail=True, methods=["post"])
    def apply_price_template(self, request, pk=None):
        """
        POST /vehicles/{id}/apply_price_template/

        Parses plain-text lines like "ENGINE COMPLETE $519.99", matches each line to a
        catalog PartFamily, then creates or updates a VehiclePart as Buy Now (no expiry by default).

        Optional body keys:
          - condition_draft: condition enum for every matched line (default: used)
          - buy_now_duration: "never" (default) or a key from BUY_NOW_DURATION_TO_DELTA for expiry
        """
        # ------------------------------------------------------------------
        # Step 1 — Resolve vehicle and validate request body
        # ------------------------------------------------------------------
        vehicle = self.get_object()
        print(f"[price_template] start vehicle_id={vehicle.id} user={request.user.id}", flush=True)
        logger.info("apply_price_template: start vehicle_id=%s", vehicle.pk)

        ser = self._PriceTemplateInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        template_text = (vd.get("template_text") or "").strip()
        raw_cd = vd.get("condition_draft")
        if raw_cd is not None and str(raw_cd).strip():
            condition_draft = str(raw_cd).strip()
        else:
            condition_draft = VehiclePart.ConditionDraft.USED

        # Optional expiry: default is evergreen Buy Now (no buy_now_expires_at).
        duration_key = (vd.get("buy_now_duration") or "").strip() or "never"
        expires_at = None
        if duration_key != "never":
            delta = BUY_NOW_DURATION_TO_DELTA.get(duration_key, BUY_NOW_DURATION_TO_DELTA["1w"])
            expires_at = timezone.now() + delta

        line_count = len(template_text.splitlines())
        char_len = len(template_text)
        print(
            f"[price_template] input: {line_count} lines, {char_len} chars, "
            f"condition_draft={condition_draft}, duration_key={duration_key!r}, expires_at={expires_at}",
            flush=True,
        )
        logger.info(
            "apply_price_template: lines=%s chars=%s condition=%s duration=%s",
            line_count,
            char_len,
            condition_draft,
            duration_key,
        )

        # ------------------------------------------------------------------
        # Step 2 — Build lookup indexes for PartFamily rows (exact + fuzzy match)
        # ------------------------------------------------------------------
        # We need fast matching from a free-text part name (from the template) to a PartFamily.
        # Indexes:
        #   exact:    normalized catalog name (upper, single spaces) -> part_family_id
        #   exact_key: punctuation-stripped key -> id (handles "CAMSHAFT (BARE)" vs catalog)
        #   keys:      list of (id, key, token_set) for token-overlap scoring
        pf_rows = list(PartFamily.objects.values_list("id", "name"))
        exact = {}
        exact_key = {}
        keys = []
        for pf_id, pf_name in pf_rows:
            n = self._normalize_part_name(pf_name)
            exact.setdefault(n, pf_id)
            k = self._normalize_match_key(pf_name)
            exact_key.setdefault(k, pf_id)
            keys.append((pf_id, k, self._tokenize(k)))
        pf_index = {"exact": exact, "exact_key": exact_key, "keys": keys}
        print(
            f"[price_template] catalog index: {len(pf_rows)} PartFamily rows, "
            f"{len(exact)} exact keys, {len(exact_key)} stripped keys",
            flush=True,
        )

        # Default category for auto-created PartFamily rows (seller price lists rarely match 22 seed names).
        default_category = PartCategory.objects.order_by("sort_order", "id").first()
        if not default_category:
            return Response(
                {"detail": "No part categories configured; cannot create parts from template."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Same template often repeats labels; cache normalized name -> part_family_id in this request.
        template_pf_cache: dict[str, int] = {}

        # ------------------------------------------------------------------
        # Step 3 — Walk each line: parse -> match PartFamily -> get_or_create VehiclePart -> save
        # ------------------------------------------------------------------
        results = []
        created = 0
        updated = 0
        skipped = 0
        parse_fail = 0
        part_families_created = 0

        for idx, line in enumerate(template_text.splitlines(), start=1):
            # Step 3a — Parse "NAME $price" (blank lines are ignored)
            parsed = self._parse_template_line(line)
            if not parsed:
                if (line or "").strip():
                    skipped += 1
                    parse_fail += 1
                    results.append({"line": idx, "raw": line, "status": "skipped", "reason": "Could not parse."})
                continue

            part_name, price = parsed
            if price <= 0:
                skipped += 1
                results.append(
                    {
                        "line": idx,
                        "raw": line,
                        "status": "skipped",
                        "reason": "Price must be greater than zero for Buy Now.",
                    }
                )
                continue
            norm_key = self._normalize_part_name(part_name)

            # Step 3b — Resolve PartFamily: in-request cache → catalog match → existing by name → create new
            if norm_key in template_pf_cache:
                pf_id = template_pf_cache[norm_key]
            else:
                pf_id = self._best_part_family_match_id(part_name, pf_index)
                if not pf_id:
                    existing_pf = PartFamily.objects.filter(name__iexact=part_name.strip()).first()
                    if existing_pf:
                        pf_id = existing_pf.pk
                        if idx <= 3:
                            print(
                                f"[price_template] line {idx}: matched existing PartFamily id={pf_id} name={part_name!r}",
                                flush=True,
                            )
                    else:
                        slug = f"{slugify(part_name.strip())[:40]}-{uuid.uuid4().hex[:10]}"
                        fam = PartFamily.objects.create(
                            category=default_category,
                            slug=slug,
                            name=part_name.strip()[:255],
                            buy_new_only=False,
                            variant_templates=[],
                            created_by=request.user,
                        )
                        pf_id = fam.pk
                        part_families_created += 1
                        if idx <= 5 or idx % 100 == 0:
                            print(
                                f"[price_template] line {idx}: created PartFamily id={pf_id} name={part_name!r}",
                                flush=True,
                            )
                        # New catalog row: keep indexes consistent for later lines (optional)
                        n = self._normalize_part_name(fam.name)
                        exact[n] = pf_id
                        k = self._normalize_match_key(fam.name)
                        exact_key.setdefault(k, pf_id)
                        keys.append((pf_id, k, self._tokenize(k)))

                template_pf_cache[norm_key] = pf_id

            # Step 3c — One inventory row per (vehicle, part_family, variant_key="")
            vp, was_created = VehiclePart.objects.get_or_create(
                vehicle=vehicle,
                part_family_id=pf_id,
                variant_key="",
                defaults={"label": part_name},
            )

            # Step 3d — Apply listing fields (Buy Now + price + optional expiry)
            vp.label = vp.label or part_name
            vp.price = price
            vp.listing_state = VehiclePart.ListingState.BUY_NOW
            vp.condition_draft = condition_draft
            vp.buy_now_expires_at = expires_at
            vp.is_removed = False
            vp.save(
                update_fields=[
                    "label",
                    "price",
                    "listing_state",
                    "condition_draft",
                    "buy_now_expires_at",
                    "is_removed",
                    "updated_at",
                ]
            )

            if was_created:
                created += 1
                results.append({"line": idx, "raw": line, "status": "created", "vehicle_part_id": vp.id})
            else:
                updated += 1
                results.append({"line": idx, "raw": line, "status": "updated", "vehicle_part_id": vp.id})

        # ------------------------------------------------------------------
        # Step 4 — Response summary and capped per-line results (API payload size)
        # ------------------------------------------------------------------
        results_cap = 600
        results_out = results[:results_cap]
        truncated = len(results) > results_cap
        print(
            f"[price_template] done: vehicle_parts_created={created} vehicle_parts_updated={updated} "
            f"skipped={skipped} parse_fail={parse_fail} part_families_created={part_families_created} "
            f"total_results_rows={len(results)} truncated={truncated}",
            flush=True,
        )
        logger.info(
            "apply_price_template: done created=%s updated=%s skipped=%s part_families_created=%s",
            created,
            updated,
            skipped,
            part_families_created,
        )

        return Response(
            {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "total_lines": line_count,
                "parse_failures": parse_fail,
                "part_families_created": part_families_created,
                "condition_draft": condition_draft,
                "buy_now_duration": duration_key,
                "results": results_out,
                "results_truncated": truncated,
                "results_total": len(results),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def custom_parts(self, request, pk=None):
        vehicle = self.get_object()
        ser = CustomPartCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        category = ser.validated_data["category"]
        name = ser.validated_data["name"].strip()
        templates = ser.validated_data.get("variant_templates")
        if templates is None:
            templates = []
        if not isinstance(templates, list):
            return Response({"detail": "variant_templates must be a list."}, status=400)
        slug = f"{slugify(name)[:48]}-{uuid.uuid4().hex[:10]}"
        stored_templates = templates if templates else []
        family = PartFamily.objects.create(
            category=category,
            slug=slug,
            name=name,
            buy_new_only=False,
            variant_templates=stored_templates,
            created_by=request.user,
        )
        tmpls = family.variant_templates if family.variant_templates else [{}]
        created = 0
        for tmpl in tmpls:
            if not isinstance(tmpl, dict):
                tmpl = {}
            vk = variant_key_from_dict(tmpl)
            label = label_for_part(family.name, tmpl)
            _, was_created = VehiclePart.objects.get_or_create(
                vehicle=vehicle,
                part_family=family,
                variant_key=vk,
                defaults={"label": label},
            )
            if was_created:
                created += 1
        return Response({"part_family_id": family.id, "parts_created": created}, status=status.HTTP_201_CREATED)


class VehiclePartListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller]
    serializer_class = VehiclePartSerializer
    pagination_class = PartsPagination

    def get_queryset(self):
        vehicle = get_object_or_404(Vehicle, pk=self.kwargs["vehicle_id"], owner=self.request.user)
        qs = vehicle.parts.select_related("part_family", "part_family__category")
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(label__icontains=q)
                | Q(description__icontains=q)
                | Q(part_family__name__icontains=q)
            )
        cat = self.request.query_params.get("category")
        if cat:
            qs = qs.filter(part_family__category__slug=cat)
        st = self.request.query_params.get("listing_state")
        if st:
            qs = qs.filter(listing_state=st)
            if st in (
                VehiclePart.ListingState.SOLD,
                VehiclePart.ListingState.UNAVAILABLE,
                VehiclePart.ListingState.SOLD_ELSEWHERE,
            ):
                if self.request.query_params.get("show_old") not in ("1", "true", "True"):
                    cutoff = timezone.now() - timedelta(days=90)
                    qs = qs.filter(updated_at__gte=cutoff)
        if self.request.query_params.get("hide_removed") == "1":
            qs = qs.filter(is_removed=False)
        ordering = (self.request.query_params.get("ordering") or "").strip()
        order_map = {
            "updated": "-updated_at",
            "price_asc": "price",
            "price_desc": "-price",
            "label_asc": "label",
            "label_desc": "-label",
        }
        if ordering in order_map:
            return qs.order_by(order_map[ordering], "id")
        return qs.order_by("part_family__category__sort_order", "part_family__name", "variant_key")


class VehiclePartBulkDeleteView(APIView):
    """POST — bulk delete parts with the same safety rules as single delete."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]

    class _Input(Serializer):
        part_ids = ListField(child=IntegerField(min_value=1), allow_empty=False)
        force = IntegerField(required=False)

    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        ser = self._Input(data=request.data)
        ser.is_valid(raise_exception=True)
        part_ids = list({int(x) for x in ser.validated_data["part_ids"]})
        force = ser.validated_data.get("force") in (1, "1", True)

        parts = list(vehicle.parts.filter(id__in=part_ids))
        found_ids = {p.id for p in parts}
        missing = [pid for pid in part_ids if pid not in found_ids]

        blocked = []
        needs_force = []
        deleted = []

        for p in parts:
            orders_count = p.orders.count()
            cart_items_count = p.cart_items.count()
            quotes_count = p.quotes.count()
            threads_count = p.message_threads.count()

            if orders_count:
                blocked.append(
                    {
                        "id": p.id,
                        "label": p.label,
                        "reason": "orders_attached",
                        "counts": {
                            "orders": orders_count,
                            "cart_items": cart_items_count,
                            "quotes": quotes_count,
                            "message_threads": threads_count,
                        },
                    }
                )
                continue

            has_activity = (cart_items_count + quotes_count + threads_count) > 0
            if has_activity and not force:
                needs_force.append(
                    {
                        "id": p.id,
                        "label": p.label,
                        "reason": "activity_attached",
                        "counts": {
                            "orders": orders_count,
                            "cart_items": cart_items_count,
                            "quotes": quotes_count,
                            "message_threads": threads_count,
                        },
                    }
                )
                continue

            if force:
                p.quotes.all().delete()
                p.message_threads.update(vehicle_part=None)

            p.delete()
            deleted.append(p.id)

        status_code = status.HTTP_200_OK
        if blocked or needs_force:
            status_code = status.HTTP_409_CONFLICT

        return Response(
            {
                "deleted_ids": deleted,
                "blocked": blocked,
                "needs_force": needs_force,
                "missing": missing,
            },
            status=status_code,
        )


class VehiclePartBulkUpdateView(APIView):
    """POST — bulk update fields on parts (used for return policy propagation)."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]

    class _Input(Serializer):
        part_ids = ListField(child=IntegerField(min_value=1), allow_empty=False)
        return_policy = CharField(required=False, allow_blank=False, max_length=16)

    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        ser = self._Input(data=request.data)
        ser.is_valid(raise_exception=True)
        part_ids = list({int(x) for x in ser.validated_data["part_ids"]})
        qs = vehicle.parts.filter(id__in=part_ids)

        updated = 0
        fields = []
        if "return_policy" in ser.validated_data:
            rp = ser.validated_data["return_policy"]
            valid = {c[0] for c in ReturnPolicy.choices}
            if rp not in valid:
                return Response({"detail": "Invalid return_policy."}, status=400)
            qs.update(return_policy=rp, updated_at=timezone.now())
            updated = qs.count()
            fields.append("return_policy")

        return Response({"updated": updated, "fields": fields})


class VehiclePartDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller, IsVehiclePartOwner]
    serializer_class = VehiclePartSerializer

    def get_queryset(self):
        return VehiclePart.objects.select_related(
            "vehicle",
            "part_family",
            "part_family__category",
        ).filter(vehicle__owner=self.request.user)

    def get_object(self):
        vehicle = get_object_or_404(Vehicle, pk=self.kwargs["vehicle_id"], owner=self.request.user)
        return get_object_or_404(VehiclePart, pk=self.kwargs["pk"], vehicle=vehicle)

    def destroy(self, request, *args, **kwargs):
        """
        Safe delete:
        - If the part is referenced by an Order (PROTECT), deletion is blocked.
        - If the part has "offers"/activity (quotes, threads, cart items), return 409 unless ?force=1.
        - With ?force=1, quotes are deleted and threads are detached (vehicle_part=NULL), then the part is deleted.
        """
        part = self.get_object()

        orders_count = part.orders.count()
        cart_items_count = part.cart_items.count()
        quotes_count = part.quotes.count()
        threads_count = part.message_threads.count()

        if orders_count:
            return Response(
                {
                    "detail": "This part cannot be deleted because it has orders attached.",
                    "counts": {
                        "orders": orders_count,
                        "cart_items": cart_items_count,
                        "quotes": quotes_count,
                        "message_threads": threads_count,
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        has_activity = (cart_items_count + quotes_count + threads_count) > 0
        force = request.query_params.get("force") in ("1", "true", "True", "yes")
        if has_activity and not force:
            return Response(
                {
                    "detail": "This part has offers/messages attached. Deleting it will also delete related offers.",
                    "counts": {
                        "orders": orders_count,
                        "cart_items": cart_items_count,
                        "quotes": quotes_count,
                        "message_threads": threads_count,
                    },
                    "hint": "Retry with ?force=1 to delete anyway.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        if force:
            # Delete offers (quotes) explicitly; detach threads so message history remains.
            part.quotes.all().delete()
            part.message_threads.update(vehicle_part=None)

        part.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def public_listable_vehicle_parts_queryset():
    """Parts visible to anonymous buyers for MVP browse/discovery."""
    return (
        VehiclePart.objects.filter(
            is_removed=False,
            part_family__buy_new_only=False,
            vehicle__year__isnull=False,
        )
        .exclude(vehicle__make="")
        .exclude(vehicle__model="")
        .filter(
            Q(listing_state=VehiclePart.ListingState.BUY_NOW)
            | Q(listing_state=VehiclePart.ListingState.MESSAGE_ONLY)
            | Q(listing_state=VehiclePart.ListingState.DRAFT)
        )
        .select_related("vehicle", "part_family", "part_family__category")
    )


def public_listable_parts_for_buyer_vehicle(
    validated: dict,
    *,
    match_year: bool = True,
    year_slack: int = 5,
):
    """
    All public listable parts on donor vehicles matching buyer make / model, and optionally year.

    match_year=False — used for “browse by car only”: any model year for that make/model.
    When match_year=True and buyer_year is set, allow ±year_slack model years (same generation).
    """
    qs = public_listable_vehicle_parts_queryset()
    if match_year:
        y = validated.get("buyer_year")
        if y is not None:
            try:
                yi = int(y)
                qs = qs.filter(
                    vehicle__year__gte=yi - year_slack,
                    vehicle__year__lte=yi + year_slack,
                )
            except (TypeError, ValueError):
                pass
    if make := (validated.get("buyer_make") or "").strip():
        qs = qs.filter(vehicle__make__icontains=make)
    if model := (validated.get("buyer_model") or "").strip():
        qs = qs.filter(vehicle__model__icontains=model)
    return qs


def _vehicle_ymm_match_q(validated: dict, *, year_slack: int = 5) -> Q:
    """Filter VehiclePart rows whose donor vehicle matches buyer Y/M/M (±year slack)."""
    q = Q()
    y = validated.get("buyer_year")
    if y is not None:
        try:
            yi = int(y)
            q &= Q(vehicle__year__gte=yi - year_slack, vehicle__year__lte=yi + year_slack)
        except (TypeError, ValueError):
            pass
    if make := (validated.get("buyer_make") or "").strip():
        q &= Q(vehicle__make__icontains=make)
    if model := (validated.get("buyer_model") or "").strip():
        q &= Q(vehicle__model__icontains=model)
    return q


def _compat_candidates_vehicle_q(candidates: list[dict]) -> Q | None:
    """
    OR of inventory vehicles matching Perplexity-compatible donor rows (make/model/year ranges).
    """
    compat_q = Q()
    any_row = False
    for c in candidates or []:
        c_make = (c.get("make") or "").strip()
        c_model = (c.get("model") or "").strip()
        yr_start = c.get("year_range_start") or c.get("year")
        yr_end = c.get("year_range_end") or c.get("year")
        if not (c_make or c_model):
            continue
        cq = Q()
        if c_make:
            cq &= Q(vehicle__make__icontains=c_make)
        if c_model:
            cq &= Q(vehicle__model__icontains=c_model)
        if yr_start is not None and yr_end is not None:
            cq &= Q(vehicle__year__gte=yr_start, vehicle__year__lte=yr_end)
        elif yr_start is not None:
            cq &= Q(vehicle__year__gte=yr_start)
        compat_q |= cq
        any_row = True
    return compat_q if any_row else None


def _part_search_term_q(normalized_part: str, refined_for_search: str, part_raw: str) -> Q:
    """
    OR full phrases + individual words (≥3 chars) from the buyer query so short terms
    like "oil", "rim", "battery" still match catalog labels.
    """
    term_q = Q()
    for x in {p for p in (normalized_part, refined_for_search, part_raw) if (p or "").strip()}:
        term_q |= (
            Q(label__icontains=x)
            | Q(description__icontains=x)
            | Q(part_family__name__icontains=x)
        )
    for x in (part_raw, refined_for_search, normalized_part):
        if not (x or "").strip():
            continue
        for w in re.split(r"\W+", x.lower()):
            if len(w) >= 3:
                term_q |= (
                    Q(label__icontains=w)
                    | Q(description__icontains=w)
                    | Q(part_family__name__icontains=w)
                )
    return term_q


class NormalizePartNameView(APIView):
    """POST /browse/normalize-part/ — use DeepSeek to normalize a raw part name."""

    permission_classes = [AllowAny]

    def post(self, request):
        from .ai_assist import _extract_json_block

        raw = str(request.data.get("raw_name") or "").strip()
        if not raw:
            return Response({"error": "raw_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(raw) > 200:
            return Response({"normalized_name": raw[:200]})

        from django.conf import settings as django_settings
        api_key = (getattr(django_settings, "DEEPSEEK_API_KEY", None) or "").strip()
        if not api_key:
            return Response({"normalized_name": raw, "source": "fallback"})

        system = (
            "You normalize raw user-typed car part names into clean, standard catalog names. "
            "Return ONLY this JSON: {\"normalized_name\": string}. "
            "Examples: 'left headlite' → 'Left Headlight', 'frnt bumpr' → 'Front Bumper', "
            "'tranny' → 'Transmission', 'alternater' → 'Alternator'. "
            "Capitalize each word. Keep it concise — 1–4 words."
        )
        try:
            with httpx.Client(timeout=12) as client:
                r = client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": getattr(django_settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": raw},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 60,
                    },
                )
                r.raise_for_status()
                body = r.json()
        except Exception:
            return Response({"normalized_name": raw, "source": "fallback"})

        content = (((body or {}).get("choices") or [{}])[0].get("message", {}).get("content", ""))
        parsed = _extract_json_block(content) or {}
        name = str(parsed.get("normalized_name") or raw).strip()[:120]
        return Response({"normalized_name": name or raw, "source": "deepseek"})


class VehiclePhotoDeleteView(APIView):
    """DELETE /vehicles/{vehicle_id}/photos/{photo_id}/ — remove a single vehicle photo."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def delete(self, request, vehicle_id, photo_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        photo = get_object_or_404(VehiclePhoto, pk=photo_id, vehicle=vehicle)
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehiclePartPhotoUploadView(APIView):
    """POST multipart — upload a local photo for a vehicle part."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, vehicle_id, part_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        part = get_object_or_404(VehiclePart, pk=part_id, vehicle=vehicle)
        ser = VehiclePartPhotoSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        photo = ser.save(vehicle_part=part)

        # Ensure the seller UI can immediately display the uploaded image via existing `image_urls`.
        try:
            abs_url = request.build_absolute_uri(photo.image.url)
        except Exception:
            abs_url = None
        if abs_url:
            current = part.image_urls if isinstance(part.image_urls, list) else []
            part.image_urls = [abs_url, *[u for u in current if u != abs_url]][:8]
            part.save(update_fields=["image_urls", "updated_at"])

        return Response(ser.data, status=status.HTTP_201_CREATED)


class PublicBrowsePagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 48


class PublicPartBrowseView(generics.ListAPIView):
    """
    GET — anonymous browse/search for listed parts (Phase 5).
    Query: year, make, model, trim, category (slug), part_family (id), variant_key,
    q (text), buyer_zip (shipping copy), is_damaged (0|1), facets=1 (category counts).
    """

    permission_classes = [AllowAny]
    serializer_class = PublicVehiclePartSerializer
    pagination_class = PublicBrowsePagination

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["buyer_zip"] = self.request.query_params.get("buyer_zip", "").strip()
        return ctx

    def get_queryset(self):
        qs = public_listable_vehicle_parts_queryset()
        r = self.request.query_params
        if y := r.get("year"):
            try:
                qs = qs.filter(vehicle__year=int(y))
            except ValueError:
                pass
        if make := r.get("make", "").strip():
            qs = qs.filter(vehicle__make__icontains=make)
        if model := r.get("model", "").strip():
            qs = qs.filter(vehicle__model__icontains=model)
        if trim := r.get("trim", "").strip():
            qs = qs.filter(vehicle__trim__icontains=trim)
        if cat := r.get("category", "").strip():
            qs = qs.filter(part_family__category__slug=cat)
        if pf := r.get("part_family"):
            try:
                qs = qs.filter(part_family_id=int(pf))
            except ValueError:
                pass
        if vk := r.get("variant_key", "").strip():
            qs = qs.filter(variant_key=vk)
        if r.get("is_damaged") in ("0", "false", "False"):
            qs = qs.filter(is_damaged=False)
        elif r.get("is_damaged") in ("1", "true", "True"):
            qs = qs.filter(is_damaged=True)
        q = r.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(label__icontains=q)
                | Q(description__icontains=q)
                | Q(part_family__name__icontains=q)
            )
        return qs.order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is None:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        if request.query_params.get("facets") == "1":
            fac = (
                queryset.values(
                    "part_family__category__slug",
                    "part_family__category__name",
                    "part_family__category__sort_order",
                )
                .annotate(count=Count("id"))
                .order_by("part_family__category__sort_order", "part_family__category__name")
            )
            response.data["facets"] = {"categories": list(fac)}
            pf = request.query_params.get("part_family")
            if pf:
                try:
                    vid = int(pf)
                    variants = (
                        queryset.filter(part_family_id=vid)
                        .values("variant_key")
                        .annotate(count=Count("id"))
                        .order_by("variant_key")
                    )
                    response.data["facets"]["variants"] = list(variants)
                except ValueError:
                    response.data["facets"]["variants"] = []
        return response


class PublicCarAssistInputSerializer(Serializer):
    buyer_year = IntegerField(required=False, min_value=1900, max_value=2100)
    buyer_make = CharField(required=False, allow_blank=True, max_length=64)
    buyer_model = CharField(required=False, allow_blank=True, max_length=64)
    part_need = CharField(required=False, allow_blank=True, max_length=200)
    buyer_zip = CharField(required=False, allow_blank=True, max_length=16)
    category = CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        make = (attrs.get("buyer_make") or "").strip()
        part = (attrs.get("part_need") or "").strip()
        cat = (attrs.get("category") or "").strip()
        if not make and not part and not cat:
            raise ValidationError("Please provide a make or a part name to search.")
        if cat and part:
            raise ValidationError("Send either category or part_need, not both.")
        return attrs


class PublicReverseZipView(APIView):
    """GET ?lat=&lon= — resolve US ZIP via OpenStreetMap Nominatim (server-side, reliable User-Agent)."""

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            lat = float(request.query_params.get("lat", ""))
            lon = float(request.query_params.get("lon", ""))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid lat/lon."}, status=status.HTTP_400_BAD_REQUEST)
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return Response({"detail": "Lat/lon out of range."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            r = httpx.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers={"User-Agent": "PartBridge/1.0 (contact@partbridge.invalid)"},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            addr = data.get("address") or {}
            raw_zip = (addr.get("postcode") or "").strip()
            m = re.search(r"(\d{5})", raw_zip)
            if m:
                return Response({"zip": m.group(1)})
        except Exception:
            logger.exception("reverse_zip nominatim failed")
        return Response({"detail": "Could not resolve ZIP."}, status=status.HTTP_404_NOT_FOUND)


class PublicCarOptionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Vehicle.objects.filter(year__isnull=False).exclude(make="").exclude(model="")
        years = list(qs.values_list("year", flat=True).distinct().order_by("-year")[:40])
        makes = list(qs.values_list("make", flat=True).distinct().order_by("make")[:100])
        make = (request.query_params.get("make") or "").strip()
        models_qs = qs
        if make:
            models_qs = models_qs.filter(make__iexact=make)
        models = list(models_qs.values_list("model", flat=True).distinct().order_by("model")[:120])
        return Response({"years": years, "makes": makes, "models": models})


class PublicCarAssistView(APIView):
    """
    POST /browse/cars/assist/

    Requires at least one of: buyer_make, part_need.

    If part_need is given:
      - Ask Perplexity for compatible donor vehicle ranges + normalized part label.
      - Return buy_now parts matching the part name on matching donor vehicles.

    Always returns:
      - listings: buy_now VehiclePart rows (empty when no part_need)
      - potential_cars: donor vehicle cards matching buyer Y/M/M + compatible ranges
      - compatible_vehicles: AI-derived fitment ranges (so the frontend never calls Perplexity)

    Listings are capped at _LISTINGS_SERIALIZE_MAX for JSON payload size; `listings_total_count`
    is the full queryset count before that cap (so the UI can show "N of M").
    """

    permission_classes = [AllowAny]
    # Serialized part rows per assist response (was 48 — too small vs real inventory).
    _LISTINGS_SERIALIZE_MAX = 500

    def post(self, request):
        serializer = PublicCarAssistInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vd = serializer.validated_data
        part_need = (vd.get("part_need") or "").strip()
        buyer_make = (vd.get("buyer_make") or "").strip()
        buyer_model = (vd.get("buyer_model") or "").strip()
        buyer_year = vd.get("buyer_year")
        buyer_zip = (vd.get("buyer_zip") or "").strip()
        category_slug = (vd.get("category") or "").strip()

        if part_need:
            search_mode = "custom_part"
        elif category_slug:
            search_mode = "category_browse"
        else:
            search_mode = "cars_only"

        try:
            # ------------------------------------------------------------------
            # Step 1 — If part_need, refine phrase + ask Perplexity for donor ranges
            # ------------------------------------------------------------------
            compatible_vehicles = []
            normalized_part = part_need
            suggested_category = ""
            ai_source = "none"
            part_refinement = None


            if part_need:
                part_refinement = {
                    "original": part_need,
                    "refined": part_need,
                    "note":  "",
                    "source":  "fallback",
                }
                refined_for_ai = (part_refinement.get("refined_query") or part_need).strip() or part_need
                ai = suggest_cars_and_part_phrase(
                    buyer_year=buyer_year,
                    buyer_make=buyer_make,
                    buyer_model=buyer_model,
                    part_query=refined_for_ai,
                )
                compatible_vehicles = ai.get("candidate_vehicles") or []
                normalized_part = refined_for_ai
                suggested_category = ai.get("suggested_category_name") or ""
                ai_source = ai.get("source") or "fallback"

            # ------------------------------------------------------------------
            # Step 2 — Build listings (buy_now + message_only, see public_listable_*)
            # ------------------------------------------------------------------
            base_qs = public_listable_vehicle_parts_queryset()
            if category_slug:
                base_qs = base_qs.filter(part_family__category__slug=category_slug)

            if part_need:
                parts_qs = base_qs.filter(
                    _part_search_term_q(normalized_part, part_need, part_need)
                )
            else:
                parts_qs = base_qs

            # Vehicle filter: buyer's car (±5 yr) OR compatible donor ranges from AI
            vehicle_q = Q()
            if buyer_make:
                bq = Q(vehicle__make__icontains=buyer_make)
                if buyer_model:
                    bq &= Q(vehicle__model__icontains=buyer_model)
                if buyer_year is not None:
                    bq &= Q(
                        vehicle__year__gte=buyer_year - 5,
                        vehicle__year__lte=buyer_year + 5,
                    )
                vehicle_q |= bq
            compat_q = _compat_candidates_vehicle_q(compatible_vehicles)
            if compat_q:
                vehicle_q |= compat_q
            if vehicle_q:
                parts_qs = parts_qs.filter(vehicle_q)

            parts_qs = parts_qs.order_by("-updated_at")
            listings_total_count = parts_qs.count()
            parts_limited = parts_qs[: self._LISTINGS_SERIALIZE_MAX]
            listings_payload = PublicVehiclePartSerializer(
                list(parts_limited),
                many=True,
                context={"request": request, "buyer_zip": buyer_zip},
            ).data
            listings_returned = len(listings_payload)

            # ------------------------------------------------------------------
            # Step 3 — Build donor vehicle cards
            # ------------------------------------------------------------------
            donor_q = Q()
            if buyer_make:
                dq = Q(vehicle__make__icontains=buyer_make)
                if buyer_model:
                    dq &= Q(vehicle__model__icontains=buyer_model)
                if buyer_year is not None:
                    dq &= Q(
                        vehicle__year__gte=buyer_year - 5,
                        vehicle__year__lte=buyer_year + 5,
                    )
                donor_q |= dq

            compat_q = _compat_candidates_vehicle_q(compatible_vehicles)
            if compat_q:
                donor_q |= compat_q

            if donor_q:
                donor_parts_qs = public_listable_vehicle_parts_queryset().filter(donor_q)
                if category_slug:
                    donor_parts_qs = donor_parts_qs.filter(
                        part_family__category__slug=category_slug
                    )
            else:
                donor_parts_qs = public_listable_vehicle_parts_queryset().none()

            potential_cars_payload = _build_potential_donor_payloads(donor_parts_qs, buyer_zip, request)

            # ------------------------------------------------------------------
            # Step 4 — Return
            # ------------------------------------------------------------------
            logger.info(
                "browse_cars_assist ok part_need=%r normalized=%r listings_total=%s listings_returned=%s cap=%s cars=%s ai_source=%s",
                part_need,
                normalized_part,
                listings_total_count,
                listings_returned,
                self._LISTINGS_SERIALIZE_MAX,
                len(potential_cars_payload),
                ai_source,
            )
            logger.debug("browse_cars_assist compatible_vehicles=%s", compatible_vehicles)
            return Response(
                {
                    "search_mode": search_mode,
                    "listings": listings_payload,
                    "listings_count": listings_returned,
                    "listings_total_count": listings_total_count,
                    "potential_cars": potential_cars_payload,
                    "compatible_vehicles": compatible_vehicles,
                    "normalized_part_query": normalized_part,
                    "suggested_category_name": suggested_category,
                    "ai_source": ai_source,
                    "part_refinement": part_refinement,
                }
            )

        except Exception:
            logger.exception(
                "browse_cars_assist failed buyer_year=%s buyer_make=%s part_need_len=%s",
                buyer_year,
                buyer_make,
                len(part_need or ""),
            )

            return Response(
                {"detail": "Could not process search right now."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PublicBrowseVehicleDetailView(APIView):
    """
    GET — single donor vehicle visible in public browse: photos, specs, seller summary,
    and all public listable parts for this VIN row.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        from orders.models import Order

        try:
            vehicle = (
                Vehicle.objects.select_related("owner")
                .prefetch_related(
                    Prefetch("photos", queryset=VehiclePhoto.objects.order_by("sort_order", "id")),
                )
                .get(pk=pk)
            )
        except Vehicle.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        base_parts_qs = public_listable_vehicle_parts_queryset().filter(vehicle_id=pk)
        if not base_parts_qs.exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        buyer_zip = request.query_params.get("buyer_zip", "").strip()
        buy_now_only = request.query_params.get("buy_now_only", "").lower() in ("1", "true", "yes")
        q_raw = (request.query_params.get("q") or "").strip()

        now = timezone.now()
        purchasable_buy_now_q = Q(
            listing_state=VehiclePart.ListingState.BUY_NOW,
            price__isnull=False,
            price__gt=0,
        ) & (Q(buy_now_expires_at__isnull=True) | Q(buy_now_expires_at__gte=now))

        parts_qs = base_parts_qs.filter(purchasable_buy_now_q) if buy_now_only else base_parts_qs

        if q_raw:
            parts_qs = parts_qs.filter(
                Q(label__icontains=q_raw)
                | Q(description__icontains=q_raw)
                | Q(part_family__name__icontains=q_raw)
            )

        total_count = parts_qs.count()
        try:
            page = int(request.query_params.get("page", "1"))
        except (TypeError, ValueError):
            page = 1
        page = max(1, page)
        try:
            page_size = int(request.query_params.get("page_size", "120"))
        except (TypeError, ValueError):
            page_size = 120
        page_size = max(1, min(page_size, 120))
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        start = (page - 1) * page_size
        parts_list = list(
            parts_qs.order_by(
                "part_family__category__sort_order",
                "part_family__name",
                "variant_key",
            )[start : start + page_size]
        )
        parts_data = PublicVehiclePartSerializer(
            parts_list,
            many=True,
            context={"request": request, "buyer_zip": buyer_zip},
        ).data

        owner = vehicle.owner
        display_name = (owner.get_full_name() or "").strip() or owner.username
        completed = Order.objects.filter(seller_id=owner.id, state=Order.State.DELIVERED).count()
        gallery = _vehicle_public_photos_payload(vehicle, request, max_photos=24)

        vdata = {
            "id": vehicle.id,
            "year": vehicle.year,
            "make": vehicle.make,
            "model": vehicle.model,
            "trim": (vehicle.trim or "").strip(),
            "engine": (vehicle.engine or "").strip(),
            "transmission": (vehicle.transmission or "").strip(),
            "drivetrain": (vehicle.drivetrain or "").strip(),
            "body_style": (vehicle.body_style or "").strip(),
            "color": (vehicle.color or "").strip(),
            "vin_masked": (vehicle.vin[-4:] if vehicle.vin and len(vehicle.vin) >= 4 else None),
            "location_state": (vehicle.location_state or "").strip(),
            "location_zip_masked": mask_zip(vehicle.location_zip),
            "has_damage": vehicle.has_damage,
            "damage_items": vehicle.damage_items or [],
            "odometer_miles": vehicle.odometer_miles,
            "mileage_unavailable": bool(vehicle.mileage_unavailable),
            "primary_photo_url": gallery[0]["url"] if gallery else None,
            "photo_urls": gallery,
            "seller": {
                "id": owner.id,
                "display_name": display_name,
                "member_since": owner.date_joined.isoformat() if owner.date_joined else None,
                "completed_sales": completed,
                "rating_avg": None,
                "rating_count": 0,
                "trust_note": (
                    f"{completed} completed sales on PartBridge"
                    if completed
                    else "New seller — no completed sales yet"
                ),
            },
        }

        # Parts that are no longer purchasable — shown for buyer reference
        inactive_states = [
            VehiclePart.ListingState.SOLD,
            VehiclePart.ListingState.UNAVAILABLE,
            VehiclePart.ListingState.SOLD_ELSEWHERE,
        ]
        inactive_qs = (
            VehiclePart.objects.filter(vehicle_id=pk, listing_state__in=inactive_states, is_removed=False)
            .select_related("part_family")
            .order_by("part_family__name", "label")[:60]
        )
        inactive_data = [
            {"id": p.id, "label": p.label, "state": p.listing_state}
            for p in inactive_qs
        ]

        payload = {
            "vehicle": vdata,
            "parts": parts_data,
            "parts_count": total_count,
            "parts_page": page,
            "parts_page_size": page_size,
            "parts_total_pages": total_pages,
            "inactive_parts": inactive_data,
        }
        if buy_now_only:
            other_qs = (
                base_parts_qs.exclude(purchasable_buy_now_q)
                .select_related("part_family")
                .order_by("part_family__name", "label")[:400]
            )
            payload["other_parts"] = [
                {
                    "id": p.id,
                    "label": p.label,
                    "listing_state": p.listing_state,
                    "listing_state_effective": p.effective_listing_state,
                }
                for p in other_qs
            ]

        return Response(payload)


class PublicPartDetailView(generics.RetrieveAPIView):
    """GET single public listing (shareable)."""

    permission_classes = [AllowAny]
    serializer_class = PublicVehiclePartSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return public_listable_vehicle_parts_queryset()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["buyer_zip"] = self.request.query_params.get("buyer_zip", "").strip()
        return ctx


class PartOptionSetView(APIView):
    """GET options for a specific vehicle part (for buyer and seller UIs)."""

    permission_classes = [AllowAny]

    def get(self, request, vehicle_part_id):
        try:
            part = VehiclePart.objects.select_related("part_family", "vehicle").get(pk=vehicle_part_id)
        except VehiclePart.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            option_set = PartOptionSet.objects.prefetch_related("options__compatibilities").get(
                vehicle=part.vehicle,
                part_family=part.part_family,
            )
        except PartOptionSet.DoesNotExist:
            return Response({"detail": "No options processed yet.", "status": "pending"})
        return Response(PartOptionSetSerializer(option_set).data)


class TriggerPartPipelineView(APIView):
    """POST — manually trigger the listing pipeline for a part (seller action)."""

    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def post(self, request, vehicle_id, part_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, owner=request.user)
        part = get_object_or_404(VehiclePart, pk=part_id, vehicle=vehicle)
        from .tasks import run_part_listing_pipeline
        run_part_listing_pipeline.apply_async(args=[part.id])
        VehiclePart.objects.filter(pk=part.id).update(
            listing_pipeline_status="processing",
            listing_pipeline_started_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response({"detail": "Pipeline queued.", "vehicle_part_id": part.id})


class BrowseErrorReportView(APIView):
    """POST — buyer submits a search error report."""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = BrowseErrorReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reporter = request.user if request.user.is_authenticated else None
        report = ser.save(reporter=reporter)
        # Email admin
        try:
            from django.conf import settings as djsettings
            from django.core.mail import send_mail
            admin_email = (getattr(djsettings, "ORDER_ADMIN_EMAIL", "") or "").strip()
            if admin_email:
                part_label = ""
                if report.vehicle_part_id:
                    try:
                        part_label = VehiclePart.objects.get(pk=report.vehicle_part_id).label
                    except Exception:
                        pass
                send_mail(
                    subject=f"Browse error report #{report.id} — Partbridge",
                    message=(
                        f"A buyer reported an issue:\n\n"
                        f"Part: {part_label or 'N/A'}\n"
                        f"Search query: {report.search_query}\n"
                        f"Issue: {report.issue_description}\n"
                        f"Contact: {report.contact_email or 'N/A'}\n"
                        f"Reporter: {reporter.email if reporter else 'Anonymous'}\n"
                    ),
                    from_email=djsettings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True,
                )
        except Exception:
            pass
        return Response({"detail": "Report submitted. Thank you!", "id": report.id}, status=status.HTTP_201_CREATED)


class CompatibleVehiclesSearchView(APIView):
    """
    GET /browse/parts/compatible/?part_family=<id>&option_key=<key>&year=&make=&model=
    Search for parts on compatible vehicles using the PartCompatibility table.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        from django.db.models import Q as DQ

        part_family_id = request.query_params.get("part_family")
        option_key = request.query_params.get("option_key", "")
        buyer_year = request.query_params.get("year")
        buyer_make = (request.query_params.get("make") or "").strip()
        buyer_model = (request.query_params.get("model") or "").strip()
        buyer_zip = (request.query_params.get("buyer_zip") or "").strip()

        if not part_family_id:
            return Response({"detail": "part_family is required."}, status=400)

        # Find options for this part family across all vehicles
        option_qs = PartOption.objects.filter(
            option_set__part_family_id=part_family_id,
            is_applicable=True,
        )
        if option_key:
            option_qs = option_qs.filter(option_key=option_key)

        # Get compatible vehicle specs from PartCompatibility
        compat_qs = PartCompatibility.objects.filter(option__in=option_qs)

        # Build Q for compatible vehicles
        compat_vehicle_q = DQ()
        for c in compat_qs[:50]:
            cq = DQ(vehicle__make__icontains=c.make, vehicle__model__icontains=c.model)
            cq &= DQ(vehicle__year__gte=c.year_range_start, vehicle__year__lte=c.year_range_end)
            compat_vehicle_q |= cq

        # Also include the buyer's own make/model range
        buyer_q = DQ()
        if buyer_make:
            bq = DQ(vehicle__make__icontains=buyer_make)
            if buyer_model:
                bq &= DQ(vehicle__model__icontains=buyer_model)
            if buyer_year:
                try:
                    yi = int(buyer_year)
                    bq &= DQ(vehicle__year__gte=yi - 5, vehicle__year__lte=yi + 5)
                except (TypeError, ValueError):
                    pass
            buyer_q |= bq

        combined_q = compat_vehicle_q | buyer_q
        if not combined_q:
            parts_qs = public_listable_vehicle_parts_queryset().filter(part_family_id=part_family_id)
        else:
            parts_qs = public_listable_vehicle_parts_queryset().filter(
                part_family_id=part_family_id
            ).filter(combined_q)

        parts_qs = parts_qs.order_by("-updated_at")
        total = parts_qs.count()
        parts_list = list(parts_qs[:48])
        data = PublicVehiclePartSerializer(
            parts_list,
            many=True,
            context={"request": request, "buyer_zip": buyer_zip},
        ).data
        return Response({"count": total, "results": data})
