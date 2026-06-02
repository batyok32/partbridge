from django.contrib import admin

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


@admin.register(PartCategory)
class PartCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "illustration_key")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PartFamily)
class PartFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "buy_new_only", "created_by")
    list_filter = ("buy_new_only", "category")
    search_fields = ("name", "slug")
    raw_id_fields = ("created_by",)


class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
    extra = 0
    fields = ("section", "image", "sort_order")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("id", "vin", "year", "make", "model", "owner", "analytics_status", "created_at")
    list_filter = ("analytics_status",)
    search_fields = ("vin", "make", "model", "owner__email")
    raw_id_fields = ("owner",)
    inlines = [VehiclePhotoInline]
    fieldsets = (
        (None, {"fields": ("owner", "vin", "year", "make", "model", "trim", "engine", "transmission", "drivetrain", "body_style")}),
        ("Colors", {"fields": ("color", "interior_color", "exterior_color_code", "interior_color_code", "paint_code")}),
        ("Location", {"fields": ("location_state", "location_zip", "pickup_allowed", "pickup_address")}),
        ("Condition", {"fields": ("condition_description", "has_damage", "damage_items", "odometer_miles", "mileage_unavailable")}),
        ("AI Description", {"fields": ("ai_image_description",), "classes": ("collapse",)}),
        ("Analytics", {"fields": ("analytics_status", "analytics_last_completed_at", "analytics_next_refresh_at")}),
        ("Notes", {"fields": ("notes",)}),
    )


class VehiclePartPhotoInline(admin.TabularInline):
    model = VehiclePartPhoto
    extra = 0


@admin.register(VehiclePart)
class VehiclePartAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "vehicle",
        "listing_state",
        "grade",
        "price",
        "package_size_category",
        "return_policy",
        "is_damaged",
        "is_removed",
        "listing_pipeline_status",
    )
    list_filter = ("listing_state", "grade", "is_damaged", "is_removed", "package_size_category", "listing_pipeline_status")
    search_fields = ("label", "vehicle__vin", "vehicle__make", "vehicle__model")
    raw_id_fields = ("vehicle", "part_family", "selected_option")
    inlines = [VehiclePartPhotoInline]
    fieldsets = (
        (None, {"fields": ("vehicle", "part_family", "variant_key", "label", "listing_state", "condition_draft", "grade", "price", "return_policy")}),
        ("AI", {"fields": ("ai_description",), "classes": ("collapse",)}),
        ("Shipping", {"fields": ("local_pickup_only", "shipping_disabled", "package_size_category", "size_packaged_length_cm", "size_packaged_width_cm", "size_packaged_height_cm", "size_packaged_weight_kg")}),
        ("Photos", {"fields": ("image_urls", "primary_photo_section")}),
        ("Part option", {"fields": ("selected_option",)}),
        ("Pipeline", {"fields": ("listing_pipeline_status", "listing_pipeline_started_at", "listing_pipeline_completed_at", "listing_pipeline_error"), "classes": ("collapse",)}),
        ("Other", {"fields": ("is_damaged", "is_removed", "condition_description", "description", "color_override")}),
    )


class PartOptionInline(admin.TabularInline):
    model = PartOption
    extra = 0
    readonly_fields = ("confidence", "needs_manual_check", "source", "created_at")


@admin.register(PartOptionSet)
class PartOptionSetAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "part_family", "status", "processed_at")
    list_filter = ("status",)
    search_fields = ("vehicle__vin", "part_family__name")
    inlines = [PartOptionInline]


class PartCompatibilityInline(admin.TabularInline):
    model = PartCompatibility
    extra = 0


@admin.register(PartOption)
class PartOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "option_label", "option_key", "confidence", "needs_manual_check", "is_applicable", "source")
    list_filter = ("needs_manual_check", "is_applicable", "source")
    search_fields = ("option_label", "option_key")
    inlines = [PartCompatibilityInline]


@admin.register(BrowseErrorReport)
class BrowseErrorReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "vehicle_part", "search_query", "created_at")
    search_fields = ("reporter__email", "issue_description", "search_query")
    readonly_fields = ("created_at",)
