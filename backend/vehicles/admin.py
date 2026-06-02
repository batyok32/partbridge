from django.contrib import admin

from .models import Vehicle, VehiclePhoto


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "generation", "modification", "year", "condition", "status", "seller_zip", "created_at")
    list_filter = ("status", "condition")
    search_fields = ("vin", "seller__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(VehiclePhoto)
class VehiclePhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "sort_order", "is_primary", "label", "uploaded_at")
    list_filter = ("is_primary",)
