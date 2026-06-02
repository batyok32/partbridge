from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser

from .models import Category, Item, Variation
from .serializers import CategorySerializer, ItemListSerializer, ItemSerializer, VariationSerializer


class CategoryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related("children")


class ItemListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemListSerializer

    def get_queryset(self):
        qs = Item.objects.filter(status=Item.Status.ACTIVE).select_related("category").prefetch_related("photos")
        params = self.request.query_params
        if cat := params.get("category"):
            qs = qs.filter(category__slug=cat)
        if vehicle_id := params.get("vehicle"):
            qs = qs.filter(vehicle_id=vehicle_id)
        if generation_id := params.get("generation"):
            qs = qs.filter(compatibilities__generation_id=generation_id).distinct()
        return qs.order_by("-created_at")


class ItemDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ItemSerializer

    def get_queryset(self):
        return Item.objects.select_related("category").prefetch_related("photos", "options")


class VariationListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = VariationSerializer

    def get_queryset(self):
        qs = Variation.objects.all()
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(review_status=status)
        return qs
