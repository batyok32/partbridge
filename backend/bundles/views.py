from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Bundle, BundleCategory
from .serializers import BundleCategorySerializer, BundleSerializer


class BundleCategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleCategorySerializer
    queryset = BundleCategory.objects.all()


class BundleListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleSerializer

    def get_queryset(self):
        qs = Bundle.objects.filter(status=Bundle.Status.ACTIVE).prefetch_related("bundle_items")
        cat_id = self.request.query_params.get("category")
        if cat_id:
            qs = qs.filter(bundle_category_id=cat_id)
        return qs


class BundleDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = BundleSerializer
    queryset = Bundle.objects.prefetch_related("bundle_items")
