from django.db.models import Q
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


class BrowseVehicleDetailView(APIView):
    """Public endpoint for the browse/vehicles/[id] frontend page."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        from parts.models import Item
        from parts.serializers import ItemListSerializer

        vehicle = get_object_or_404(
            Vehicle.objects.select_related(
                "generation__car_model__make", "generation__car_model", "modification"
            ).prefetch_related("photos"),
            pk=pk,
        )

        items_qs = (
            Item.objects.filter(
                vehicle=vehicle,
                status="active",
                vehicle__seller__seller_applications__status="approved",
            )
            .select_related("category", "vehicle__generation__car_model__make", "vehicle__seller")
            .prefetch_related("photos", "options", "alt_part_numbers")
        )

        q = (request.query_params.get("q") or "").strip()
        if q:
            items_qs = items_qs.filter(
                Q(title__icontains=q)
                | Q(category__name__icontains=q)
                | Q(oem_part_number__icontains=q)
            )

        buy_now_only = request.query_params.get("buy_now_only") == "1"
        inactive_items = Item.objects.filter(vehicle=vehicle).exclude(status="active") if not q else Item.objects.none()

        page_size = min(int(request.query_params.get("page_size") or 20), 120)
        page = max(1, int(request.query_params.get("page") or 1))
        total_count = items_qs.count()

        if total_count == 0 and not q:
            return Response({"detail": "No listable parts."}, status=status.HTTP_404_NOT_FOUND)

        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        page_items = items_qs[offset: offset + page_size]

        ctx = {"request": request}
        serialized_parts = ItemListSerializer(page_items, many=True, context=ctx).data

        def to_browse_part(d):
            return {
                **d,
                "label": d.get("category_name") or d.get("title") or "",
                "listing_state": "buy_now" if d.get("status") == "active" else d.get("status", ""),
                "listing_state_effective": "buy_now" if d.get("status") == "active" else d.get("status", ""),
                "condition_draft": d.get("condition", ""),
                "photo_urls": [{"url": u} for u in (d.get("photo_urls") or [])],
                "primary_photo_url": (d.get("photo_urls") or [None])[0],
                "vehicle_id": vehicle.id,
                "part_family": {"category": {"illustration_key": None}},
            }

        parts = [to_browse_part(d) for d in serialized_parts]
        other_parts = [to_browse_part(d) for d in ItemListSerializer(
            inactive_items[:50], many=True, context=ctx
        ).data] if not buy_now_only else []

        request_obj = request._request if hasattr(request, "_request") else request
        def abs_url(path):
            if not path:
                return None
            if path.startswith("http"):
                return path
            return request.build_absolute_uri(path)

        photo_urls = []
        for photo in vehicle.photos.order_by("sort_order"):
            url = None
            if photo.image:
                url = abs_url(photo.image.url)
            if url:
                photo_urls.append({"url": url})

        make = ""
        model = ""
        gen_label = ""
        if vehicle.generation:
            make = vehicle.generation.car_model.make.name
            model = vehicle.generation.car_model.name
            codes = vehicle.generation.chassis_codes or []
            start = vehicle.generation.production_start.year if vehicle.generation.production_start else ""
            end = vehicle.generation.production_end.year if vehicle.generation.production_end else "present"
            gen_label = f"{codes[0]} ({start}–{end})" if codes and start else vehicle.generation.name or ""

        vehicle_data = {
            "id": vehicle.id,
            "year": vehicle.year,
            "make": make,
            "model": model,
            "generation_label": gen_label,
            "mileage": vehicle.mileage,
            "condition": vehicle.condition,
            "seller_zip": vehicle.seller_zip,
            "photo_urls": photo_urls,
            "primary_photo_url": photo_urls[0]["url"] if photo_urls else None,
        }

        return Response({
            "vehicle": vehicle_data,
            "parts": parts,
            "other_parts": other_parts,
            "inactive_parts": [],
            "parts_count": total_count,
            "parts_total_pages": total_pages,
            "parts_page": page,
            "parts_page_size": page_size,
        })


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
