from rest_framework import serializers

from catalog.serializers import GenerationSerializer, ModificationSerializer

from .models import Vehicle, VehiclePhoto


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ("id", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class VehicleListSerializer(serializers.ModelSerializer):
    generation_detail = GenerationSerializer(source="generation", read_only=True)
    primary_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            "id", "seller", "generation", "generation_detail", "modification",
            "vin", "year", "color", "mileage", "condition", "status",
            "seller_zip", "primary_photo_url", "created_at",
        )
        read_only_fields = ("id", "seller", "created_at")

    def get_primary_photo_url(self, obj):
        photo = obj.photos.filter(is_primary=True).first() or obj.photos.first()
        return photo.url if photo else None


class VehicleDetailSerializer(serializers.ModelSerializer):
    generation_detail = GenerationSerializer(source="generation", read_only=True)
    modification_detail = ModificationSerializer(source="modification", read_only=True)
    photos = VehiclePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id", "seller", "generation", "generation_detail",
            "modification", "modification_detail",
            "vin", "year", "color", "mileage", "condition", "status",
            "seller_zip", "photos", "created_at", "updated_at",
        )
        read_only_fields = ("id", "seller", "created_at", "updated_at")


class VehicleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            "id", "generation", "modification", "vin", "year",
            "color", "mileage", "condition", "status", "seller_zip",
        )
        read_only_fields = ("id",)
