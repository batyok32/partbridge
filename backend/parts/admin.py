from django.contrib import admin

from .models import Category, Item, ItemCompatibility, ItemOptionConfig, ItemPhoto, Option, OptionCategory, Variation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent", "shipping_size_default")
    search_fields = ("name", "slug")
    list_filter = ("shipping_size_default",)


@admin.register(OptionCategory)
class OptionCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "name", "type")
    list_filter = ("type", "category")
    search_fields = ("name",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "vehicle", "category", "price", "status", "condition", "shipping_size", "created_at")
    list_filter = ("status", "condition", "shipping_size", "category")
    search_fields = ("title", "oem_part_number")
    readonly_fields = ("shipping_size", "created_at")


@admin.register(ItemOptionConfig)
class ItemOptionConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "option_category", "is_buyer_question", "surviving_count")
    list_filter = ("is_buyer_question",)


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "option_category", "value", "is_ai_eliminated")
    list_filter = ("is_ai_eliminated",)
    search_fields = ("value",)


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "item", "ai_confidence", "review_status", "created_at")
    list_filter = ("ai_confidence", "review_status")


@admin.register(ItemCompatibility)
class ItemCompatibilityAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "generation", "modification", "compat_level", "confidence_score", "source", "is_verified")
    list_filter = ("compat_level", "source", "is_verified")


@admin.register(ItemPhoto)
class ItemPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "sort_order", "is_primary", "label", "uploaded_at")
    list_filter = ("is_primary",)
