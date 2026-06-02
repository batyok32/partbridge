from django.contrib import admin

from .models import CartItem, Dispute, DisputeMessage, Order, OrderItem, Payment, SellerReview, ShippingRequest


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


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "item", "price_at_purchase")
    search_fields = ("order__id",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "amount", "refunded_amount", "provider", "paid_at")
    list_filter = ("status", "provider")


@admin.register(ShippingRequest)
class ShippingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "order_item", "seller", "method", "shipping_size", "is_delivered", "carrier", "tracking_number")
    list_filter = ("method", "is_delivered", "shipping_size")


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ("id", "order_item", "buyer", "seller", "reason", "status", "opened_at")
    list_filter = ("reason", "status")


@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "dispute", "sender", "sender_role", "sent_at")
    list_filter = ("sender_role",)


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "seller", "buyer", "order_item", "rating", "created_at")
    list_filter = ("rating",)
