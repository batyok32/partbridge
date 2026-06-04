from django.contrib import admin
from django.utils.html import format_html

from .models import Bundle, BundleCategory, BundleItem


class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 1
    autocomplete_fields = ("item",)
    fields = ("item",)


@admin.register(BundleCategory)
class BundleCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "image_preview")
    list_filter = ("type",)
    search_fields = ("name",)
    readonly_fields = ("image_preview",)
    fields = ("name", "type", "image", "image_preview")

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:60px;max-width:80px;object-fit:cover;border-radius:4px;">',
                obj.image.url,
            )
        return "—"


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "bundle_category", "total_items_price", "discount_pct", "fixed_price", "status", "created_at")
    list_filter = ("status", "bundle_category")
    search_fields = ("name",)
    readonly_fields = ("total_items_price", "created_at")
    inlines = [BundleItemInline]
    fieldsets = (
        (None, {"fields": ("bundle_category", "name", "status", "created_at")}),
        (
            "Assembly settings",
            {
                "fields": ("category",),
                "description": (
                    "Assembly bundles only. Choose the part category that best describes the assembled unit "
                    "(e.g. 'Engine', 'Suspension Kit'). This is used as the category for the purchasable assembly item."
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Pricing",
            {
                "fields": ("total_items_price", "discount_pct", "fixed_price"),
                "description": (
                    "Enter a discount % OR a fixed price — the other is computed automatically on save. "
                    "Fixed price takes priority when both are set."
                ),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.bundle_category.type == "assembly":
            return fieldsets
        # Hide assembly settings section for discount bundles
        return [fs for fs in fieldsets if fs[0] != "Assembly settings"]

    @admin.display(description="Items total")
    def total_items_price(self, obj):
        if not obj.pk:
            return "—"
        total = sum(
            float(bi.item.price)
            for bi in obj.bundle_items.select_related("item").all()
        )
        return f"${total:,.2f}"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        bundle = form.instance
        items = bundle.bundle_items.select_related("item").all()
        total = sum(float(bi.item.price) for bi in items)
        if total <= 0:
            return
        if bundle.fixed_price is not None:
            pct = max(0, round((1 - float(bundle.fixed_price) / total) * 100, 2))
            Bundle.objects.filter(pk=bundle.pk).update(discount_pct=pct)
        else:
            price = round(total * (1 - float(bundle.discount_pct) / 100), 2)
            Bundle.objects.filter(pk=bundle.pk).update(fixed_price=price)
