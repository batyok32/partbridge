from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import (
    BrowseErrorReport,
    PartCategory,
    PartCompatibility,
    PartFamily,
    PartOption,
    PartOptionSet,
    Vehicle,
    VehiclePart,
    VehiclePartPhoto,
    VehiclePhoto,
)
from .shipping_preview import mask_zip, shipping_preview_stub


def _market_summary_from_report(data):
    if not data:
        return None
    po = data.get("part_out_summary") or {}
    return {
        "estimated_total_net": po.get("estimated_total_net"),
        "stats_combined": (data.get("stats") or {}).get("combined"),
        "counts": data.get("counts"),
        "top_opportunities": (data.get("top_opportunities") or [])[:5],
        "scraped_at": data.get("scraped_at"),
    }


class PartCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartCategory
        fields = ("id", "slug", "name", "sort_order", "illustration_key")


class PartFamilySerializer(serializers.ModelSerializer):
    category = PartCategorySerializer(read_only=True)

    class Meta:
        model = PartFamily
        fields = ("id", "slug", "name", "buy_new_only", "variant_templates", "category")


class VehiclePhotoSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()

    class Meta:
        model = VehiclePhoto
        fields = ("id", "section", "kind", "image", "sort_order", "created_at")
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")
        if request and rep.get("image"):
            rep["image"] = request.build_absolute_uri(rep["image"])
        return rep


class VehiclePartPhotoSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()

    class Meta:
        model = VehiclePartPhoto
        fields = ("id", "image", "sort_order", "created_at")
        read_only_fields = ("id", "created_at")

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")
        if request and rep.get("image"):
            rep["image"] = request.build_absolute_uri(rep["image"])
        return rep


class PartCompatibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartCompatibility
        fields = ("make", "model", "year_range_start", "year_range_end", "trim", "notes")


class PartOptionSerializer(serializers.ModelSerializer):
    compatibilities = PartCompatibilitySerializer(many=True, read_only=True)

    class Meta:
        model = PartOption
        fields = (
            "id",
            "option_key",
            "option_label",
            "confidence",
            "needs_manual_check",
            "is_applicable",
            "source",
            "compatibilities",
        )


class PartOptionSetSerializer(serializers.ModelSerializer):
    options = PartOptionSerializer(many=True, read_only=True)

    class Meta:
        model = PartOptionSet
        fields = ("id", "status", "options", "processed_at")


class VehiclePartSerializer(serializers.ModelSerializer):
    part_family = PartFamilySerializer(read_only=True)
    category_slug = serializers.CharField(source="part_family.category.slug", read_only=True)
    listing_state_effective = serializers.CharField(read_only=True, source="effective_listing_state")
    selected_option = PartOptionSerializer(read_only=True)

    class Meta:
        model = VehiclePart
        fields = (
            "id",
            "part_family",
            "category_slug",
            "variant_key",
            "label",
            "listing_state",
            "listing_state_effective",
            "condition_draft",
            "condition_description",
            "ai_description",
            "grade",
            "color_override",
            "description",
            "price",
            "return_policy",
            "buy_now_expires_at",
            "local_pickup_only",
            "shipping_disabled",
            "package_size_category",
            "size_length_cm",
            "size_width_cm",
            "size_height_cm",
            "size_weight_kg",
            "size_packaged_length_cm",
            "size_packaged_width_cm",
            "size_packaged_height_cm",
            "size_packaged_weight_kg",
            "use_vehicle_location",
            "location_note",
            "image_urls",
            "primary_photo_section",
            "is_damaged",
            "is_removed",
            "selected_option",
            "listing_pipeline_status",
            "listing_pipeline_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "variant_key",
            "created_at",
            "updated_at",
            "part_family",
            "listing_state_effective",
            "buy_now_expires_at",
            "ai_description",
            "grade",
            "selected_option",
            "listing_pipeline_status",
            "listing_pipeline_error",
            "primary_photo_section",
        )

    def validate(self, data):
        inst = self.instance
        if inst is None:
            state = data.get("listing_state", VehiclePart.ListingState.DRAFT)
            price = data.get("price")
            condition = data.get("condition_draft")
        else:
            state = data.get("listing_state", inst.listing_state)
            price = data["price"] if "price" in data else inst.price
            condition = data.get("condition_draft", serializers.empty)
            if condition is serializers.empty:
                condition = inst.condition_draft

        if state == VehiclePart.ListingState.BUY_NOW:
            bad_price = price is None
            if not bad_price:
                try:
                    bad_price = Decimal(str(price)) <= 0
                except Exception:
                    bad_price = True
            if bad_price:
                raise serializers.ValidationError({"price": "Buy Now requires a price greater than zero."})
            if not condition:
                raise serializers.ValidationError({"condition_draft": "Buy Now requires a condition."})
        return data

    def update(self, instance, validated_data):
        inst = super().update(instance, validated_data)
        if inst.listing_state != VehiclePart.ListingState.BUY_NOW:
            if inst.buy_now_expires_at is not None:
                inst.buy_now_expires_at = None
                inst.save(update_fields=["buy_now_expires_at", "updated_at"])
        return inst


