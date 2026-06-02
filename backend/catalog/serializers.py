from rest_framework import serializers

from .models import CarModel, Generation, Make, Modification


class MakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Make
        fields = ("id", "name", "slug", "country", "logo_url", "created_at")


class CarModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarModel
        fields = ("id", "make", "name", "slug", "created_at")


class GenerationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Generation
        fields = (
            "id", "car_model", "make", "chassis_codes", "name", "body_style",
            "production_start", "production_end", "region", "created_at",
        )


class ModificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modification
        fields = (
            "id", "generation", "code", "variant_name", "engine_code",
            "engine_displacement_cc", "fuel_type", "transmission_type",
            "transmission_detail", "cab_type", "drive_type", "power_hp",
            "production_start", "production_end", "created_at",
        )
