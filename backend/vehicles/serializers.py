from rest_framework import serializers

from .models import Vehicle, VehiclePhoto


class VehiclePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePhoto
        fields = ("id", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


class VehicleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            "id", "seller", "generation", "modification", "vin", "year",
            "color", "mileage", "condition", "status", "seller_zip", "created_at",
        )
        read_only_fields = ("id", "seller", "created_at")


class VehicleDetailSerializer(serializers.ModelSerializer):
    photos = VehiclePhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id", "seller", "generation", "modification", "vin", "year",
            "color", "mileage", "condition", "status", "seller_zip",
            "photos", "created_at", "updated_at",
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
