from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser

from .models import Category, Item, Variation
from .serializers import CategorySerializer, ItemListSerializer, ItemSerializer, VariationSerializer


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()


class ItemListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemListSerializer

    def get_queryset(self):
        qs = (
            Item.objects.filter(status=Item.Status.ACTIVE)
            .select_related("category", "vehicle__generation__car_model__make")
            .prefetch_related("photos")
        )
        params = self.request.query_params
        if cat := params.get("category"):
            qs = qs.filter(category__slug=cat)
        if vehicle_id := params.get("vehicle"):
            qs = qs.filter(vehicle_id=vehicle_id)
        if generation_id := params.get("generation"):
            qs = qs.filter(compatibilities__generation_id=generation_id).distinct()
        if make_id := params.get("make"):
            qs = qs.filter(vehicle__generation__make_id=make_id)
        if q := params.get("q"):
            qs = qs.filter(title__icontains=q)
        if condition := params.get("condition"):
            qs = qs.filter(condition=condition)
        if shipping_size := params.get("shipping_size"):
            qs = qs.filter(shipping_size=shipping_size)
        return qs.order_by("-created_at")


class ItemDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemSerializer

    def get_queryset(self):
        return (
            Item.objects.select_related("category", "vehicle__generation__car_model__make")
            .prefetch_related("photos", "options__option_category")
        )


class VariationListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = VariationSerializer

    def get_queryset(self):
        qs = Variation.objects.all()
        if status := self.request.query_params.get("status"):
            qs = qs.filter(review_status=status)
        return qs
