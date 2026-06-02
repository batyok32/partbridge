from __future__ import annotations

from rest_framework import serializers

from .models import CartItem, Dispute, DisputeMessage, Order, OrderItem, Payment, SellerReview, ShippingRequest


class CartItemSerializer(serializers.ModelSerializer):
    item_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ("id", "user", "item", "item_detail", "added_at")
        read_only_fields = ("id", "user", "added_at")

    def get_item_detail(self, obj):
        from parts.serializers import ItemListSerializer
        return ItemListSerializer(obj.item).data


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("id", "order", "item", "price_at_purchase", "item_snapshot", "selected_options")
        read_only_fields = ("id",)


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "buyer", "shipping_address", "status", "subtotal",
            "shipping_cost", "total", "vehicle_snapshot", "order_items", "placed_at",
        )
        read_only_fields = ("id", "buyer", "placed_at")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id", "order", "status", "amount", "refunded_amount",
            "provider", "provider_reference", "payment_method",
            "paid_at", "refunded_at", "created_at",
        )
        read_only_fields = ("id", "created_at")


class ShippingRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRequest
        fields = (
            "id", "order_item", "seller", "method", "shipping_size",
            "origin_zip", "dest_zip", "quoted_cost", "actual_cost",
            "carrier", "tracking_number", "label_url", "estimated_days",
            "is_delivered", "delivered_at", "created_at",
        )
        read_only_fields = ("id", "created_at")


class DisputeMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeMessage
        fields = ("id", "dispute", "sender", "sender_role", "body", "attachment_url", "sent_at")
        read_only_fields = ("id", "sender", "sent_at")


class DisputeSerializer(serializers.ModelSerializer):
    messages = DisputeMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Dispute
        fields = (
            "id", "order_item", "buyer", "seller", "reason", "description",
            "status", "resolution", "resolved_by", "refund_amount",
            "return_required", "opened_at", "resolved_at", "messages",
        )
        read_only_fields = ("id", "buyer", "seller", "opened_at", "resolved_at", "resolved_by")


class SellerReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerReview
        fields = ("id", "seller", "buyer", "order_item", "rating", "body", "created_at")
        read_only_fields = ("id", "buyer", "seller", "created_at")
