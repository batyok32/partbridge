from django.db.models import Avg
from rest_framework import serializers

from orders.models import SellerReview

from .models import Category, Item, ItemCompatibility, ItemPhoto, Option, OptionCategory, OptionValue, PartNumber, Variation
from .querysets import active_items_qs, item_fitment_status


class PartNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartNumber
        fields = ("id", "number_raw", "number_normalized", "brand")


def _abs(request, url):
    """Return absolute URL; safe to call on already-absolute URLs."""
    if not url:
        return None
    if request:
        return request.build_absolute_uri(url)
    return url


class CategorySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "sort_order", "shipping_size_default", "image_url")

    def get_image_url(self, obj):
        return _abs(self.context.get("request"), obj.image.url if obj.image else None)


class CategoryWithCountSerializer(CategorySerializer):
    item_count = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ("item_count",)

    def get_item_count(self, obj):
        from django.db.models import Q as _Q
        qs = active_items_qs().filter(_Q(category=obj) | _Q(category__parent=obj))
        generation_id = self.context.get("car_generation_id")
        modification_id = self.context.get("car_modification_id")
        if generation_id and self.context.get("compatible_only"):
            from .querysets import filter_items_by_car
            qs = filter_items_by_car(
                qs,
                generation_id=generation_id,
                modification_id=modification_id,
                compatible_only=True,
            )
        return qs.count()


class ItemPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPhoto
        fields = ("id", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")


class OptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionValue
        fields = ("id", "value", "sort_order")


class OptionCategorySerializer(serializers.ModelSerializer):
    predefined_values = OptionValueSerializer(many=True, read_only=True)

    class Meta:
        model = OptionCategory
        fields = ("id", "name", "type", "is_required", "predefined_values")


class OptionSerializer(serializers.ModelSerializer):
    option_category_name = serializers.CharField(source="option_category.name", read_only=True)

    class Meta:
        model = Option
        fields = ("id", "option_category", "option_category_name", "value")


class ItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    category_image_url = serializers.SerializerMethodField()
    primary_photo_url = serializers.SerializerMethodField()
    vehicle_year = serializers.IntegerField(source="vehicle.year", read_only=True, allow_null=True)
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()
    vehicle_generation_name = serializers.SerializerMethodField()
    vehicle_generation_label = serializers.SerializerMethodField()
    vehicle_seller_zip = serializers.CharField(source="vehicle.seller_zip", read_only=True)
    fitment = serializers.SerializerMethodField()
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    seller_rating_avg = serializers.SerializerMethodField()
    seller_review_count = serializers.SerializerMethodField()
    alt_part_numbers = PartNumberSerializer(many=True, read_only=True)
    options = OptionSerializer(many=True, read_only=True)
    photo_urls = serializers.SerializerMethodField()
    vehicle_image_url = serializers.SerializerMethodField()
    is_assembly = serializers.SerializerMethodField()
    assembly_shipping_sizes = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id", "title", "price", "status", "condition", "shipping_size",
            "is_assembly", "assembly_shipping_sizes",
            "category", "category_name", "category_slug", "category_image_url",
            "oem_part_number", "oem_part_number_normalized", "alt_part_numbers",
            "options",
            "primary_photo_url", "photo_urls", "vehicle_image_url",
            "vehicle", "vehicle_year", "vehicle_make", "vehicle_model",
            "vehicle_generation_name", "vehicle_generation_label", "vehicle_seller_zip",
            "fitment", "seller_id", "seller_name", "seller_rating_avg", "seller_review_count",
            "created_at",
        )

    def get_is_assembly(self, obj):
        return obj.assembly_bundle_id is not None

    def get_assembly_shipping_sizes(self, obj):
        if not obj.assembly_bundle_id:
            return None
        try:
            return [bi.item.shipping_size for bi in obj.assembly_bundle.bundle_items.all() if bi.item]
        except Exception:
            return None

    def get_category_image_url(self, obj):
        cat = obj.category
        return _abs(self.context.get("request"), cat.image.url if cat and cat.image else None)

    def get_primary_photo_url(self, obj):
        request = self.context.get("request")
        photo = obj.photos.filter(is_primary=True).first() or obj.photos.first()
        if photo and photo.url:
            return _abs(request, photo.url)
        cat = obj.category
        if cat and cat.image:
            return _abs(request, cat.image.url)
        return None

    def get_photo_urls(self, obj):
        request = self.context.get("request")
        primary = obj.photos.filter(is_primary=True).first()
        others = obj.photos.exclude(pk=primary.pk) if primary else obj.photos.all()
        photos = ([primary] if primary else []) + list(others[:8])
        return [_abs(request, p.url) for p in photos if p and p.url]

    def get_vehicle_image_url(self, obj):
        if not obj.vehicle:
            return None
        request = self.context.get("request")
        photo = obj.vehicle.photos.order_by("sort_order").first()
        if not photo:
            return None
        if photo.image:
            return _abs(request, photo.image.url)
        return None

    def get_vehicle_make(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.make.name
        return ""

    def get_vehicle_model(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.name
        return ""

    def get_vehicle_generation_name(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.name or ""
        return ""

    def get_vehicle_generation_label(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            g = obj.vehicle.generation
            codes = g.chassis_codes or []
            code = codes[0] if codes else (g.name or "")
            start = g.production_start.year if g.production_start else ""
            end = g.production_end.year if g.production_end else "present"
            if code and start:
                return f"{code} ({start}–{end})"
            return g.name or ""
        return ""

    def get_fitment(self, obj):
        generation_id = self.context.get("car_generation_id")
        if not generation_id:
            return None
        return item_fitment_status(
            obj,
            generation_id=generation_id,
            modification_id=self.context.get("car_modification_id"),
        )

    def get_seller_id(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        return seller.id if seller else None

    def get_seller_name(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return ""
        name = f"{seller.first_name} {seller.last_name}".strip()
        return name or seller.email.split("@")[0]

    def get_seller_rating_avg(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return None
        agg = SellerReview.objects.filter(seller=seller).aggregate(avg=Avg("rating"))
        return round(agg["avg"], 1) if agg["avg"] is not None else None

    def get_seller_review_count(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return 0
        return SellerReview.objects.filter(seller=seller).count()


class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    category_image_url = serializers.SerializerMethodField()
    photos = ItemPhotoSerializer(many=True, read_only=True)
    options = OptionSerializer(many=True, read_only=True)
    alt_part_numbers = PartNumberSerializer(many=True, read_only=True)
    vehicle_year = serializers.IntegerField(source="vehicle.year", read_only=True, allow_null=True)
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()
    vehicle_generation_label = serializers.SerializerMethodField()
    vehicle_seller_zip = serializers.CharField(source="vehicle.seller_zip", read_only=True)
    vehicle_condition = serializers.CharField(source="vehicle.condition", read_only=True, default="")
    vehicle_mileage = serializers.IntegerField(source="vehicle.mileage", read_only=True, allow_null=True)
    vehicle_photos = serializers.SerializerMethodField()
    vehicle_modification = serializers.SerializerMethodField()
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    seller_member_since = serializers.SerializerMethodField()
    seller_rating_avg = serializers.SerializerMethodField()
    seller_review_count = serializers.SerializerMethodField()
    fitment = serializers.SerializerMethodField()
    verified_compatibilities = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id", "vehicle", "category", "category_name", "category_slug", "category_image_url",
            "title", "description", "price", "status", "condition",
            "weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in", "shipping_size",
            "oem_part_number", "oem_part_number_normalized", "alt_part_numbers",
            "photos", "options",
            "vehicle_year", "vehicle_make", "vehicle_model",
            "vehicle_generation_label", "vehicle_seller_zip",
            "vehicle_condition", "vehicle_mileage", "vehicle_photos",
            "vehicle_modification",
            "seller_id", "seller_name", "seller_member_since",
            "seller_rating_avg", "seller_review_count",
            "fitment", "verified_compatibilities",
            "created_at",
        )
        read_only_fields = ("id", "oem_part_number_normalized", "created_at")

    def get_category_image_url(self, obj):
        cat = obj.category
        return _abs(self.context.get("request"), cat.image.url if cat and cat.image else None)

    def get_vehicle_make(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.make.name
        return ""

    def get_vehicle_model(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.name
        return ""

    def get_vehicle_generation_label(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            g = obj.vehicle.generation
            parts = [g.car_model.make.name, g.car_model.name]
            if g.name:
                parts.append(g.name)
            start = g.production_start.year if g.production_start else ""
            end = g.production_end.year if g.production_end else "present"
            return f"{' '.join(parts)} ({start}–{end})"
        return ""

    def get_vehicle_photos(self, obj):
        if not obj.vehicle:
            return []
        request = self.context.get("request")
        result = []
        for p in obj.vehicle.photos.all()[:12]:
            url = _abs(request, p.url) if p.url else None
            thumb = _abs(request, p.thumbnail_url) if p.thumbnail_url else url
            result.append({"url": url, "thumbnail_url": thumb, "is_primary": p.is_primary, "label": p.label})
        return result

    def get_vehicle_modification(self, obj):
        mod = obj.vehicle.modification if obj.vehicle else None
        if not mod:
            return None
        return {
            "engine_code": mod.engine_code or None,
            "engine_displacement_cc": mod.engine_displacement_cc,
            "fuel_type": mod.fuel_type or None,
            "transmission_type": mod.transmission_type or None,
            "drive_type": mod.drive_type or None,
            "power_hp": mod.power_hp,
            "variant_name": mod.variant_name or None,
        }

    def get_seller_id(self, obj):
        if obj.vehicle and obj.vehicle.seller:
            return obj.vehicle.seller_id
        return None

    def get_seller_name(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return ""
        name = f"{seller.first_name} {seller.last_name}".strip()
        return name or seller.email.split("@")[0]

    def get_seller_member_since(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return None
        return seller.date_joined.date().isoformat()

    def get_seller_rating_avg(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return None
        agg = SellerReview.objects.filter(seller=seller).aggregate(avg=Avg("rating"))
        return round(agg["avg"], 1) if agg["avg"] is not None else None

    def get_seller_review_count(self, obj):
        seller = obj.vehicle.seller if obj.vehicle else None
        if not seller:
            return 0
        return SellerReview.objects.filter(seller=seller).count()

    def get_fitment(self, obj):
        generation_id = self.context.get("car_generation_id")
        if not generation_id:
            return None
        return item_fitment_status(
            obj,
            generation_id=generation_id,
            modification_id=self.context.get("car_modification_id"),
        )

    def get_verified_compatibilities(self, obj):
        seen = set()
        result = []
        for compat in obj.compatibilities.all():
            if not compat.is_verified:
                continue
            gen = compat.generation
            if not gen:
                continue
            if gen.id in seen:
                continue
            seen.add(gen.id)
            make_name = gen.car_model.make.name if gen.car_model else ""
            model_name = gen.car_model.name if gen.car_model else ""
            codes = gen.chassis_codes or []
            code = codes[0] if codes else gen.name or ""
            start = gen.production_start.year if gen.production_start else ""
            end = gen.production_end.year if gen.production_end else "present"
            gen_label = f"{code} ({start}–{end})" if code and start else gen.name or ""
            result.append({
                "generation_id": gen.id,
                "make_name": make_name,
                "model_name": model_name,
                "generation_label": gen_label,
                "year_from": compat.year_from,
                "year_to": compat.year_to,
            })
        result.sort(key=lambda x: (x["make_name"], x["model_name"], x["generation_label"]))
        return result


class VariationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variation
        fields = (
            "id", "vehicle", "item", "item_snapshot", "ai_confidence", "review_status", "created_at",
        )
        read_only_fields = ("id", "created_at")


class ItemCompatibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCompatibility
        fields = (
            "id", "item", "generation", "modification", "compat_level",
            "year_from", "year_to", "confidence_score", "source", "is_verified", "notes", "created_at",
        )
        read_only_fields = ("id", "is_verified", "created_at")
