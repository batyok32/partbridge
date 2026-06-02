from rest_framework import serializers

from .models import Category, Item, ItemCompatibility, ItemPhoto, Option, Variation


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "shipping_size_default")


class ItemPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPhoto
        fields = ("id", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")


class OptionSerializer(serializers.ModelSerializer):
    option_category_name = serializers.CharField(source="option_category.name", read_only=True)

    class Meta:
        model = Option
        fields = ("id", "option_category", "option_category_name", "value", "is_ai_eliminated", "elimination_reason")


class VehicleBriefSerializer(serializers.Serializer):
    """Lightweight vehicle summary embedded in Item responses."""
    id = serializers.IntegerField()
    year = serializers.IntegerField(allow_null=True)
    seller_zip = serializers.CharField()
    make_name = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()
    generation_name = serializers.SerializerMethodField()

    def get_make_name(self, obj):
        if obj.generation:
            return obj.generation.car_model.make.name
        return ""

    def get_model_name(self, obj):
        if obj.generation:
            return obj.generation.car_model.name
        return ""

    def get_generation_name(self, obj):
        if obj.generation:
            return obj.generation.name or ""
        return ""


class ItemListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    primary_photo_url = serializers.SerializerMethodField()
    vehicle_year = serializers.IntegerField(source="vehicle.year", read_only=True, allow_null=True)
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id", "title", "price", "status", "condition", "shipping_size",
            "category", "category_name", "category_slug", "oem_part_number",
            "primary_photo_url", "vehicle", "vehicle_year", "vehicle_make", "vehicle_model",
            "created_at",
        )

    def get_primary_photo_url(self, obj):
        photo = obj.photos.filter(is_primary=True).first() or obj.photos.first()
        return photo.url if photo else None

    def get_vehicle_make(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.make.name
        return ""

    def get_vehicle_model(self, obj):
        if obj.vehicle and obj.vehicle.generation:
            return obj.vehicle.generation.car_model.name
        return ""


class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    photos = ItemPhotoSerializer(many=True, read_only=True)
    options = OptionSerializer(many=True, read_only=True)
    vehicle_year = serializers.IntegerField(source="vehicle.year", read_only=True, allow_null=True)
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()
    vehicle_generation_label = serializers.SerializerMethodField()
    vehicle_seller_zip = serializers.CharField(source="vehicle.seller_zip", read_only=True)

    class Meta:
        model = Item
        fields = (
            "id", "vehicle", "category", "category_name", "category_slug",
            "title", "description", "price", "status", "condition",
            "weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in", "shipping_size",
            "oem_part_number", "photos", "options",
            "vehicle_year", "vehicle_make", "vehicle_model",
            "vehicle_generation_label", "vehicle_seller_zip",
            "created_at",
        )
        read_only_fields = ("id", "shipping_size", "created_at")

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
