from rest_framework import serializers

from .models import CarModel, Generation, Make, Modification


class MakeSerializer(serializers.ModelSerializer):
    listing_count = serializers.IntegerField(read_only=True, required=False)
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Make
        fields = ("id", "name", "slug", "country", "logo_url", "listing_count", "created_at")

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo:
            url = obj.logo.url
            return request.build_absolute_uri(url) if request else url
        return obj.logo_url or None


class CarModelSerializer(serializers.ModelSerializer):
    make_name = serializers.CharField(source="make.name", read_only=True)

    class Meta:
        model = CarModel
        fields = ("id", "make", "make_name", "name", "slug", "created_at")


class GenerationSerializer(serializers.ModelSerializer):
    make_name = serializers.CharField(source="car_model.make.name", read_only=True)
    car_model_name = serializers.CharField(source="car_model.name", read_only=True)
    display_label = serializers.SerializerMethodField()

    class Meta:
        model = Generation
        fields = (
            "id", "car_model", "make", "make_name", "car_model_name",
            "chassis_codes", "name", "body_style", "display_label",
            "production_start", "production_end", "region", "created_at",
        )

    def get_display_label(self, obj):
        parts = [obj.car_model.make.name, obj.car_model.name]
        if obj.name:
            parts.append(obj.name)
        start = obj.production_start.year if obj.production_start else ""
        end = obj.production_end.year if obj.production_end else "present"
        return f"{' '.join(parts)} ({start}–{end})"


class ModificationSerializer(serializers.ModelSerializer):
    display_label = serializers.SerializerMethodField()

    class Meta:
        model = Modification
        fields = (
            "id", "generation", "code", "variant_name", "engine_code",
            "engine_displacement_cc", "fuel_type", "transmission_type",
            "transmission_detail", "cab_type", "drive_type", "power_hp",
            "production_start", "production_end", "display_label", "created_at",
        )

    def get_display_label(self, obj):
        parts = [obj.code]
        if obj.variant_name:
            parts.append(obj.variant_name)
        if obj.engine_code:
            parts.append(obj.engine_code)
        return " · ".join(parts)
