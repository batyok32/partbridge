from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class SellerVerification(models.Model):
    """Kept for data continuity; verification is no longer required to sell."""

    class DocumentsReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_verification",
    )
    stripe_account_id = models.CharField(max_length=128, blank=True)
    connect_onboarded_at = models.DateTimeField(null=True, blank=True)
    id_verified_at = models.DateTimeField(null=True, blank=True)
    ssn_verified_at = models.DateTimeField(null=True, blank=True)
    first_sale_at = models.DateTimeField(null=True, blank=True)
    document_id_front = models.ImageField(upload_to="seller_verify/%Y/%m/", blank=True)
    document_id_back = models.ImageField(upload_to="seller_verify/%Y/%m/", blank=True)
    document_selfie = models.ImageField(upload_to="seller_verify/%Y/%m/", blank=True)
    documents_submitted_at = models.DateTimeField(null=True, blank=True)
    documents_review_status = models.CharField(
        max_length=16,
        choices=DocumentsReviewStatus.choices,
        default=DocumentsReviewStatus.PENDING,
    )
    documents_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SellerVerification<{self.user_id}>"

    @property
    def payout_ready(self) -> bool:
        return bool(self.connect_onboarded_at and self.documents_approved_at)


class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        CASH = "cash", "Cash (test)"

    class State(models.TextChoices):
        PAYMENT_PENDING = "payment_pending", "Awaiting payment"
        PAID_ESCROW = "paid_escrow", "Paid — awaiting shipment"
        SELLER_CONFIRMED = "seller_confirmed", "Seller confirmed"
        LABEL_PROCESSING = "label_processing", "Shipping label processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        REFUND_PENDING = "refund_pending", "Refund pending"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"
        HOLD = "hold", "On hold"
        AVAILABLE_FOR_PAYOUT = "available_for_payout", "Available for payout"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_bought",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_sold",
    )
    vehicle_part = models.ForeignKey(
        "vehicles.VehiclePart",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    source_quote_id = models.PositiveIntegerField(null=True, blank=True)
    buyer_state = models.CharField(max_length=2, blank=True)
    buyer_zip = models.CharField(max_length=10, blank=True)
    # Full shipping address for label generation
    buyer_name = models.CharField(max_length=128, blank=True)
    buyer_address_line1 = models.CharField(max_length=255, blank=True)
    buyer_address_line2 = models.CharField(max_length=255, blank=True)
    buyer_city = models.CharField(max_length=128, blank=True)
    buyer_notes = models.TextField(blank=True)
    source_cart_item = models.ForeignKey(
        "CartItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders_from_checkout",
    )
    shipping_mode = models.CharField(max_length=24, blank=True)
    shipping_amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Shipping amount — charged separately after purchase.",
    )
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="usd")
    state = models.CharField(max_length=32, choices=State.choices, default=State.PAYMENT_PENDING)
    fitment_verified_at = models.DateTimeField()
    return_policy_ack_at = models.DateTimeField()

    payment_method = models.CharField(
        max_length=16,
        choices=PaymentMethod.choices,
        default=PaymentMethod.STRIPE,
    )
    stripe_payment_intent_id = models.CharField(max_length=128, blank=True)
    stripe_client_secret = models.CharField(max_length=255, blank=True)

    # Shipping management (manual — admin uploads label)
    shipping_instructions = models.TextField(
        blank=True,
        help_text="Instructions to the seller from admin (how to package/ship).",
    )
    shipping_label_url = models.URLField(blank=True, help_text="Label PDF uploaded by admin.")
    tracking_url = models.URLField(blank=True, help_text="Carrier tracking URL for buyer.")
    tracking_carrier = models.CharField(max_length=64, blank=True)
    tracking_number = models.CharField(max_length=128, blank=True)
    tracking_status = models.CharField(max_length=64, blank=True)
    last_tracking_at = models.DateTimeField(null=True, blank=True)
    shipping_label_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shipping_paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When buyer paid for shipping separately.",
    )

    payout_blocked = models.BooleanField(default=False)
    payout_block_reason = models.CharField(max_length=255, blank=True)
    payout_block_deadline = models.DateTimeField(null=True, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    seller_confirmation_due_at = models.DateTimeField(null=True, blank=True)
    seller_confirmed_at = models.DateTimeField(null=True, blank=True)
    pre_ship_photos = models.JSONField(default=list, blank=True)
    pre_ship_checklist_complete_at = models.DateTimeField(null=True, blank=True)
    package_length_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_width_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_height_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    package_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dimensions_confirmed_at = models.DateTimeField(null=True, blank=True)
    insurance_opt_in = models.BooleanField(default=False)

    refund_requested_at = models.DateTimeField(null=True, blank=True)
    refund_request_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    hold_until = models.DateTimeField(null=True, blank=True)
    released_to_seller_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    vehicle_snapshot = models.JSONField(default=dict, blank=True)
    delivery_photos = models.JSONField(default=list, blank=True)
    delivery_notes = models.TextField(blank=True)
    funds_held_until_delivered = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Order<{self.id}> part={self.vehicle_part_id} state={self.state}"

    def enter_escrow(self) -> None:
        now = timezone.now()
        self.state = self.State.PAID_ESCROW
        self.paid_at = now
        self.seller_confirmed_at = now
        self.seller_confirmation_due_at = None
        self.hold_until = now + timedelta(days=3)
        self.save(
            update_fields=[
                "state",
                "paid_at",
                "seller_confirmed_at",
                "seller_confirmation_due_at",
                "hold_until",
                "updated_at",
            ]
        )

    @property
    def buyer_display_state(self) -> str:
        """Three-step buyer-facing status: Paid → Shipped → Completed."""
        if self.state in (self.State.PAYMENT_PENDING,):
            return "awaiting_payment"
        if self.state in (self.State.DELIVERED, self.State.AVAILABLE_FOR_PAYOUT):
            return "completed"
        if self.state == self.State.SHIPPED:
            return "shipped"
        return "paid"


class CartItem(models.Model):
    class ShippingMode(models.TextChoices):
        STANDARD = "standard", "Standard"
        NEXT_DAY = "next_day", "Next day"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    vehicle_part = models.ForeignKey(
        "vehicles.VehiclePart",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveSmallIntegerField(default=1)
    shipping_mode = models.CharField(
        max_length=24,
        choices=ShippingMode.choices,
        default=ShippingMode.STANDARD,
    )
    buyer_zip_snapshot = models.CharField(max_length=16, blank=True)
    shipping_quoted_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    buyer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle_part"],
                name="uniq_cart_item_user_vehicle_part",
            )
        ]

    def __str__(self):
        return f"CartItem<{self.user_id}:{self.vehicle_part_id}>"


class SellerReview(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="seller_review",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_reviews_written",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_reviews_received",
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SellerReview<{self.order_id}> {self.rating}★"
