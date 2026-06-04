from django.db.models import Avg, Count, Q
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Make

from .models import Category, Item, Option, OptionCategory, OptionValue, PartNumber, Variation
from .models import normalize_part_number
from .querysets import active_items_qs, filter_items_by_car
from .serializers import (
    CategorySerializer,
    CategoryWithCountSerializer,
    ItemListSerializer,
    ItemSerializer,
    OptionCategorySerializer,
    VariationSerializer,
)


def _parse_car_params(params):
    generation_id = params.get("generation") or params.get("generation_id")
    modification_id = params.get("modification") or params.get("modification_id")
    compatible_only = params.get("compatible_only", "").lower() in ("1", "true", "yes")
    return generation_id, modification_id, compatible_only


def _apply_item_filters(qs, params):
    if cat := params.get("category"):
        slugs = [s.strip() for s in cat.split(",") if s.strip()]
        if len(slugs) == 1:
            # include items in this category AND items in its child categories
            qs = qs.filter(
                Q(category__slug=slugs[0]) | Q(category__parent__slug=slugs[0])
            )
        elif slugs:
            qs = qs.filter(
                Q(category__slug__in=slugs) | Q(category__parent__slug__in=slugs)
            )
   
    compatible_only = params.get("compatible_only") in ("1", "true", "True")
    if generation_id := params.get("generation") or params.get("generation_id"):
        if not compatible_only:
            gen_slug = params.get("generation_slug")
            if gen_slug and not str(generation_id).isdigit():
                qs = qs.filter(vehicle__generation__name__iexact=generation_id)
            elif str(generation_id).isdigit():
                qs = qs.filter(vehicle__generation_id=generation_id)

    if year := params.get("year"):
        if not compatible_only:
            qs = qs.filter(vehicle__year=year)

    
    if vehicle_id := params.get("vehicle"):
        qs = qs.filter(vehicle_id=vehicle_id)
    if make_id := params.get("make"):
        qs = qs.filter(vehicle__generation__make_id=make_id)
    if model_id := params.get("model"):
        qs = qs.filter(vehicle__generation__car_model_id=model_id)
   
    if modification_id := params.get("modification") or params.get("modification_id"):
        if str(modification_id).isdigit():
            qs = qs.filter(vehicle__modification_id=modification_id)
    if part_number := params.get("part_number"):
        normalized = normalize_part_number(part_number)
        if normalized:
            alt_item_ids = PartNumber.objects.filter(
                number_normalized__icontains=normalized
            ).values_list("item_id", flat=True)
            qs = qs.filter(
                Q(oem_part_number_normalized__icontains=normalized) | Q(id__in=alt_item_ids)
            )
    if condition := params.get("condition"):
        conditions = [c.strip() for c in condition.split(",") if c.strip()]
        if len(conditions) == 1:
            qs = qs.filter(condition=conditions[0])
        elif conditions:
            qs = qs.filter(condition__in=conditions)
    if price_min := params.get("price_min"):
        qs = qs.filter(price__gte=price_min)
    if price_max := params.get("price_max"):
        qs = qs.filter(price__lte=price_max)
    if pickup_state := params.get("pickup_state"):
        qs = qs.filter(vehicle__seller_state__iexact=pickup_state)

    for key, val in params.items():
        if key.startswith("option_") and val:
            cat_type = key[7:]
            qs = qs.filter(
                options__option_category__type=cat_type,
                options__value__iexact=val,
            ).distinct()

    generation_id, modification_id, compatible_only = _parse_car_params(params)
    qs = filter_items_by_car(
        qs,
        generation_id=generation_id if str(generation_id or "").isdigit() else None,
        modification_id=modification_id if str(modification_id or "").isdigit() else None,
        compatible_only=compatible_only,
    )
    return qs, generation_id, modification_id


