from django.contrib import admin
from django.utils.html import format_html

from .models import Vehicle, VehiclePhoto


def _is_admin_user(user):
    return user.is_superuser or user.groups.filter(name="Admin").exists()


class AdminGroupOnly:
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


class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
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


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "generation", "modification", "year", "condition", "status", "seller_zip", "created_at")
    list_filter = ("status", "condition")
    search_fields = ("vin", "seller__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [VehiclePhotoInline]


@admin.register(VehiclePhoto)
class VehiclePhotoAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "vehicle", "sort_order", "is_primary", "label", "uploaded_at")
    list_filter = ("is_primary",)
