from rest_framework import serializers

from catalog.serializers import GenerationSerializer, ModificationSerializer

from .models import Vehicle, VehiclePhoto


class VehiclePhotoSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = VehiclePhoto
        fields = ("id", "image", "url", "thumbnail_url", "sort_order", "is_primary", "label", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")
        extra_kwargs = {"url": {"required": False, "allow_blank": True}}

    def validate(self, data):
        if not data.get("image") and not data.get("url"):
            raise serializers.ValidationError("Provide either an image file or a url.")
        return data


class VehicleListSerializer(serializers.ModelSerializer):
    generation_detail = GenerationSerializer(source="generation", read_only=True)
    primary_photo_url = serializers.SerializerMethodField()
    make_name = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()
    generation_label = serializers.SerializerMethodField()
    parts_count = serializers.SerializerMethodField()
    photos_count = serializers.SerializerMethodField()
    analytics_status = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            "id", "seller", "generation", "generation_detail", "modification",
            "vin", "year", "color", "mileage", "condition", "status",
            "seller_zip", "primary_photo_url", "created_at",
            "make_name", "model_name", "generation_label",
            "parts_count", "photos_count", "analytics_status",
        )
        read_only_fields = ("id", "seller", "created_at")

    def get_primary_photo_url(self, obj):
        photo = obj.photos.filter(is_primary=True).first() or obj.photos.first()
        return photo.url if photo else None

    def get_make_name(self, obj):
        try:
            return obj.generation.car_model.make.name if obj.generation else ""
        except Exception:
            return ""

    def get_model_name(self, obj):
        try:
            return obj.generation.car_model.name if obj.generation else ""
        except Exception:
            return ""

    def get_generation_label(self, obj):
        try:
            gen = obj.generation
            if not gen:
                return ""
            codes = ", ".join(gen.chassis_codes) if gen.chassis_codes else ""
            year_start = gen.production_start.year if gen.production_start else ""
            year_end = gen.production_end.year if gen.production_end else ""
            years = f"{year_start}–{year_end}" if year_start else ""
            if codes and years:
                return f"{codes} ({years})"
            return codes or years
        except Exception:
            return ""

    def get_parts_count(self, obj):
        return obj.items.count()

    def get_photos_count(self, obj):
        return obj.photos.count()

    def get_analytics_status(self, obj):
        return obj.status


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
