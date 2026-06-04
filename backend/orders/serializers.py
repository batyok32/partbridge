from __future__ import annotations

from rest_framework import serializers

from .models import CartBundle, CartItem, Dispute, DisputeMessage, Order, OrderItem, Payment, SellerReview, ShippingRequest


class CartItemSerializer(serializers.ModelSerializer):
    item_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ("id", "user", "item", "shipping_mode", "item_detail", "added_at")
        read_only_fields = ("id", "user", "added_at")

    def get_item_detail(self, obj):
        from parts.serializers import ItemListSerializer
        return ItemListSerializer(obj.item, context=self.context).data


class CartBundleSerializer(serializers.ModelSerializer):
    bundle_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartBundle
        fields = ("id", "bundle", "shipping_mode", "bundle_detail", "added_at")
        read_only_fields = ("id", "added_at")

    def get_bundle_detail(self, obj):
        from bundles.serializers import BundleSearchSerializer
        return BundleSearchSerializer(obj.bundle, context=self.context).data


class OrderItemSerializer(serializers.ModelSerializer):
    item_photo_url = serializers.SerializerMethodField()
    tracking_number = serializers.SerializerMethodField()
    carrier = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id", "order", "item", "price_at_purchase", "item_snapshot", "selected_options",
            "item_photo_url", "tracking_number", "carrier",
        )
        read_only_fields = ("id",)

    def get_item_photo_url(self, obj):
        if obj.item:
            photo = obj.item.photos.filter(is_primary=True).first() or obj.item.photos.first()
            return photo.url if photo else None
        return None

    def get_tracking_number(self, obj):
        req = obj.shipping_requests.first()
        return req.tracking_number if req else None

    def get_carrier(self, obj):
        req = obj.shipping_requests.first()
        return req.carrier if req else None


class OrderItemDetailSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField(source="item.id", read_only=True, allow_null=True)
    item_title = serializers.SerializerMethodField()
    item_photo_url = serializers.SerializerMethodField()
    seller_id = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    shipping = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    bundle_id = serializers.IntegerField(source="bundle.id", read_only=True, allow_null=True)
    bundle_name = serializers.SerializerMethodField()
    dispute_status = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id", "item_id", "price_at_purchase", "item_snapshot", "selected_options",
            "item_title", "item_photo_url", "seller_id", "seller_name", "shipping", "review",
            "bundle_id", "bundle_name", "dispute_status",
        )

    def get_item_title(self, obj):
        if obj.item:
            return obj.item.title
        return (obj.item_snapshot or {}).get("title", "")

    def get_item_photo_url(self, obj):
        if obj.item:
            photo = obj.item.photos.filter(is_primary=True).first() or obj.item.photos.first()
            return photo.url if photo else None
        return (obj.item_snapshot or {}).get("primary_photo_url")

    def get_seller_id(self, obj):
        try:
            return obj.item.vehicle.seller_id
        except AttributeError:
            return None

    def get_seller_name(self, obj):
        try:
            s = obj.item.vehicle.seller
            name = f"{s.first_name} {s.last_name}".strip()
            return name or s.email.split("@")[0]
        except AttributeError:
            return ""

    def get_shipping(self, obj):
        req = obj.shipping_requests.first()
        if not req:
            return None
        return {
            "tracking_number": req.tracking_number,
            "carrier": req.carrier,
            "is_delivered": req.is_delivered,
            "method": req.method,
            "estimated_days": req.estimated_days,
        }

    def get_review(self, obj):
        review = obj.seller_reviews.first()
        if not review:
            return None
        return {"id": review.id, "rating": review.rating, "body": review.body}

    def get_bundle_name(self, obj):
        return obj.bundle.name if obj.bundle_id else None

    def get_dispute_status(self, obj):
        dispute = obj.disputes.first()
        return dispute.status if dispute else None


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    has_open_dispute = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "buyer", "shipping_address", "status", "subtotal",
            "shipping_cost", "tax", "total", "vehicle_snapshot", "order_items", "placed_at",
            "has_open_dispute",
        )
        read_only_fields = ("id", "buyer", "placed_at")

    def get_has_open_dispute(self, obj):
        open_statuses = {"open", "under_review"}
        for oi in obj.order_items.all():
            if any(d.status in open_statuses for d in oi.disputes.all()):
                return True
        return False


