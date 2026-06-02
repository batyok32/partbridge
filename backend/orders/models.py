from __future__ import annotations

from django.conf import settings
from django.db import models


class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    item = models.ForeignKey(
        "parts.Item",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "item")]

    def __str__(self):
        return f"CartItem user={self.user_id} item={self.item_id}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders_bought",
    )
    shipping_address = models.ForeignKey(
        "accounts.ShippingAddress",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vehicle_snapshot = models.JSONField(default=dict, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-placed_at"]

    def __str__(self):
        return f"Order #{self.id} status={self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items")
    item = models.ForeignKey("parts.Item", on_delete=models.PROTECT, related_name="order_items")
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    item_snapshot = models.JSONField(default=dict, blank=True)
    selected_options = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"OrderItem order={self.order_id} item={self.item_id}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        PARTIAL_REFUND = "partial_refund", "Partial Refund"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    provider = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} order={self.order_id} status={self.status}"


class ShippingRequest(models.Model):
    class Method(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        PARCEL = "parcel", "Parcel"
        FREIGHT = "freight", "Freight"

    class ShippingSize(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"
        XL = "xl", "XL"

    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="shipping_requests")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shipping_requests",
    )
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.PARCEL)
    shipping_size = models.CharField(max_length=8, choices=ShippingSize.choices, default=ShippingSize.MEDIUM)
    origin_zip = models.CharField(max_length=16)
    dest_zip = models.CharField(max_length=16)
    quoted_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    carrier = models.CharField(max_length=64, blank=True)
    tracking_number = models.CharField(max_length=128, blank=True)
    label_url = models.CharField(max_length=1024, blank=True)
    estimated_days = models.PositiveSmallIntegerField(null=True, blank=True)
    is_delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ShippingRequest #{self.id} order_item={self.order_item_id}"


class Dispute(models.Model):
    class Reason(models.TextChoices):
        NOT_AS_DESCRIBED = "not_as_described", "Not As Described"
        WRONG_PART = "wrong_part", "Wrong Part"
        NOT_RECEIVED = "not_received", "Not Received"
        DAMAGED = "damaged", "Damaged"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_REVIEW = "under_review", "Under Review"
        RESOLVED_REFUND = "resolved_refund", "Resolved — Refund"
        RESOLVED_RETURN = "resolved_return", "Resolved — Return"
        RESOLVED_NO_ACTION = "resolved_no_action", "Resolved — No Action"
        CLOSED = "closed", "Closed"

    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="disputes")
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disputes_as_buyer",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disputes_as_seller",
    )
    reason = models.CharField(max_length=24, choices=Reason.choices)
    description = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="disputes_resolved",
    )
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    return_required = models.BooleanField(default=False)
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"Dispute #{self.id} status={self.status}"


class DisputeMessage(models.Model):
    class SenderRole(models.TextChoices):
        BUYER = "buyer", "Buyer"
        SELLER = "seller", "Seller"
        SUPPORT = "support", "Support"

    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dispute_messages",
    )
    sender_role = models.CharField(max_length=8, choices=SenderRole.choices)
    body = models.TextField()
    attachment_url = models.CharField(max_length=1024, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"DisputeMessage #{self.id} dispute={self.dispute_id}"


class SellerReview(models.Model):
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_reviews_received",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_reviews_written",
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="seller_reviews",
    )
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SellerReview #{self.id} {self.rating}★"
