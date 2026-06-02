from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import serializers

from .dimensions import cm_to_inches, inches_to_cm, kg_to_pounds, pounds_to_kg
from .models import CartItem, Order, SellerReview
from .payments import stripe_configured
from .tracking_ui import build_tracking_steps


class CheckoutIntentSerializer(serializers.Serializer):
    vehicle_part_id = serializers.IntegerField()
    fitment_verified = serializers.BooleanField()
    return_policy_read = serializers.BooleanField()
    shipping_mode = serializers.ChoiceField(
        choices=("standard", "next_day"),
        default="standard",
    )
    buyer_state = serializers.CharField(required=False, allow_blank=True, max_length=2)
    buyer_zip = serializers.CharField(required=False, allow_blank=True, max_length=10)
    payment_method = serializers.ChoiceField(choices=("stripe", "cash"), default="stripe", required=False)

    def validate(self, attrs):
        if not attrs.get("fitment_verified"):
            raise serializers.ValidationError(
                {"fitment_verified": "You must confirm fitment before checkout."}
            )
        if not attrs.get("return_policy_read"):
            raise serializers.ValidationError(
                {"return_policy_read": "You must acknowledge return policy before checkout."}
            )
        if not (attrs.get("buyer_zip") or "").strip():
            raise serializers.ValidationError({"buyer_zip": "ZIP is required for delivery."})
        return attrs


class CheckoutIntentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "state",
            "amount_usd",
            "shipping_amount_usd",
            "shipping_mode",
            "currency",
            "stripe_payment_intent_id",
            "stripe_client_secret",
            "payout_blocked",
            "payout_block_reason",
            "payout_block_deadline",
            "created_at",
            "payment_method",
        )


class ConfirmPaymentSerializer(serializers.Serializer):
    payment_intent_id = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=("succeeded", "failed"), default="succeeded")


class CartCheckoutPreviewSerializer(serializers.Serializer):
    buyer_state = serializers.CharField(required=False, allow_blank=True, max_length=2)
    buyer_zip = serializers.CharField(required=False, allow_blank=True, max_length=16)


class SellerConfirmSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Confirmation must be true.")
        return value


class PreShipChecklistSerializer(serializers.Serializer):
    pre_ship_photos = serializers.ListField(child=serializers.URLField(), min_length=0, max_length=12, required=False, default=list)
    package_length_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_width_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_height_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_weight_lb = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.25"))
    overage_acknowledged = serializers.BooleanField(default=True)
    insurance_opt_in = serializers.BooleanField(default=False)

    def validate(self, attrs):
        attrs["package_length_cm"] = inches_to_cm(attrs.pop("package_length_in"))
        attrs["package_width_cm"] = inches_to_cm(attrs.pop("package_width_in"))
        attrs["package_height_cm"] = inches_to_cm(attrs.pop("package_height_in"))
        attrs["package_weight_kg"] = pounds_to_kg(attrs.pop("package_weight_lb"))
        return attrs


class ShippingPlanSerializer(serializers.Serializer):
    package_length_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_width_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_height_in = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.5"))
    package_weight_lb = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.25"))
    insurance_opt_in = serializers.BooleanField(default=False)
    overage_acknowledged = serializers.BooleanField(default=True)

    def validate(self, attrs):
        attrs["package_length_cm"] = inches_to_cm(attrs.pop("package_length_in"))
        attrs["package_width_cm"] = inches_to_cm(attrs.pop("package_width_in"))
        attrs["package_height_cm"] = inches_to_cm(attrs.pop("package_height_in"))
        attrs["package_weight_kg"] = pounds_to_kg(attrs.pop("package_weight_lb"))
        return attrs


class PurchaseLabelSerializer(serializers.Serializer):
    carrier = serializers.CharField(required=False, allow_blank=True, max_length=64)


class TrackingUpdateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(required=False)
    tracking_number = serializers.CharField(required=False, allow_blank=True, max_length=128)
    status = serializers.CharField(max_length=64)
    carrier = serializers.CharField(required=False, allow_blank=True, max_length=64)
    at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if not attrs.get("order_id") and not attrs.get("tracking_number"):
            raise serializers.ValidationError("Provide order_id or tracking_number.")
        return attrs