class OrderDetailSerializer(serializers.ModelSerializer):
    order_items = OrderItemDetailSerializer(many=True, read_only=True)
    shipping_address_details = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "buyer", "status", "subtotal", "shipping_cost", "tax", "total",
            "placed_at", "order_items", "shipping_address_details", "payment",
        )
        read_only_fields = ("id", "buyer", "placed_at")

    def get_shipping_address_details(self, obj):
        try:
            addr = obj.shipping_address
            return {
                "full_name": addr.full_name,
                "line1": addr.line1,
                "line2": addr.line2,
                "city": addr.city,
                "state": addr.state,
                "zip": addr.zip,
            }
        except Exception:
            return None

    def get_payment(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        if not payment:
            return None
        return {"status": payment.status, "amount": str(payment.amount)}


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
    sender_display = serializers.SerializerMethodField()

    class Meta:
        model = DisputeMessage
        fields = ("id", "dispute", "sender", "sender_role", "sender_display", "body", "attachment_url", "sent_at")
        read_only_fields = ("id", "sender", "sent_at")

    def get_sender_display(self, obj):
        try:
            name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
            return name or obj.sender.email.split("@")[0]
        except Exception:
            return ""


class DisputeSerializer(serializers.ModelSerializer):
    messages = DisputeMessageSerializer(many=True, read_only=True)
    item_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = (
            "id", "order_item", "buyer", "seller", "reason", "description",
            "status", "resolution", "resolved_by", "refund_amount",
            "return_required", "opened_at", "resolved_at", "messages", "item_snapshot",
        )
        read_only_fields = ("id", "buyer", "seller", "opened_at", "resolved_at", "resolved_by")

    def get_item_snapshot(self, obj):
        try:
            snap = obj.order_item.item_snapshot or {}
            if not snap and obj.order_item.item:
                item = obj.order_item.item
                snap = {"title": item.title, "price": str(item.price)}
            return snap
        except Exception:
            return {}


class SellerReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerReview
        fields = ("id", "seller", "buyer", "order_item", "rating", "body", "created_at")
        read_only_fields = ("id", "buyer", "seller", "created_at")


# ─── Seller-facing serializers ────────────────────────────────────────────────

class SellerSaleItemSerializer(serializers.ModelSerializer):
    item_title = serializers.SerializerMethodField()
    item_id = serializers.IntegerField(source="item.id", read_only=True, allow_null=True)
    shipping_size = serializers.SerializerMethodField()
    tracking_number = serializers.SerializerMethodField()
    carrier = serializers.SerializerMethodField()
    is_delivered = serializers.SerializerMethodField()
    shipping_request_id = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id", "item_id", "item_title", "price_at_purchase",
            "shipping_size", "tracking_number", "carrier",
            "is_delivered", "shipping_request_id",
        )

    def get_item_title(self, obj):
        return obj.item.title if obj.item else (obj.item_snapshot or {}).get("title", "")

    def get_shipping_size(self, obj):
        return obj.item.shipping_size if obj.item else (obj.item_snapshot or {}).get("shipping_size", "")

    def get_tracking_number(self, obj):
        sr = obj.shipping_requests.first()
        return sr.tracking_number if sr else ""

    def get_carrier(self, obj):
        sr = obj.shipping_requests.first()
        return sr.carrier if sr else ""

    def get_is_delivered(self, obj):
        sr = obj.shipping_requests.first()
        return sr.is_delivered if sr else False

    def get_shipping_request_id(self, obj):
        sr = obj.shipping_requests.first()
        return sr.id if sr else None


class SellerSaleSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()
    shipping_address_text = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "status", "total", "placed_at", "buyer_name", "shipping_address_text", "items")

    def get_items(self, obj):
        seller = self.context.get("seller")
        ois = list(obj.order_items.all())
        if seller:
            ois = [oi for oi in ois if oi.item and oi.item.vehicle and oi.item.vehicle.seller_id == seller.id]
        return SellerSaleItemSerializer(ois, many=True).data

    def get_buyer_name(self, obj):
        return obj.buyer.first_name or obj.buyer.email.split("@")[0]

    def get_shipping_address_text(self, obj):
        try:
            addr = obj.shipping_address
            return f"{addr.city}, {addr.state} {addr.zip}"
        except Exception:
            return ""


# ─── Seller order detail ──────────────────────────────────────────────────────

class SellerOrderDetailItemSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField(source="item.id", read_only=True, allow_null=True)
    item_title = serializers.SerializerMethodField()
    item_photo_url = serializers.SerializerMethodField()
    condition = serializers.SerializerMethodField()
    vehicle_info = serializers.SerializerMethodField()
    shipping_size = serializers.SerializerMethodField()
    tracking_number = serializers.SerializerMethodField()
    carrier = serializers.SerializerMethodField()
    is_delivered = serializers.SerializerMethodField()
    shipping_request_id = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id", "item_id", "item_title", "item_photo_url", "condition",
            "price_at_purchase", "vehicle_info", "shipping_size",
            "tracking_number", "carrier", "is_delivered", "shipping_request_id",
        )

    def get_item_title(self, obj):
        return obj.item.title if obj.item else (obj.item_snapshot or {}).get("title", "")

    def get_item_photo_url(self, obj):
        if obj.item:
            photo = obj.item.photos.filter(is_primary=True).first() or obj.item.photos.first()
            return photo.url if photo else None
        return (obj.item_snapshot or {}).get("primary_photo_url")

    def get_condition(self, obj):
        if obj.item:
            return obj.item.condition
        return (obj.item_snapshot or {}).get("condition")

    def get_vehicle_info(self, obj):
        snap = obj.item_snapshot or {}
        if obj.item and obj.item.vehicle:
            v = obj.item.vehicle
            try:
                make = v.generation.car_model.make.name if v.generation else ""
                model = v.generation.car_model.name if v.generation else ""
            except Exception:
                make = ""
                model = ""
            return {"year": v.year, "make": make, "model": model, "vin": v.vin}
        return {
            "year": snap.get("vehicle_year"),
            "make": snap.get("vehicle_make"),
            "model": snap.get("vehicle_model"),
            "vin": snap.get("vehicle_vin"),
        }

    def get_shipping_size(self, obj):
        return obj.item.shipping_size if obj.item else (obj.item_snapshot or {}).get("shipping_size", "")

    def get_tracking_number(self, obj):
        sr = obj.shipping_requests.first()
        return sr.tracking_number if sr else ""

    def get_carrier(self, obj):
        sr = obj.shipping_requests.first()
        return sr.carrier if sr else ""

    def get_is_delivered(self, obj):
        sr = obj.shipping_requests.first()
        return sr.is_delivered if sr else False

    def get_shipping_request_id(self, obj):
        sr = obj.shipping_requests.first()
        return sr.id if sr else None


class SellerOrderDetailSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    buyer_name = serializers.SerializerMethodField()
    ship_to = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "status", "subtotal", "shipping_cost", "tax", "total",
            "placed_at", "items", "buyer_name", "ship_to", "payment_status",
        )

    def get_items(self, obj):
        seller = self.context.get("seller")
        ois = list(obj.order_items.all())
        if seller:
            ois = [oi for oi in ois if oi.item and oi.item.vehicle and oi.item.vehicle.seller_id == seller.id]
        return SellerOrderDetailItemSerializer(ois, many=True).data

    def get_buyer_name(self, obj):
        return obj.buyer.first_name or obj.buyer.email.split("@")[0]

    def get_ship_to(self, obj):
        try:
            addr = obj.shipping_address
            return {
                "full_name": addr.full_name,
                "line1": addr.line1,
                "line2": addr.line2 or "",
                "city": addr.city,
                "state": addr.state,
                "zip": addr.zip,
            }
        except Exception:
            return None

    def get_payment_status(self, obj):
        p = obj.payments.order_by("-created_at").first()
        return p.status if p else None
