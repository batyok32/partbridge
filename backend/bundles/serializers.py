from decimal import Decimal

from rest_framework import serializers

from parts.serializers import ItemListSerializer

from .models import Bundle, BundleCategory, BundleItem


def _abs(request, url):
    if not url:
        return None
    if request:
        return request.build_absolute_uri(url)
    return url


class BundleCategorySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = BundleCategory
        fields = ("id", "name", "type", "image_url")

    def get_image_url(self, obj):
        return _abs(self.context.get("request"), obj.image.url if obj.image else None)


class BundleItemInlineSerializer(serializers.ModelSerializer):
    item_detail = ItemListSerializer(source="item", read_only=True)

    class Meta:
        model = BundleItem
        fields = ("id", "item", "item_detail")


class BundleSearchSerializer(serializers.ModelSerializer):
    bundle_type = serializers.CharField(source="bundle_category.type", read_only=True)
    bundle_category_name = serializers.CharField(source="bundle_category.name", read_only=True)
    bundle_category_image_url = serializers.SerializerMethodField()
    items = BundleItemInlineSerializer(source="bundle_items", many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    primary_photo_url = serializers.SerializerMethodField()
    vehicle_year = serializers.SerializerMethodField()
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()
    vehicle_generation_label = serializers.SerializerMethodField()
    assembly_item_id = serializers.SerializerMethodField()

    class Meta:
        model = Bundle
        fields = (
            "id", "name", "discount_pct", "status",
            "bundle_type", "bundle_category_name", "bundle_category_image_url",
            "items", "item_count",
            "total_price", "discounted_price",
            "primary_photo_url",
            "vehicle_year", "vehicle_make", "vehicle_model", "vehicle_generation_label",
            "assembly_item_id",
            "created_at",
        )

    def get_assembly_item_id(self, obj):
        from parts.models import Item
        if obj.bundle_category.type == BundleCategory.BundleType.ASSEMBLY:
            return Item.objects.filter(assembly_bundle=obj).values_list("id", flat=True).first()
        return None

    def _bundle_items(self, obj):
        return obj.bundle_items.select_related(
            "item__vehicle__generation__car_model__make"
        ).prefetch_related("item__photos")

    def get_bundle_category_image_url(self, obj):
        bc = obj.bundle_category
        return _abs(self.context.get("request"), bc.image.url if bc and bc.image else None)

    def get_item_count(self, obj):
        return obj.bundle_items.count()

    def get_total_price(self, obj):
        total = sum(
            bi.item.price
            for bi in self._bundle_items(obj)
            if bi.item and bi.item.price is not None
        )
        return str(Decimal(total).quantize(Decimal("0.01")))

    def get_discounted_price(self, obj):
        total = Decimal(self.get_total_price(obj))
        if obj.discount_pct:
            total = total * (1 - obj.discount_pct / 100)
        return str(total.quantize(Decimal("0.01")))

    def get_primary_photo_url(self, obj):
        request = self.context.get("request")
        # First: try item photos from bundle items
        for bi in self._bundle_items(obj):
            if not bi.item:
                continue
            photo = bi.item.photos.filter(is_primary=True).first() or bi.item.photos.first()
            if photo and photo.url:
                return _abs(request, photo.url)
        # Fallback: bundle category image
        bc = obj.bundle_category
        if bc and bc.image:
            return _abs(request, bc.image.url)
        return None

    def _first_vehicle(self, obj):
        bi = self._bundle_items(obj).first()
        return bi.item.vehicle if bi and bi.item else None

    def get_vehicle_year(self, obj):
        v = self._first_vehicle(obj)
        return v.year if v else None

    def get_vehicle_make(self, obj):
        v = self._first_vehicle(obj)
        return v.generation.car_model.make.name if v and v.generation else ""

    def get_vehicle_model(self, obj):
        v = self._first_vehicle(obj)
        return v.generation.car_model.name if v and v.generation else ""

    def get_vehicle_generation_label(self, obj):
        v = self._first_vehicle(obj)
        if v and v.generation:
            g = v.generation
            codes = g.chassis_codes or []
            code = codes[0] if codes else (g.name or "")
            start = g.production_start.year if g.production_start else ""
            end = g.production_end.year if g.production_end else "present"
            return f"{code} ({start}–{end})" if code and start else g.name or ""
        return ""


class BundleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BundleItem
        fields = ("id", "bundle", "item")


class BundleSerializer(serializers.ModelSerializer):
    bundle_items = BundleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Bundle
        fields = ("id", "bundle_category", "name", "discount_pct", "status", "bundle_items", "created_at")
