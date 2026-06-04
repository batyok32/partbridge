from django.contrib import admin

from .models import (
    CartItem, Dispute, DisputeMessage,
    Order, OrderItem, Payment, SellerReview, ShippingRequest,
)


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


# ── Inlines ───────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("item", "price_at_purchase")
    readonly_fields = ("item", "price_at_purchase")
    show_change_link = True  # click through to OrderItem page → shows ShippingRequest

    def has_add_permission(self, request, obj=None):
        return False


class ShippingRequestInline(admin.TabularInline):
    model = ShippingRequest
    extra = 0
    fields = ("seller", "method", "shipping_size", "origin_zip", "dest_zip",
              "carrier", "tracking_number", "quoted_cost", "actual_cost",
              "is_delivered", "delivered_at")
    readonly_fields = ("seller",)


class DisputeMessageInline(admin.TabularInline):
    model = DisputeMessage
    extra = 1
    fields = ("sender", "sender_role", "body", "attachment_url", "sent_at")
    readonly_fields = ("sent_at",)


# ── Main admins ───────────────────────────────────────────────────────────────

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "item", "added_at")
    search_fields = ("user__email",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "status", "subtotal", "shipping_cost", "total", "placed_at")
    list_filter = ("status",)
    search_fields = ("buyer__email",)
    readonly_fields = ("placed_at",)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "item", "price_at_purchase")
    search_fields = ("order__id",)
    inlines = [ShippingRequestInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "amount", "refunded_amount", "provider", "paid_at")
    list_filter = ("status", "provider")


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ("id", "order_item", "buyer", "seller", "reason", "status", "opened_at")
    list_filter = ("reason", "status")
    inlines = [DisputeMessageInline]


# ── Admin-group-only standalones ──────────────────────────────────────────────

@admin.register(ShippingRequest)
class ShippingRequestAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "order_item", "seller", "method", "shipping_size", "is_delivered", "carrier", "tracking_number")
    list_filter = ("method", "is_delivered", "shipping_size")


@admin.register(DisputeMessage)
class DisputeMessageAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "dispute", "sender", "sender_role", "sent_at")
    list_filter = ("sender_role",)


@admin.register(SellerReview)
class SellerReviewAdmin(AdminGroupOnly, admin.ModelAdmin):
    list_display = ("id", "seller", "buyer", "order_item", "rating", "created_at")
    list_filter = ("rating",)
