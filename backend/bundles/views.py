from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Bundle, BundleCategory
from .serializers import BundleCategorySerializer, BundleSearchSerializer, BundleSerializer

_BUNDLE_QS = Bundle.objects.select_related("bundle_category").prefetch_related(
    "bundle_items__item__vehicle__generation__car_model__make",
    "bundle_items__item__photos",
)


class BundleCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleCategorySerializer
    queryset = BundleCategory.objects.all()


class BundleSearchView(generics.ListAPIView):
    """
    Search-ready bundle list — full item details, computed pricing, vehicle info.
    Filters: make, generation, category (part category slug), q (name keyword), type (assembly|discount).
    """
    permission_classes = [AllowAny]
    serializer_class = BundleSearchSerializer

    def get_queryset(self):
        qs = _BUNDLE_QS.filter(status=Bundle.Status.ACTIVE)
        params = self.request.query_params
        if make_id := params.get("make"):
            qs = qs.filter(bundle_items__item__vehicle__generation__make_id=make_id).distinct()
        if gen_id := params.get("generation"):
            qs = qs.filter(bundle_items__item__vehicle__generation_id=gen_id).distinct()
        if category := params.get("category"):
            qs = qs.filter(
                Q(bundle_items__item__category__slug=category) |
                Q(bundle_items__item__category__parent__slug=category)
            ).distinct()
        if q := params.get("q"):
            qs = qs.filter(name__icontains=q)
        if btype := params.get("type"):
            qs = qs.filter(bundle_category__type=btype)
        return qs.order_by("-created_at")


class BundleDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleSearchSerializer
    queryset = _BUNDLE_QS


class BundleListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleSerializer

    def get_queryset(self):
        qs = Bundle.objects.filter(status=Bundle.Status.ACTIVE).prefetch_related("bundle_items")
        if cat_id := self.request.query_params.get("category"):
            qs = qs.filter(bundle_category_id=cat_id)
        return qs