class PublicPartFamilyMiniSerializer(serializers.ModelSerializer):
    category = PartCategorySerializer(read_only=True)

    class Meta:
        model = PartFamily
        fields = ("id", "slug", "name", "category")


class PublicVehiclePartSerializer(serializers.ModelSerializer):
    part_family = PublicPartFamilyMiniSerializer(read_only=True)
    category_slug = serializers.CharField(source="part_family.category.slug", read_only=True)
    listing_state_effective = serializers.CharField(read_only=True, source="effective_listing_state")
    vehicle_public = serializers.SerializerMethodField()
    shipping_preview = serializers.SerializerMethodField()
    card_image_url = serializers.SerializerMethodField()
    effective_buy_price = serializers.SerializerMethodField()
    is_purchasable = serializers.SerializerMethodField()

    class Meta:
        model = VehiclePart
        fields = (
            "id",
            "label",
            "listing_state",
            "listing_state_effective",
            "condition_draft",
            "condition_description",
            "ai_description",
            "description",
            "grade",
            "price",
            "effective_buy_price",
            "offer_expires_at",
            "return_policy",
            "buy_now_expires_at",
            "is_damaged",
            "is_purchasable",
            "local_pickup_only",
            "shipping_disabled",
            "package_size_category",
            "variant_key",
            "color_override",
            "location_note",
            "size_packaged_length_cm",
            "size_packaged_width_cm",
            "size_packaged_height_cm",
            "size_packaged_weight_kg",
            "part_family",
            "category_slug",
            "vehicle_public",
            "image_urls",
            "primary_photo_section",
            "card_image_url",
            "shipping_preview",
            "created_at",
            "updated_at",
        )

    def get_is_purchasable(self, obj):
        return obj.is_purchasable()

    def get_effective_buy_price(self, obj):
        p = obj.effective_buy_price
        if p is None:
            return None
        return str(Decimal(str(p)).quantize(Decimal("0.01")))

    def get_vehicle_public(self, obj):
        v = obj.vehicle
        request = self.context.get("request")
        owner = v.owner
        display_name = (owner.get_full_name() or "").strip() or owner.username

        gallery = []
        primary_section = obj.primary_photo_section or ""
        primary_url = None

        for ph in v.photos.order_by("sort_order", "id")[:20]:
            if not ph.image:
                continue
            try:
                url = request.build_absolute_uri(ph.image.url) if request else ph.image.url
            except Exception:
                continue
            entry = {"id": ph.id, "section": ph.section, "kind": ph.kind, "url": url}
            gallery.append(entry)
            # Use section-matched photo as primary
            if primary_section and ph.section == primary_section and primary_url is None:
                primary_url = url

        if primary_url is None and gallery:
            primary_url = gallery[0]["url"]

        return {
            "vehicle_id": v.id,
            "year": v.year,
            "make": v.make,
            "model": v.model,
            "trim": (v.trim or "").strip(),
            "engine": (v.engine or "").strip(),
            "transmission": (v.transmission or "").strip(),
            "drivetrain": (v.drivetrain or "").strip(),
            "color": (v.color or "").strip(),
            "has_damage": bool(v.has_damage),
            "location_state": (v.location_state or "").strip(),
            "location_zip_masked": mask_zip(v.location_zip),
            "pickup_allowed": bool(v.pickup_allowed),
            "primary_photo_url": primary_url,
            "photo_urls": gallery,
            "odometer_miles": v.odometer_miles,
            "mileage_unavailable": bool(v.mileage_unavailable),
            "seller": {
                "id": owner.id,
                "display_name": display_name,
                "completed_sales": 0,
                "rating_avg": None,
            },
        }

    def get_card_image_url(self, obj):
        # Part photos first, then vehicle photos
        part_photos = obj.photos.order_by("sort_order", "id").first()
        if part_photos and part_photos.image:
            try:
                request = self.context.get("request")
                url = part_photos.image.url
                return request.build_absolute_uri(url) if request else url
            except Exception:
                pass
        urls = obj.image_urls or []
        if urls and isinstance(urls[0], str):
            return urls[0]
        return None

    def get_shipping_preview(self, obj):
        buyer_zip = (self.context.get("buyer_zip") or "").strip()
        if not buyer_zip:
            return {
                "available": False,
                "note": "Add your ZIP for a transit estimate.",
                "shipping_options": [],
            }
        return shipping_preview_stub(
            seller_state=obj.vehicle.location_state or "",
            seller_zip=obj.vehicle.location_zip or "",
            buyer_zip=buyer_zip,
            package_weight_kg=float(obj.size_packaged_weight_kg or 0) or None,
            pickup_allowed=bool(obj.vehicle.pickup_allowed) and not obj.local_pickup_only,
        )


