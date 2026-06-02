from rest_framework import serializers

from .models import Category, Item, ItemCompatibility, ItemPhoto, Variation


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "shipping_size_default")


class ItemPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemPhoto
        fields = ("id", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")


class ItemListSerializer(serializers.ModelSerializer):
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    primary_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id", "title", "price", "status", "condition", "shipping_size",
            "category", "category_slug", "oem_part_number", "primary_photo_url", "created_at",
        )

    def get_primary_photo_url(self, obj):
        photo = obj.photos.filter(is_primary=True).first() or obj.photos.first()
        return photo.url if photo else None


class ItemSerializer(serializers.ModelSerializer):
    category_slug = serializers.SlugRelatedField(source="category", slug_field="slug", read_only=True)
    photos = ItemPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Item
        fields = (
            "id", "vehicle", "category", "category_slug", "title", "description",
            "price", "status", "condition", "weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in",
            "shipping_size", "oem_part_number", "photos", "created_at",
        )
        read_only_fields = ("id", "shipping_size", "created_at")


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