class CartItemSerializer(serializers.ModelSerializer):
    vehicle_part_label = serializers.CharField(source="vehicle_part.label", read_only=True)
    vehicle_part_price = serializers.DecimalField(source="vehicle_part.price", max_digits=10, decimal_places=2, read_only=True)
    listing_state = serializers.CharField(source="vehicle_part.listing_state", read_only=True)
    listing_state_effective = serializers.CharField(source="vehicle_part.effective_listing_state", read_only=True)
    vehicle_vin = serializers.CharField(source="vehicle_part.vehicle.vin", read_only=True)
    vehicle_year = serializers.IntegerField(source="vehicle_part.vehicle.year", read_only=True, allow_null=True)
    vehicle_make = serializers.CharField(source="vehicle_part.vehicle.make", read_only=True, allow_blank=True)
    vehicle_model = serializers.CharField(source="vehicle_part.vehicle.model", read_only=True, allow_blank=True)
    pickup_allowed = serializers.BooleanField(source="vehicle_part.vehicle.pickup_allowed", read_only=True)
    pickup_zip = serializers.CharField(source="vehicle_part.vehicle.location_zip", read_only=True, allow_blank=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "vehicle_part",
            "vehicle_part_label",
            "vehicle_part_price",
            "listing_state",
            "listing_state_effective",
            "vehicle_vin",
            "vehicle_year",
            "vehicle_make",
            "vehicle_model",
            "pickup_allowed",
            "pickup_zip",
            "quantity",
            "shipping_mode",
            "buyer_zip_snapshot",
            "shipping_quoted_usd",
            "buyer_notes",
            "created_at",
        )