def _apply_sort(qs, params, *, generation_id=None):
    sort = params.get("sort", "newest")
    if sort == "price_asc":
        return qs.order_by("price", "-created_at")
    if sort == "price_desc":
        return qs.order_by("-price", "-created_at")
    if sort == "best_match" and generation_id and str(generation_id).isdigit():
        from django.db.models import Max

        return qs.annotate(
            best_compat_score=Max(
                "compatibilities__confidence_score",
                filter=Q(compatibilities__generation_id=generation_id),
            )
        ).order_by("-best_compat_score", "-created_at")
    return qs.order_by("-created_at")


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        qs = Category.objects.all()
        if self.request.query_params.get("featured") in ("1", "true", "yes"):
            qs = qs.filter(parent__isnull=True)
        if parent := self.request.query_params.get("parent"):
            if parent == "null":
                qs = qs.filter(parent__isnull=True)
            else:
                qs = qs.filter(parent_id=parent)
        return qs.order_by("sort_order", "name")

    def get_serializer_class(self):
        if self.request.query_params.get("with_counts"):
            return CategoryWithCountSerializer
        return CategorySerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        generation_id, modification_id, compatible_only = _parse_car_params(self.request.query_params)
        gen = generation_id if str(generation_id or "").isdigit() else None
        ctx["car_generation_id"] = gen
        ctx["car_modification_id"] = modification_id if str(modification_id or "").isdigit() else None
        ctx["compatible_only"] = compatible_only or bool(gen)
        return ctx


class ItemListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemListSerializer

    def get_queryset(self):
        qs = active_items_qs()
        print("ACTIVE ITEMS QS:", qs.query)
        print("COUNT BEFORE FILTERS:", qs.count())
        print("QUERY PARAMS:", self.request.query_params)
        qs, generation_id, modification_id = _apply_item_filters(qs, self.request.query_params)
        print("FILTERED QS:", qs.query)
        print("COUNT AFTER FILTERS:", qs.count())
        return _apply_sort(qs, self.request.query_params, generation_id=generation_id)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        generation_id, modification_id, _ = _parse_car_params(self.request.query_params)
        ctx["car_generation_id"] = generation_id if str(generation_id or "").isdigit() else None
        ctx["car_modification_id"] = modification_id if str(modification_id or "").isdigit() else None
        return ctx

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        count = queryset.count()
        limit = request.query_params.get("limit")
        offset = request.query_params.get("offset")
        if limit and str(limit).isdigit():
            limit_int = int(limit)
            offset_int = int(offset) if offset and str(offset).isdigit() else 0
            queryset = queryset[offset_int:offset_int + limit_int]
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": count, "results": serializer.data})


class OptionFiltersView(APIView):
    """
    Returns surviving option values grouped by OptionCategory for items
    matching the given category + car filters. Powers the dynamic spec
    filter panel on the search page.

    GET /api/parts/option-filters/?category=headlights&generation=5
    """
    permission_classes = [AllowAny]

    def get(self, request):
        params = request.query_params
        qs = active_items_qs()
        if cat := params.get("category"):
            qs = qs.filter(category__slug=cat)
        if make_id := params.get("make"):
            qs = qs.filter(vehicle__generation__make_id=make_id)
        generation_id, modification_id, _ = _parse_car_params(params)
        if generation_id and str(generation_id).isdigit():
            qs = filter_items_by_car(
                qs,
                generation_id=generation_id,
                modification_id=modification_id if str(modification_id or "").isdigit() else None,
                compatible_only=True,
            )

        item_ids = qs.values_list("id", flat=True)
        surviving = (
            Option.objects.filter(item__in=item_ids)
            .select_related("option_category")
            .values("option_category__type", "option_category__name", "option_category__is_required", "value")
            .distinct()
            .order_by("-option_category__is_required", "option_category__type", "value")
        )

        groups = {}
        for row in surviving:
            t = row["option_category__type"]
            if t not in groups:
                groups[t] = {
                    "type": t,
                    "name": row["option_category__name"],
                    "is_required": row["option_category__is_required"],
                    "values": [],
                }
            if row["value"] not in groups[t]["values"]:
                groups[t]["values"].append(row["value"])

        return Response(list(groups.values()))


class ItemDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemSerializer

    def get_queryset(self):
        return (
            Item.objects.select_related(
                "category",
                "vehicle__generation__car_model__make",
                "vehicle__modification",
                "vehicle__seller",
            )
            .prefetch_related(
                "photos",
                "options__option_category",
                "alt_part_numbers",
                "vehicle__photos",
                "compatibilities__generation__car_model__make",
            )
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        params = self.request.query_params
        gen_id = params.get("generation") or params.get("generation_id")
        mod_id = params.get("modification") or params.get("modification_id")
        ctx["car_generation_id"] = gen_id if str(gen_id or "").isdigit() else None
        ctx["car_modification_id"] = mod_id if str(mod_id or "").isdigit() else None
        return ctx


class HomeFeaturedCategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        generation_id, modification_id, compatible_only = _parse_car_params(request.query_params)
        gen_id = generation_id if str(generation_id or "").isdigit() else None
        categories = Category.objects.filter(parent__isnull=True).order_by("sort_order", "name")[:12]
        ctx = {
            "car_generation_id": gen_id,
            "car_modification_id": modification_id if str(modification_id or "").isdigit() else None,
            "compatible_only": compatible_only,
        }
        serializer = CategoryWithCountSerializer(categories, many=True, context=ctx)
        return Response(serializer.data)


class HomeRecentItemsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = active_items_qs()
        generation_id, modification_id, compatible_only = _parse_car_params(request.query_params)
        gen_id = generation_id if str(generation_id or "").isdigit() else None
        if compatible_only and gen_id:
            qs = filter_items_by_car(
                qs,
                generation_id=gen_id,
                modification_id=modification_id if str(modification_id or "").isdigit() else None,
                compatible_only=True,
            )
        limit = int(request.query_params.get("limit", 12))
        items = qs.order_by("-created_at")[:limit]
        ctx = {
            "car_generation_id": gen_id,
            "car_modification_id": modification_id if str(modification_id or "").isdigit() else None,
        }
        serializer = ItemListSerializer(items, many=True, context=ctx)
        return Response(serializer.data)


class OptionCategoryListView(generics.ListAPIView):
    """
    GET /api/parts/option-categories/?category=<slug>
    Returns OptionCategories with their predefined values for a given part category.
    Used by the seller listing form to build attribute dropdowns.
    """
    permission_classes = [AllowAny]
    serializer_class = OptionCategorySerializer

    def get_queryset(self):
        qs = OptionCategory.objects.prefetch_related("predefined_values")
        if slug := self.request.query_params.get("category"):
            qs = qs.filter(category__slug=slug)
        return qs


class VariationListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = VariationSerializer

    def get_queryset(self):
        qs = Variation.objects.all()
        if status := self.request.query_params.get("status"):
            qs = qs.filter(review_status=status)
        return qs


class PartNumberAutocompleteView(APIView):
    """
    GET /api/parts/part-number-autocomplete/?q=<partial>
    Returns up to 10 matching part numbers (OEM + alternates) for autocomplete.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])

        normalized = normalize_part_number(q)
        if not normalized:
            return Response([])

        results = []
        seen = set()

        oem_hits = (
            Item.objects.filter(
                oem_part_number_normalized__icontains=normalized,
                status=Item.Status.ACTIVE,
            )
            .exclude(oem_part_number="")
            .values("oem_part_number", "oem_part_number_normalized")
            .distinct()[:10]
        )
        for row in oem_hits:
            n = row["oem_part_number_normalized"]
            if n not in seen:
                seen.add(n)
                results.append({
                    "number": row["oem_part_number"],
                    "normalized": n,
                    "type": "oem",
                    "label": "OEM",
                })

        alt_hits = (
            PartNumber.objects.filter(
                number_normalized__icontains=normalized,
                item__status=Item.Status.ACTIVE,
            )
            .values("number_raw", "number_normalized", "brand")
            .distinct()[:10]
        )
        for row in alt_hits:
            n = row["number_normalized"]
            if n not in seen:
                seen.add(n)
                results.append({
                    "number": row["number_raw"],
                    "normalized": n,
                    "type": "cross_ref",
                    "label": row["brand"] or "Cross-ref",
                })

        return Response(results[:10])
