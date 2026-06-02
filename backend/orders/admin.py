from django.contrib import admin
from django.utils import timezone

from .models import CartItem, Order, SellerReview, SellerVerification
from .order_notifications import send_delivery_photos_to_buyer, send_seller_verification_approved_email


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "buyer",
        "seller",
        "vehicle_part",
        "amount_usd",
        "state",
        "shipping_paid_at",
        "tracking_number",
        "tracking_status",
        "created_at",
    )
    list_filter = ("state", "payout_blocked", "funds_held_until_delivered")
    search_fields = ("buyer__email", "seller__email", "vehicle_part__label", "stripe_payment_intent_id", "tracking_number")
    readonly_fields = ("created_at", "updated_at", "paid_at", "released_to_seller_at", "buyer_display_state")
    fieldsets = (
        (None, {"fields": ("buyer", "seller", "vehicle_part", "state", "amount_usd", "shipping_amount_usd", "currency")}),
        ("Buyer address", {"fields": ("buyer_name", "buyer_address_line1", "buyer_address_line2", "buyer_city", "buyer_state", "buyer_zip", "buyer_notes")}),
        ("Vehicle snapshot", {"fields": ("vehicle_snapshot",), "classes": ("collapse",)}),
        ("Escrow / payout", {"fields": ("funds_held_until_delivered", "released_to_seller_at", "payout_blocked", "hold_until")}),
        (
            "Shipping management",
            {
                "fields": (
                    "shipping_instructions",
                    "shipping_label_url",
                    "tracking_url",
                    "tracking_carrier",
                    "tracking_number",
                    "tracking_status",
                    "shipping_label_cost_usd",
                    "shipping_paid_at",
                )
            },
        ),
        ("Delivery", {"fields": ("delivered_at", "delivery_photos", "delivery_notes")}),
        ("Returns", {"fields": ("refund_requested_at", "refund_request_reason", "refunded_at")}),
        ("Cancellation", {"fields": ("cancelled_at", "cancellation_reason")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "paid_at", "buyer_display_state")}),
    )

    def save_model(self, request, obj, form, change):
        prev = None
        if change and obj.pk:
            prev = Order.objects.filter(pk=obj.pk).values(
                "state", "delivery_photos", "shipping_label_url", "tracking_number"
            ).first()
        super().save_model(request, obj, form, change)
        if not change or not prev:
            return

        # Send delivery photos when state is set to delivered with new photos
        photos = obj.delivery_photos or []
        if obj.state == Order.State.DELIVERED and photos:
            prev_p = prev.get("delivery_photos") or []
            if prev.get("state") != Order.State.DELIVERED or prev_p != photos:
                try:
                    send_delivery_photos_to_buyer(obj)
                except Exception:
                    pass

        # Notify seller when label is uploaded
        if obj.shipping_label_url and not prev.get("shipping_label_url"):
            try:
                _notify_seller_label_ready(obj)
            except Exception:
                pass

        # Notify buyer when tracking is added
        if obj.tracking_number and not prev.get("tracking_number"):
            try:
                _notify_buyer_shipped(obj)
            except Exception:
                pass


def _notify_seller_label_ready(order):
    from .notifications import send_order_email
    send_order_email(
        to_email=order.seller.email,
        subject=f"Shipping label ready — Order #{order.id} — Partbridge",
        body=(
            f"Your shipping label for Order #{order.id} is ready.\n\n"
            f"Item: {order.vehicle_part.label}\n"
            f"Label: {order.shipping_label_url}\n\n"
            + (f"Instructions:\n{order.shipping_instructions}\n\n" if order.shipping_instructions else "")
            + "Please pack and drop off as soon as possible."
        ),
    )
    # Move order state to label_processing → shipped
    if order.state == Order.State.PAID_ESCROW:
        Order.objects.filter(pk=order.pk).update(
            state=Order.State.LABEL_PROCESSING,
            updated_at=timezone.now(),
        )


def _notify_buyer_shipped(order):
    from .notifications import send_order_email
    tracking_line = ""
    if order.tracking_url:
        tracking_line = f"\nTrack your shipment: {order.tracking_url}"
    elif order.tracking_number:
        tracking_line = f"\nTracking number: {order.tracking_number} ({order.tracking_carrier})"
    send_order_email(
        to_email=order.buyer.email,
        subject=f"Your order has shipped — Order #{order.id} — Partbridge",
        body=(
            f"Great news! Order #{order.id} has been shipped.\n\n"
            f"Item: {order.vehicle_part.label}\n"
            + tracking_line
            + "\n\nYou can view your order in your Purchases page."
        ),
    )
    if order.state in (Order.State.PAID_ESCROW, Order.State.LABEL_PROCESSING, Order.State.SELLER_CONFIRMED):
        Order.objects.filter(pk=order.pk).update(
            state=Order.State.SHIPPED,
            updated_at=timezone.now(),
        )


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "seller", "buyer", "rating", "created_at")
    search_fields = ("seller__email", "buyer__email", "order__vehicle_part__label")


@admin.register(SellerVerification)
class SellerVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "documents_review_status",
        "payout_ready",
        "connect_onboarded_at",
        "documents_approved_at",
        "updated_at",
    )
    search_fields = ("user__email", "stripe_account_id")
    readonly_fields = ("documents_submitted_at", "created_at", "updated_at", "payout_ready")
    fieldsets = (
        (None, {"fields": ("user", "stripe_account_id", "connect_onboarded_at")}),
        (
            "Identity documents",
            {
                "fields": (
                    "document_id_front",
                    "document_id_back",
                    "document_selfie",
                    "documents_submitted_at",
                    "documents_review_status",
                    "documents_approved_at",
                )
            },
        ),
        ("Legacy", {"fields": ("id_verified_at", "ssn_verified_at", "first_sale_at")}),
    )

    def save_model(self, request, obj, form, change):
        prev_status = None
        if change and obj.pk:
            prev_status = (
                SellerVerification.objects.filter(pk=obj.pk)
                .values_list("documents_review_status", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.documents_review_status == SellerVerification.DocumentsReviewStatus.APPROVED:
            if not obj.documents_approved_at:
                obj.documents_approved_at = timezone.now()
                obj.save(update_fields=["documents_approved_at", "updated_at"])
            if prev_status != SellerVerification.DocumentsReviewStatus.APPROVED:
                try:
                    send_seller_verification_approved_email(obj)
                except Exception:
                    pass


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "vehicle_part", "quantity", "shipping_mode", "shipping_quoted_usd", "updated_at")
    search_fields = ("user__email", "vehicle_part__label")
