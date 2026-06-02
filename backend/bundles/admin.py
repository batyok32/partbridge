from django.contrib import admin

from .models import Bundle, BundleCategory, BundleItem


@admin.register(BundleCategory)
class BundleCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type")
    list_filter = ("type",)
    search_fields = ("name",)


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "bundle_category", "discount_pct", "status", "created_at")
    list_filter = ("status", "bundle_category")
    search_fields = ("name",)


@admin.register(BundleItem)
class BundleItemAdmin(admin.ModelAdmin):
    list_display = ("id", "bundle", "item")
    list_filter = ("bundle",)