class VehicleListSerializer(serializers.ModelSerializer):
    parts_count = serializers.IntegerField(read_only=True)
    photos_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "vin",
            "year",
            "make",
            "model",
            "trim",
            "engine",
            "transmission",
            "drivetrain",
            "body_style",
            "color",
            "interior_color",
            "exterior_color_code",
            "paint_code",
            "location_state",
            "location_zip",
            "condition_description",
            "pickup_allowed",
            "pickup_address",
            "return_policy_default",
            "analytics_status",
            "analytics_next_refresh_at",
            "parts_count",
            "photos_count",
            "created_at",
            "updated_at",
        )


class VehicleDetailSerializer(serializers.ModelSerializer):
    photos = VehiclePhotoSerializer(many=True, read_only=True)
    market_analysis_summary = serializers.SerializerMethodField()
    can_refresh_market_analytics = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "vin",
            "year",
            "make",
            "model",
            "trim",
            "engine",
            "transmission",
            "drivetrain",
            "body_style",
            "color",
            "interior_color",
            "exterior_color_code",
            "interior_color_code",
            "paint_code",
            "location_state",
            "location_zip",
            "notes",
            "condition_description",
            "ai_image_description",
            "pickup_allowed",
            "pickup_address",
            "return_policy_default",
            "has_damage",
            "damage_items",
            "analytics_status",
            "analytics_last_completed_at",
            "analytics_next_refresh_at",
            "market_analysis_summary",
            "can_refresh_market_analytics",
            "odometer_miles",
            "mileage_unavailable",
            "photos",
            "created_at",
            "updated_at",
        )

    def get_market_analysis_summary(self, obj):
        from analytics.models import PartAnalysis

        latest = (
            PartAnalysis.objects.filter(vehicle=obj, status="completed")
            .order_by("-completed_at")
            .first()
        )
        if not latest or not latest.analysis_data:
            return None
        return _market_summary_from_report(latest.analysis_data)

    def get_can_refresh_market_analytics(self, obj):
        return obj.can_refresh_market_analytics()


class VehicleCreateUpdateSerializer(serializers.ModelSerializer):
    def validate_location_state(self, value):
        v = (value or "").strip().upper()
        if v and len(v) != 2:
            raise serializers.ValidationError("State must be a 2-letter code.")
        return v

    def validate_location_zip(self, value):
        return (value or "").strip()[:10]

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "vin",
            "year",
            "make",
            "model",
            "trim",
            "engine",
            "transmission",
            "drivetrain",
            "body_style",
            "color",
            "interior_color",
            "exterior_color_code",
            "interior_color_code",
            "paint_code",
            "location_state",
            "location_zip",
            "notes",
            "condition_description",
            "pickup_allowed",
            "pickup_address",
            "return_policy_default",
            "has_damage",
            "damage_items",
            "analytics_status",
            "odometer_miles",
            "mileage_unavailable",
        )
        read_only_fields = ("id", "analytics_status")

    def validate_vin(self, value):
        v = (value or "").strip().upper()
        if len(v) != 17:
            raise serializers.ValidationError("VIN must be exactly 17 characters.")
        return v


class VinDecodeSerializer(serializers.Serializer):
    vin = serializers.CharField(min_length=17, max_length=17)
    include_raw = serializers.BooleanField(required=False, default=False)

    def validate_vin(self, value):
        return (value or "").strip().upper()


class CustomPartCreateSerializer(serializers.Serializer):
    category = serializers.PrimaryKeyRelatedField(queryset=PartCategory.objects.all())
    name = serializers.CharField(max_length=255)
    variant_templates = serializers.JSONField(default=list)


class BrowseErrorReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrowseErrorReport
        fields = ("id", "vehicle_part", "search_query", "issue_description", "contact_email", "created_at")
        read_only_fields = ("id", "created_at")