class CartAddSerializer(serializers.Serializer):
    vehicle_part_id = serializers.IntegerField()
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=5, default=1)
    shipping_mode = serializers.ChoiceField(choices=("standard", "next_day"), default="standard")
    buyer_zip = serializers.CharField(required=False, allow_blank=True, max_length=16)
    buyer_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class CartItemUpdateSerializer(serializers.Serializer):
    shipping_mode = serializers.ChoiceField(choices=("standard", "next_day", "pickup"), required=False)
    buyer_zip = serializers.CharField(required=False, allow_blank=True, max_length=16)
    buyer_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class OrderSerializer(serializers.ModelSerializer):
    vehicle_part_label = serializers.CharField(source="vehicle_part.label", read_only=True)
    stripe_payment_intent_id = serializers.SerializerMethodField()
    stripe_client_secret = serializers.SerializerMethodField()
    stripe_checkout_available = serializers.SerializerMethodField()
    tracking_steps = serializers.SerializerMethodField()
    vehicle_vin = serializers.SerializerMethodField()
    vehicle_year = serializers.SerializerMethodField()
    vehicle_make = serializers.SerializerMethodField()
    vehicle_model = serializers.SerializerMethodField()
    package_length_in = serializers.SerializerMethodField()
    package_width_in = serializers.SerializerMethodField()
    package_height_in = serializers.SerializerMethodField()
    package_weight_lb = serializers.SerializerMethodField()
    seller_display_name = serializers.SerializerMethodField()
    seller_email = serializers.SerializerMethodField()
    seller_rating_avg = serializers.SerializerMethodField()
    seller_rating_count = serializers.SerializerMethodField()
    my_seller_review = serializers.SerializerMethodField()
    buyer_shipping_summary = serializers.SerializerMethodField()
    payment_summary = serializers.SerializerMethodField()
    part_subtotal_usd = serializers.SerializerMethodField()
    seller_payout_summary = serializers.SerializerMethodField()
    buyer_display_state = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "state",
            "buyer_display_state",
            "buyer",
            "seller",
            "vehicle_part",
            "vehicle_part_label",
            "vehicle_snapshot",
            "vehicle_vin",
            "vehicle_year",
            "vehicle_make",
            "vehicle_model",
            "source_quote_id",
            "shipping_mode",
            "shipping_amount_usd",
            "amount_usd",
            "currency",
            "payment_method",
            "buyer_notes",
            "buyer_name",
            "buyer_address_line1",
            "buyer_address_line2",
            "buyer_city",
            "buyer_state",
            "buyer_zip",
            "fitment_verified_at",
            "return_policy_ack_at",
            "payout_blocked",
            "payout_block_reason",
            "payout_block_deadline",
            "paid_at",
            "seller_confirmation_due_at",
            "seller_confirmed_at",
            "pre_ship_checklist_complete_at",
            "pre_ship_photos",
            "package_length_cm",
            "package_width_cm",
            "package_height_cm",
            "package_weight_kg",
            "package_length_in",
            "package_width_in",
            "package_height_in",
            "package_weight_lb",
            "shipping_label_url",
            "shipping_label_cost_usd",
            "shipping_instructions",
            "tracking_url",
            "tracking_carrier",
            "tracking_number",
            "tracking_status",
            "last_tracking_at",
            "shipping_paid_at",
            "delivered_at",
            "delivery_photos",
            "delivery_notes",
            "hold_until",
            "funds_held_until_delivered",
            "released_to_seller_at",
            "refunded_at",
            "refund_request_reason",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "tracking_steps",
            "stripe_payment_intent_id",
            "stripe_client_secret",
            "stripe_checkout_available",
            "seller_display_name",
            "seller_email",
            "seller_rating_avg",
            "seller_rating_count",
            "my_seller_review",
            "buyer_shipping_summary",
            "payment_summary",
            "part_subtotal_usd",
            "seller_payout_summary",
        )

    def _buyer_can_pay_pending(self, obj: Order) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        if obj.buyer_id != request.user.id:
            return False
        return obj.state == Order.State.PAYMENT_PENDING

    def get_stripe_payment_intent_id(self, obj: Order):
        if not self._buyer_can_pay_pending(obj):
            return None
        return (obj.stripe_payment_intent_id or "").strip() or None

    def get_stripe_client_secret(self, obj: Order):
        if not self._buyer_can_pay_pending(obj):
            return None
        return (obj.stripe_client_secret or "").strip() or None

    def get_stripe_checkout_available(self, obj: Order) -> bool:
        if getattr(obj, "payment_method", None) == Order.PaymentMethod.CASH:
            return False
        return bool(self._buyer_can_pay_pending(obj) and stripe_configured())

    def get_tracking_steps(self, obj: Order):
        return build_tracking_steps(obj)

    def _veh_snap(self, obj: Order) -> dict:
        return obj.vehicle_snapshot if isinstance(obj.vehicle_snapshot, dict) else {}

    def get_vehicle_vin(self, obj: Order):
        s = self._veh_snap(obj)
        return (s.get("vin") or getattr(obj.vehicle_part.vehicle, "vin", "") or "").strip() or None

    def get_vehicle_year(self, obj: Order):
        s = self._veh_snap(obj)
        y = s.get("year")
        if y is not None:
            return y
        return obj.vehicle_part.vehicle.year

    def get_vehicle_make(self, obj: Order):
        s = self._veh_snap(obj)
        return (s.get("make") or obj.vehicle_part.vehicle.make or "").strip() or None

    def get_vehicle_model(self, obj: Order):
        s = self._veh_snap(obj)
        return (s.get("model") or obj.vehicle_part.vehicle.model or "").strip() or None

    def get_package_length_in(self, obj: Order):
        return str(cm_to_inches(obj.package_length_cm)) if obj.package_length_cm is not None else None

    def get_package_width_in(self, obj: Order):
        return str(cm_to_inches(obj.package_width_cm)) if obj.package_width_cm is not None else None

    def get_package_height_in(self, obj: Order):
        return str(cm_to_inches(obj.package_height_cm)) if obj.package_height_cm is not None else None

    def get_package_weight_lb(self, obj: Order):
        return str(kg_to_pounds(obj.package_weight_kg)) if obj.package_weight_kg is not None else None

    def get_seller_display_name(self, obj: Order):
        u = getattr(obj, "seller", None)
        if u is None:
            return None
        return (getattr(u, "name", None) or u.get_full_name() or u.email or "").strip() or None

    def get_seller_email(self, obj: Order):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        if request.user.id != obj.buyer_id:
            return None
        return getattr(obj.seller, "email", None)

    def _ratings_for_seller(self, seller_id: int) -> tuple[float | None, int]:
        cache = self.context.get("seller_ratings_cache") or {}
        if seller_id in cache:
            avg, cnt = cache[seller_id]
            return avg, cnt
        row = SellerReview.objects.filter(seller_id=seller_id).aggregate(a=Avg("rating"), c=Count("id"))
        avg = row["a"]
        cnt = row["c"] or 0
        return (float(avg) if avg is not None else None, int(cnt))

    def get_seller_rating_avg(self, obj: Order):
        avg, _ = self._ratings_for_seller(obj.seller_id)
        return round(avg, 2) if avg is not None else None

    def get_seller_rating_count(self, obj: Order):
        _, cnt = self._ratings_for_seller(obj.seller_id)
        return cnt

    def get_my_seller_review(self, obj: Order):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        if request.user.id != obj.buyer_id:
            return None
        rev = SellerReview.objects.filter(order_id=obj.id).first()
        if rev is None:
            return None
        return {
            "rating": rev.rating,
            "comment": rev.comment,
            "created_at": timezone.localtime(rev.created_at).isoformat(),
        }

    def get_buyer_shipping_summary(self, obj: Order):
        parts = [p for p in (obj.buyer_state or "", obj.buyer_zip or "") if p]
        return " ".join(parts).strip() or None

    def get_payment_summary(self, obj: Order):
        if obj.paid_at:
            if getattr(obj, "payment_method", None) == Order.PaymentMethod.CASH:
                return "Cash (test) — marked paid"
            return "Card — processed securely (Stripe)"
        if getattr(obj, "payment_method", None) == Order.PaymentMethod.CASH:
            return "Cash (test) — confirm when you complete the handoff"
        return "Payment not completed"

    def get_part_subtotal_usd(self, obj: Order):
        sub = obj.amount_usd - obj.shipping_amount_usd
        return str(sub.quantize(Decimal("0.01")))

    def get_seller_payout_summary(self, obj: Order):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        if request.user.id != obj.seller_id:
            return None
        sub = obj.amount_usd - obj.shipping_amount_usd
        return {
            "buyer_paid_total_usd": str(obj.amount_usd),
            "shipping_line_usd": str(obj.shipping_amount_usd),
            "part_subtotal_usd": str(sub.quantize(Decimal("0.01"))),
            "label_cost_usd": str(obj.shipping_label_cost_usd) if obj.shipping_label_cost_usd is not None else None,
        }


class BuyerOrderInquirySerializer(serializers.Serializer):
    topic = serializers.ChoiceField(
        choices=("contact_seller", "return_item", "item_not_received", "cancel_order"),
    )
    message = serializers.CharField(min_length=10, max_length=8000)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate(self, attrs):
        order: Order = self.context["order"]
        request = self.context["request"]
        topic = attrs["topic"]
        if request.user.id != order.buyer_id:
            raise serializers.ValidationError("Only the buyer can submit this.")
        delivered = order.state == Order.State.DELIVERED
        if topic in ("return_item", "item_not_received") and not delivered:
            raise serializers.ValidationError({"topic": "This option is available after delivery."})
        if topic == "cancel_order":
            if delivered:
                raise serializers.ValidationError({"topic": "Cancellation is not available after delivery."})
            if order.state in (Order.State.CANCELLED, Order.State.REFUNDED):
                raise serializers.ValidationError({"topic": "Order is already closed."})
        return attrs


class SellerReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=4000)


def as_amount_cents(v: Decimal) -> int:
    return int((v * 100).quantize(Decimal("1")))


def now():
    return timezone.now()
