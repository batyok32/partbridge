from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Vehicle, VehiclePhoto
from .nhtsa import decode_vin
from .serializers import (
    VehicleCreateUpdateSerializer,
    VehicleDetailSerializer,
    VehicleListSerializer,
    VehiclePhotoSerializer,
)


class VehicleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VehicleCreateUpdateSerializer
        return VehicleListSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(seller=self.request.user).prefetch_related("photos").select_related("generation__car_model__make", "modification")

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return VehicleCreateUpdateSerializer
        return VehicleDetailSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(seller=self.request.user).prefetch_related("photos").select_related("generation__car_model__make", "modification")


class VehiclePhotoListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        photos = vehicle.photos.all()
        return Response(VehiclePhotoSerializer(photos, many=True).data)

    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        ser = VehiclePhotoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(vehicle=vehicle)
        return Response(ser.data, status=status.HTTP_201_CREATED)


class VehiclePhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, vehicle_id, photo_id):
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        photo = get_object_or_404(VehiclePhoto, pk=photo_id, vehicle=vehicle)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VinDecodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        vin = (request.data.get("vin") or "").strip().upper()
        if not vin:
            return Response({"detail": "Provide a vin field."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = decode_vin(vin)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class VehicleItemListView(APIView):
    """List / create Items for a seller-owned Vehicle."""
    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_id):
        from parts.models import Item
        from parts.serializers import ItemSerializer
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        items = Item.objects.filter(vehicle=vehicle).select_related("category").prefetch_related("photos", "options")
        return Response(ItemSerializer(items, many=True, context={"request": request}).data)

    def post(self, request, vehicle_id):
        from parts.models import Category, Item
        from parts.serializers import ItemSerializer
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        data = request.data

        category_id = data.get("category")
        if not category_id:
            return Response({"detail": "category is required."}, status=400)
        try:
            category = Category.objects.get(pk=category_id)
        except Category.DoesNotExist:
            return Response({"detail": "Category not found."}, status=400)

        title = (data.get("title") or "").strip()
        if not title:
            return Response({"detail": "title is required."}, status=400)

        price = data.get("price")
        if price is None:
            return Response({"detail": "price is required."}, status=400)

        item = Item(
            vehicle=vehicle,
            category=category,
            title=title,
            price=price,
            condition=data.get("condition", "good"),
            description=(data.get("description") or "").strip(),
            oem_part_number=(data.get("oem_part_number") or "").strip(),
            shipping_size=data.get("shipping_size") or category.shipping_size_default or "medium",
        )
        item.save()
        return Response(ItemSerializer(item, context={"request": request}).data, status=status.HTTP_201_CREATED)


class VehicleItemDetailView(APIView):
    """GET / PATCH / DELETE individual Item for a seller-owned vehicle."""
    permission_classes = [IsAuthenticated]

    _ALLOWED = {
        "title", "description", "price", "condition", "status",
        "shipping_size", "oem_part_number",
        "weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in",
    }

    def _get_item(self, request, vehicle_id, item_id):
        from parts.models import Item
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        return get_object_or_404(Item, pk=item_id, vehicle=vehicle)

    def get(self, request, vehicle_id, item_id):
        from parts.serializers import ItemSerializer
        item = self._get_item(request, vehicle_id, item_id)
        return Response(ItemSerializer(item, context={"request": request}).data)

    def patch(self, request, vehicle_id, item_id):
        from parts.models import Item
        from parts.serializers import ItemSerializer
        item = self._get_item(request, vehicle_id, item_id)

        data = {k: v for k, v in request.data.items() if k in self._ALLOWED}
        if not data:
            return Response({"detail": "No updatable fields provided."}, status=400)

        if "shipping_size" in data:
            valid = [c[0] for c in Item.ShippingSize.choices]
            if data["shipping_size"] not in valid:
                return Response({"detail": f"Invalid shipping_size. Choose from: {valid}"}, status=400)

        for field, value in data.items():
            setattr(item, field, value)

        fields_to_save = set(data.keys())
        # Dimension changes trigger shipping_size recompute inside Item.save()
        if fields_to_save & {"weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in"}:
            fields_to_save.add("shipping_size")
        # OEM number changes trigger normalization inside Item.save()
        if "oem_part_number" in fields_to_save:
            fields_to_save.add("oem_part_number_normalized")

        item.save(update_fields=list(fields_to_save))
        return Response(ItemSerializer(item, context={"request": request}).data)

    def delete(self, request, vehicle_id, item_id):
        item = self._get_item(request, vehicle_id, item_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleItemPhotoView(APIView):
    """Add / delete photos on a seller-owned item."""
    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_id, item_id):
        from parts.models import Item, ItemPhoto
        from parts.serializers import ItemPhotoSerializer
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        item = get_object_or_404(Item, pk=item_id, vehicle=vehicle)
        image = request.FILES.get("image")
        url = (request.data.get("url") or "").strip()
        if not image and not url:
            return Response({"detail": "Provide an image file or url."}, status=400)
        photo = ItemPhoto.objects.create(
            item=item,
            image=image or None,
            url=url,
            label=(request.data.get("label") or "").strip(),
            sort_order=item.photos.count(),
            is_primary=not item.photos.exists(),
        )
        if image and not photo.url:
            photo.refresh_from_db(fields=["url"])
        return Response(ItemPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)

    def delete(self, request, vehicle_id, item_id, photo_id):
        from parts.models import Item, ItemPhoto
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, seller=request.user)
        item = get_object_or_404(Item, pk=item_id, vehicle=vehicle)
        photo = get_object_or_404(ItemPhoto, pk=photo_id, item=item)
        was_primary = photo.is_primary
        photo.delete()
        if was_primary:
            next_photo = item.photos.first()
            if next_photo:
                next_photo.is_primary = True
                next_photo.save(update_fields=["is_primary"])
        return Response(status=status.HTTP_204_NO_CONTENT)
