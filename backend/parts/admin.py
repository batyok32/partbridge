from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Category, Item, ItemCompatibility, ItemPhoto,
    Option, OptionCategory, OptionValue, PartNumber, Variation,
)


def _is_admin_user(user):
    return user.is_superuser or user.groups.filter(name="Admin").exists()


class AdminGroupOnly:
    """Hides a ModelAdmin from the index and all views for non-Admin-group staff."""
    def has_module_perms(self, request):
        return _is_admin_user(request.user)
    def has_view_permission(self, request, obj=None):
        return _is_admin_user(request.user)
    def has_add_permission(self, request):
        return _is_admin_user(request.user)
    def has_change_permission(self, request, obj=None):
        return _is_admin_user(request.user)
    def has_delete_permission(self, request, obj=None):
        return _is_admin_user(request.user)


# ── Inlines ──────────────────────────────────────────────────────────────────

class OptionInline(admin.TabularInline):
    model = Option
    extra = 1
    fields = ("option_category", "value")


class PartNumberInline(admin.TabularInline):
    model = PartNumber
    extra = 1
    fields = ("number_raw", "brand", "number_normalized")
    readonly_fields = ("number_normalized",)


class ItemPhotoInline(admin.TabularInline):
    model = ItemPhoto
    extra = 1
    fields = ("photo_preview", "image", "url", "thumbnail_url", "sort_order", "is_primary", "label")
    readonly_fields = ("photo_preview",)

    @admin.display(description="Preview")
    def photo_preview(self, obj):
        src = obj.image.url if obj.image else (obj.url or None)
        if src:
            return format_html(
                '<img src="{}" style="max-height:56px;max-width:80px;object-fit:cover;border-radius:4px;">',
                src,
            )
        return "—"


class ItemCompatibilityInline(admin.TabularInline):
    model = ItemCompatibility
    extra = 0
    fields = ("generation", "modification", "compat_level", "year_from", "year_to", "confidence_score", "source", "is_verified")
    autocomplete_fields = ("generation",)


# ── Main admins ───────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent", "sort_order", "shipping_size_default", "image_preview")
    search_fields = ("name", "slug")
    list_filter = ("shipping_size_default",)
    readonly_fields = ("image_preview",)
    fields = ("name", "slug", "parent", "sort_order", "shipping_size_default", "image", "image_preview")

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:60px;max-width:80px;object-fit:cover;border-radius:4px;">',
                obj.image.url,
            )
        return "—"


class OptionValueInline(admin.TabularInline):
    model = OptionValue
    extra = 1
    fields = ("value", "sort_order")


@admin.register(OptionCategory)
class OptionCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "name", "type", "is_required")
    list_filter = ("type", "is_required", "category")
    search_fields = ("name",)
    inlines = [OptionValueInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "vehicle", "category", "price", "status", "condition", "shipping_size", "created_at")
    list_filter = ("status", "condition", "shipping_size", "category")
    list_editable = ("shipping_size",)
    search_fields = ("title", "oem_part_number")
    readonly_fields = ("oem_part_number_normalized", "created_at")
    fieldsets = (
        (None, {"fields": ("vehicle", "category", "title", "description", "price", "status", "condition", "assembly_bundle")}),
        ("Shipping", {
            "fields": ("shipping_size", "weight_lbs", "dim_l_in", "dim_w_in", "dim_h_in"),
            "description": "shipping_size is auto-computed from dimensions when any dimension is provided; set manually otherwise.",
        }),
        ("Part numbers", {"fields": ("oem_part_number", "oem_part_number_normalized")}),
        ("Meta", {"fields": ("created_at",)}),
    )
    inlines = [ItemPhotoInline, OptionInline, PartNumberInline, ItemCompatibilityInline]


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "item", "ai_confidence", "review_status", "created_at")
    list_filter = ("ai_confidence", "review_status")


# ── Admin-group-only standalones (still accessible to superusers/Admin group) ─

@admin.register(Option)
class OptionAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "item", "option_category", "value")
    search_fields = ("value",)
    list_filter = ("option_category",)


@admin.register(PartNumber)
class PartNumberAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "item", "number_raw", "number_normalized", "brand")
    search_fields = ("number_raw", "number_normalized")


@admin.register(ItemCompatibility)
class ItemCompatibilityAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "item", "generation", "modification", "compat_level", "confidence_score", "source", "is_verified")
    list_filter = ("compat_level", "source", "is_verified")


@admin.register(ItemPhoto)
class ItemPhotoAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "item", "sort_order", "is_primary", "label", "uploaded_at")
    list_filter = ("is_primary",)
