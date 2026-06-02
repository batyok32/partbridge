from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from vehicles.models import VehiclePart

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from vehicles.shipping_preview import shipping_amount_for_mode, shipping_preview_stub

from .dimensions import cm_to_inches, kg_to_pounds
from .models import CartItem, Order, SellerReview, SellerVerification
from .notifications import send_order_email, send_order_sms
from .order_notifications import (
    send_buyer_order_inquiry_email,
    send_order_placed_notifications,
    send_seller_verification_submitted_email,
)
from .pdf_receipt import build_order_receipt_pdf
from .cash_payment import finalize_cash_order_payment
from .payment_completion import finalize_order_payment
from .payments import create_stripe_checkout_session_for_orders, stripe_configured, verify_checkout_session_and_finalize
from .stripe_payout import get_connect_available_usd, payout_available_to_bank
from .serializers import (
    BuyerOrderInquirySerializer,
    CartAddSerializer,
    CartCheckoutPreviewSerializer,
    CartItemSerializer,
    CartItemUpdateSerializer,
    CheckoutIntentResponseSerializer,
    CheckoutIntentSerializer,
    ConfirmPaymentSerializer,
    OrderSerializer,
    PreShipChecklistSerializer,
    PurchaseLabelSerializer,
    SellerConfirmSerializer,
    SellerReviewCreateSerializer,
    ShippingPlanSerializer,
    TrackingUpdateSerializer,
    as_amount_cents,
)

logger = logging.getLogger(__name__)


def _ensure_seller_verification(user):
    sv, _ = SellerVerification.objects.get_or_create(user=user)
    return sv


def _first_sale_for_seller(seller) -> bool:
    return not Order.objects.filter(seller=seller, paid_at__isnull=False).exists()


def _seller_ratings_cache(seller_ids: set[int]) -> dict[int, tuple[float | None, int]]:
    if not seller_ids:
        return {}
    rows = (
        SellerReview.objects.filter(seller_id__in=seller_ids)
        .values("seller_id")
        .annotate(avg=Avg("rating"), c=Count("id"))
    )
    out: dict[int, tuple[float | None, int]] = {}
    for r in rows:
        avg = r["avg"]
        out[r["seller_id"]] = (float(avg) if avg is not None else None, int(r["c"]))
    return out


def _unit_price_for_part(part: VehiclePart) -> Decimal | None:
    """Active timed offer (if not expired) or list price."""
    p = part.effective_buy_price
    if p is None:
        return None
    return Decimal(str(p))


def _purchase_totals_unit_price(
    part: VehiclePart,
    unit_price: Decimal,
    quantity: int,
    buyer_zip: str,
    shipping_mode: str,
):
    qty = max(1, int(quantity))
    mode = (shipping_mode or "standard").strip().lower()
    if mode not in ("standard", "next_day"):
        mode = "standard"
    zip_for_preview = (buyer_zip or "").strip() or (part.vehicle.location_zip or "98101")[:5]
    preview = shipping_preview_stub(
        seller_state=part.vehicle.location_state or "",
        seller_zip=part.vehicle.location_zip or "",
        buyer_zip=zip_for_preview,
        package_weight_kg=None,
        pickup_allowed=bool(part.vehicle.pickup_allowed),
    )
    ship_one = shipping_amount_for_mode(preview, mode)
    part_total = Decimal(str(unit_price)) * qty
    ship_total = ship_one * qty
    return part_total + ship_total, ship_total


def _create_order_intent(
    *,
    buyer,
    part,
    amount,
    shipping_amount_usd=Decimal("0"),
    shipping_mode="",
    source_quote_id=None,
    source_cart_item_id=None,
    buyer_state="",
    buyer_zip="",
    buyer_notes="",
    payment_method=Order.PaymentMethod.STRIPE,
):
    v = part.vehicle
    vehicle_snapshot = {
        "vin": (v.vin or "").strip(),
        "year": v.year,
        "make": (v.make or "").strip(),
        "model": (v.model or "").strip(),
        "trim": (v.trim or "").strip(),
    }
    order = Order.objects.create(
        buyer=buyer,
        seller=part.vehicle.owner,
        vehicle_part=part,
        amount_usd=amount,
        shipping_amount_usd=shipping_amount_usd,
        shipping_mode=(shipping_mode or "")[:24],
        fitment_verified_at=timezone.now(),
        return_policy_ack_at=timezone.now(),
        source_quote_id=source_quote_id,
        source_cart_item_id=source_cart_item_id,
        vehicle_snapshot=vehicle_snapshot,
        buyer_state=(buyer_state or "").strip().upper()[:2],
        buyer_zip=(buyer_zip or "").strip()[:10],
        buyer_notes=(buyer_notes or "").strip()[:2000],
        state=Order.State.PAYMENT_PENDING,
        payment_method=payment_method,
    )
    # No PaymentIntent until Stripe Checkout collects payment (or dev simulate without PI).
    order.stripe_payment_intent_id = ""
    order.stripe_client_secret = ""

    seller_ver = _ensure_seller_verification(order.seller)
    if _first_sale_for_seller(order.seller) and not seller_ver.payout_ready:
        order.payout_blocked = True
        order.payout_block_reason = (
            "Seller can complete order now; cashout is blocked until Connect onboarding and approved identity documents."
        )
        order.payout_block_deadline = timezone.now() + timedelta(days=5)
    order.save(
        update_fields=[
            "stripe_payment_intent_id",
            "stripe_client_secret",
            "payout_blocked",
            "payout_block_reason",
            "payout_block_deadline",
            "updated_at",
        ]
    )
    return order


def _next_wed_or_sat(ref):
    # 0=Mon ... 6=Sun; target Wed(2), Sat(5)
    weekday = ref.weekday()
    candidates = []
    for target in (2, 5):
        delta = (target - weekday) % 7
        if delta == 0:
            delta = 7
        candidates.append(ref + timedelta(days=delta))
    return min(candidates)


def _same_state(order: Order) -> bool:
    seller_state = (order.vehicle_part.vehicle.location_state or "").strip().upper()
    buyer_state = (order.buyer_state or "").strip().upper()
    return bool(seller_state and buyer_state and seller_state == buyer_state)


class CheckoutIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = CheckoutIntentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        part = get_object_or_404(
            VehiclePart.objects.select_related("vehicle"),
            pk=ser.validated_data["vehicle_part_id"],
        )
        if part.vehicle.owner_id == request.user.id:
            return Response({"detail": "You cannot buy your own listing."}, status=400)
        if part.effective_listing_state != VehiclePart.ListingState.BUY_NOW:
            return Response({"detail": "This listing is not available for Buy Now."}, status=400)
        unit = _unit_price_for_part(part)
        if unit is None:
            return Response({"detail": "Listing has no Buy Now price."}, status=400)

        vd = ser.validated_data
        mode = vd.get("shipping_mode") or "standard"
        bz = (vd.get("buyer_zip") or "").strip()
        pm_raw = (vd.get("payment_method") or "stripe").strip().lower()
        if pm_raw not in ("stripe", "cash"):
            return Response({"detail": "Invalid payment_method."}, status=400)
        pm = Order.PaymentMethod.CASH if pm_raw == "cash" else Order.PaymentMethod.STRIPE
        try:
            total, ship_total = _purchase_totals_unit_price(part, unit, 1, bz, mode)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        with transaction.atomic():
            order = _create_order_intent(
                buyer=request.user,
                part=part,
                amount=total,
                shipping_amount_usd=ship_total,
                shipping_mode=mode,
                buyer_state=str(vd.get("buyer_state") or ""),
                buyer_zip=bz,
                payment_method=pm,
            )
        if pm == Order.PaymentMethod.STRIPE:
            send_order_placed_notifications([order])
        return Response(CheckoutIntentResponseSerializer(order).data, status=201)


class ConfirmOrderPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.select_related("vehicle_part"), pk=order_id, buyer=request.user)
        if order.payment_method == Order.PaymentMethod.CASH:
            return Response(
                {"detail": "Cash orders use POST /orders/{id}/confirm-cash-payment/."},
                status=400,
            )
        ser = ConfirmPaymentSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        if ser.validated_data["status"] != "succeeded":
            return Response({"detail": "Payment not succeeded."}, status=400)
        if order.state != Order.State.PAYMENT_PENDING:
            return Response({"detail": "Order is not awaiting payment."}, status=409)

        pi_id = (ser.validated_data.get("payment_intent_id") or "").strip() or order.stripe_payment_intent_id
        status, err = finalize_order_payment(order_id=order.id, payment_intent_id=pi_id)
        if status == "error":
            return Response({"detail": err or "Payment verification failed."}, status=400)
        if status == "already_done":
            return Response({"detail": "Order is not awaiting payment."}, status=409)

        order.refresh_from_db()
        return Response(OrderSerializer(order, context={"request": request}).data)


class ConfirmCashPaymentView(APIView):
    """Test flow: mark a cash payment_method order as paid without Stripe."""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.select_related("vehicle_part"), pk=order_id, buyer=request.user)
        if order.payment_method != Order.PaymentMethod.CASH:
            return Response({"detail": "Not a cash test order."}, status=400)
        st, err = finalize_cash_order_payment(order_id=order.id)
        if st == "error":
            return Response({"detail": err or "Could not finalize."}, status=400)
        if st == "already_done":
            return Response({"detail": "Order is not awaiting payment."}, status=409)
        order.refresh_from_db()
        send_order_placed_notifications([order])
        return Response(OrderSerializer(order, context={"request": request}).data)


class OrderStripeCheckoutSessionView(APIView):
    """Buyer starts hosted Stripe Checkout — returns URL to redirect the browser."""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(
            Order.objects.select_related("vehicle_part"),
            pk=order_id,
            buyer=request.user,
        )
        if order.state != Order.State.PAYMENT_PENDING:
            return Response({"detail": "Order is not awaiting payment."}, status=409)
        if order.payment_method == Order.PaymentMethod.CASH:
            return Response({"detail": "Cash test orders do not use Stripe Checkout."}, status=400)
        if not stripe_configured():
            return Response(
                {"detail": "Stripe is not configured. Use simulate payment in development."},
                status=503,
            )
        try:
            url = create_stripe_checkout_session_for_orders([order])
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception:
            return Response({"detail": "Could not start Stripe Checkout."}, status=500)
        return Response({"url": url})


class VerifyCheckoutSessionView(APIView):
    """After redirect from Stripe Checkout, finalize payment (backup if webhook is slow)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = (request.query_params.get("session_id") or "").strip()
        if not session_id:
            return Response({"detail": "session_id is required."}, status=400)
        st, err, order_pk = verify_checkout_session_and_finalize(session_id=session_id, buyer_id=request.user.id)
        if st == "error":
            return Response({"detail": err or "Verification failed."}, status=400)
        if order_pk is None:
            return Response({"detail": "Could not resolve order."}, status=500)
        order = get_object_or_404(Order.objects.select_related("vehicle_part"), pk=order_pk, buyer=request.user)
        order.refresh_from_db()
        return Response(OrderSerializer(order, context={"request": request}).data)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Order.objects.filter(Q(buyer=request.user) | Q(seller=request.user))
            .select_related("vehicle_part", "vehicle_part__vehicle", "seller")
            .prefetch_related("seller_review")
        )
        cache = _seller_ratings_cache({o.seller_id for o in qs})
        return Response(
            OrderSerializer(qs, many=True, context={"request": request, "seller_ratings_cache": cache}).data
        )


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CartItem.objects.filter(user=request.user).select_related(
            "vehicle_part",
            "vehicle_part__vehicle",
        )
        return Response(CartItemSerializer(qs, many=True).data)

    def post(self, request):
        ser = CartAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        part = get_object_or_404(
            VehiclePart.objects.select_related("vehicle"),
            pk=ser.validated_data["vehicle_part_id"],
        )
        if part.vehicle.owner_id == request.user.id:
            return Response({"detail": "You cannot add your own listing to cart."}, status=400)
        unit = _unit_price_for_part(part)
        if part.effective_listing_state != VehiclePart.ListingState.BUY_NOW or unit is None:
            return Response({"detail": "Only Buy Now listings can be added to cart."}, status=400)
        mode = (ser.validated_data.get("shipping_mode") or CartItem.ShippingMode.STANDARD).lower()
        bz = (ser.validated_data.get("buyer_zip") or "").strip()
        if mode != CartItem.ShippingMode.PICKUP and not bz:
            return Response({"detail": "ZIP is required for delivery."}, status=400)
        qty = ser.validated_data["quantity"]
        try:
            _total, ship_total = _purchase_totals_unit_price(part, unit, qty, bz, mode)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        notes = (ser.validated_data.get("buyer_notes") or "").strip()[:2000]
        item, created = CartItem.objects.get_or_create(
            user=request.user,
            vehicle_part=part,
            defaults={
                "quantity": qty,
                "shipping_mode": mode,
                "buyer_zip_snapshot": bz[:16],
                "shipping_quoted_usd": ship_total,
                "buyer_notes": notes,
            },
        )
        if not created:
            item.quantity = qty
            item.shipping_mode = mode
            item.buyer_zip_snapshot = bz[:16]
            item.shipping_quoted_usd = ship_total
            item.buyer_notes = notes
            item.save(
                update_fields=[
                    "quantity",
                    "shipping_mode",
                    "buyer_zip_snapshot",
                    "shipping_quoted_usd",
                    "buyer_notes",
                    "updated_at",
                ]
            )
        item = CartItem.objects.select_related("vehicle_part", "vehicle_part__vehicle").get(pk=item.pk)
        return Response(CartItemSerializer(item).data, status=201 if created else 200)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id: int):
        item = get_object_or_404(
            CartItem.objects.select_related("vehicle_part", "vehicle_part__vehicle"),
            pk=item_id,
            user=request.user,
        )
        ser = CartItemUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        if vd and set(vd.keys()) == {"buyer_notes"}:
            item.buyer_notes = (vd.get("buyer_notes") or "").strip()[:2000]
            item.save(update_fields=["buyer_notes", "updated_at"])
            return Response(CartItemSerializer(item).data)
        part = item.vehicle_part
        mode = (ser.validated_data.get("shipping_mode") or item.shipping_mode).strip().lower()
        if "buyer_zip" in ser.validated_data:
            bz = (ser.validated_data.get("buyer_zip") or "").strip()
        else:
            bz = (item.buyer_zip_snapshot or "").strip()
        if mode != CartItem.ShippingMode.PICKUP and not bz:
            return Response({"detail": "ZIP is required for delivery."}, status=400)
        unit = _unit_price_for_part(part)
        if unit is None:
            return Response({"detail": "Part has no price."}, status=400)
        try:
            _total, ship_total = _purchase_totals_unit_price(part, unit, item.quantity, bz, mode)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        item.shipping_mode = mode
        item.buyer_zip_snapshot = bz[:16]
        item.shipping_quoted_usd = ship_total
        update_fields = ["shipping_mode", "buyer_zip_snapshot", "shipping_quoted_usd", "updated_at"]
        if "buyer_notes" in ser.validated_data:
            item.buyer_notes = (ser.validated_data.get("buyer_notes") or "").strip()[:2000]
            update_fields.append("buyer_notes")
        item.save(update_fields=update_fields)
        return Response(CartItemSerializer(item).data)

    def delete(self, request, item_id: int):
        item = get_object_or_404(CartItem, pk=item_id, user=request.user)
        item.delete()
        return Response(status=204)


class CartCheckoutPreviewView(APIView):
    """Recalculate parts + shipping totals for the cart using a destination state/ZIP."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = CartCheckoutPreviewSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        req_zip = str(ser.validated_data.get("buyer_zip") or "").strip()
        req_state = str(ser.validated_data.get("buyer_state") or "").strip().upper()[:2]
        items = list(CartItem.objects.filter(user=request.user).select_related("vehicle_part", "vehicle_part__vehicle"))
        if not items:
            return Response({"detail": "Cart is empty."}, status=400)
        lines = []
        unavailable = []
        parts_total = Decimal("0")
        shipping_total = Decimal("0")
        for item in items:
            part = item.vehicle_part
            unit = _unit_price_for_part(part)
            if part.effective_listing_state != VehiclePart.ListingState.BUY_NOW or unit is None:
                unavailable.append({"vehicle_part_id": part.id, "label": part.label})
                continue
            mode = item.shipping_mode
            bz = req_zip or (item.buyer_zip_snapshot or "").strip()
            if mode != CartItem.ShippingMode.PICKUP and not bz:
                return Response(
                    {"detail": "Each cart line needs a delivery ZIP (pickup lines excepted)."},
                    status=400,
                )
            try:
                total, ship_total = _purchase_totals_unit_price(part, unit, item.quantity, bz, mode)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            part_sub = unit * Decimal(item.quantity)
            lines.append(
                {
                    "cart_item_id": item.id,
                    "vehicle_part_id": part.id,
                    "label": part.label,
                    "quantity": item.quantity,
                    "shipping_mode": mode,
                    "unit_price": str(unit),
                    "parts_subtotal": str(part_sub),
                    "shipping_quoted_usd": str(ship_total),
                    "line_total_usd": str(total),
                }
            )
            parts_total += part_sub
            shipping_total += ship_total
        if unavailable:
            return Response(
                {
                    "detail": "One or more items are no longer available for purchase.",
                    "unavailable": unavailable,
                },
                status=400,
            )
        return Response(
            {
                "buyer_state": req_state,
                "buyer_zip": req_zip,
                "lines": lines,
                "parts_total": str(parts_total),
                "shipping_total": str(shipping_total),
                "grand_total": str(parts_total + shipping_total),
            },
            status=200,
        )


class CartCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_zip = str(request.data.get("buyer_zip") or "").strip()
        req_state = str(request.data.get("buyer_state") or "").strip().upper()[:2]
        items = list(CartItem.objects.filter(user=request.user).select_related("vehicle_part", "vehicle_part__vehicle"))
        if not items:
            return Response({"detail": "Cart is empty."}, status=400)
        unavailable = []
        for item in items:
            part = item.vehicle_part
            unit = _unit_price_for_part(part)
            if part.effective_listing_state != VehiclePart.ListingState.BUY_NOW or unit is None:
                unavailable.append({"vehicle_part_id": part.id, "label": part.label})
        if unavailable:
            return Response(
                {
                    "detail": "One or more items are no longer available for purchase. Remove them from your cart.",
                    "unavailable": unavailable,
                },
                status=400,
            )
        part_ids = [item.vehicle_part_id for item in items]
        Order.objects.filter(
            buyer=request.user,
            vehicle_part_id__in=part_ids,
            state=Order.State.PAYMENT_PENDING,
        ).delete()
        created_orders = []
        with transaction.atomic():
            for item in items:
                part = item.vehicle_part
                mode = item.shipping_mode
                bz = req_zip or (item.buyer_zip_snapshot or "").strip()
                if mode != CartItem.ShippingMode.PICKUP and not bz:
                    return Response({"detail": "Each cart line needs a ZIP for delivery (edit cart items)."}, status=400)
                unit = _unit_price_for_part(part)
                if unit is None:
                    return Response({"detail": "A cart item has no valid price."}, status=400)
                try:
                    total, ship_total = _purchase_totals_unit_price(part, unit, item.quantity, bz, mode)
                except ValueError as exc:
                    return Response({"detail": str(exc)}, status=400)
                order = _create_order_intent(
                    buyer=request.user,
                    part=part,
                    amount=total,
                    shipping_amount_usd=ship_total,
                    shipping_mode=mode,
                    buyer_state=req_state,
                    buyer_zip=bz,
                    buyer_notes=item.buyer_notes or "",
                    source_cart_item_id=item.pk,
                )
                created_orders.append(order)
        payload = {
            "orders_created": len(created_orders),
            "orders": CheckoutIntentResponseSerializer(created_orders, many=True).data,
        }
        if stripe_configured() and created_orders:
            try:
                payload["stripe_checkout_url"] = create_stripe_checkout_session_for_orders(created_orders)
            except Exception:
                logger.exception("Cart checkout: could not create Stripe Checkout session")
                Order.objects.filter(pk__in=[o.id for o in created_orders]).delete()
                return Response(
                    {"detail": "Could not start payment. Your cart is unchanged — try again."},
                    status=503,
                )
        send_order_placed_notifications(created_orders)
        return Response(payload, status=201)


class MoneySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sv = _ensure_seller_verification(request.user)
        seller_orders = Order.objects.filter(seller=request.user)
        escrow_states = [Order.State.PAID_ESCROW, Order.State.SELLER_CONFIRMED, Order.State.LABEL_PROCESSING, Order.State.SHIPPED]
        escrow_total = seller_orders.filter(state__in=escrow_states).aggregate(v=Sum("amount_usd"))["v"] or 0
        blocked_total = seller_orders.filter(payout_blocked=True, state__in=escrow_states).aggregate(v=Sum("amount_usd"))["v"] or 0
        debits_total = seller_orders.aggregate(v=Sum("shipping_label_cost_usd"))["v"] or 0
        available_total = seller_orders.filter(
            state=Order.State.DELIVERED,
            hold_until__isnull=False,
            hold_until__lte=timezone.now(),
        ).aggregate(v=Sum("amount_usd"))["v"] or 0
        recent = (
            seller_orders.filter(
                state__in=[
                    Order.State.PAID_ESCROW,
                    Order.State.SELLER_CONFIRMED,
                    Order.State.LABEL_PROCESSING,
                    Order.State.SHIPPED,
                    Order.State.DELIVERED,
                ]
            )
            .order_by("-created_at")[:40]
        )
        earnings_lines = []
        for o in recent:
            snap = o.vehicle_snapshot or {}
            earnings_lines.append(
                {
                    "order_id": o.id,
                    "amount_usd": str(o.amount_usd),
                    "state": o.state,
                    "part_label": o.vehicle_part.label,
                    "vin": snap.get("vin") or "",
                    "vehicle_title": " ".join(
                        filter(
                            None,
                            [str(snap.get("year") or ""), snap.get("make"), snap.get("model")],
                        )
                    ).strip(),
                    "paid_at": o.paid_at,
                    "delivered_at": o.delivered_at,
                }
            )
        stripe_avail, stripe_err = get_connect_available_usd(stripe_account_id=(sv.stripe_account_id or "").strip())
        return Response(
            {
                "payout_ready": sv.payout_ready,
                "verification": {
                    "connect_onboarded_at": sv.connect_onboarded_at,
                    "documents_review_status": sv.documents_review_status,
                    "documents_submitted_at": sv.documents_submitted_at,
                    "documents_approved_at": sv.documents_approved_at,
                    "id_verified_at": sv.id_verified_at,
                    "ssn_verified_at": sv.ssn_verified_at,
                },
                "stripe_connect_available_usd": str(stripe_avail) if stripe_avail is not None else None,
                "stripe_connect_balance_error": stripe_err,
                "balance": {
                    "escrow_total_usd": escrow_total,
                    "blocked_total_usd": blocked_total,
                    "available_total_usd": available_total,
                    "label_debits_usd": debits_total,
                    "net_available_usd": max(available_total - debits_total, 0),
                },
                "earnings_lines": earnings_lines,
            }
        )


class SellerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uid = request.user.id
        qs = VehiclePart.objects.filter(vehicle__owner_id=uid, is_removed=False)
        return Response(
            {
                "active_buy_now_listings": qs.filter(listing_state=VehiclePart.ListingState.BUY_NOW).count(),
                "draft_listings": qs.filter(listing_state=VehiclePart.ListingState.DRAFT).count(),
                "sold_parts": qs.filter(listing_state=VehiclePart.ListingState.SOLD).count(),
                "unavailable_parts": qs.filter(listing_state=VehiclePart.ListingState.UNAVAILABLE).count(),
                "orders_delivered": Order.objects.filter(seller_id=uid, state=Order.State.DELIVERED).count(),
                "orders_all_states": Order.objects.filter(seller_id=uid).count(),
            }
        )


class CashoutRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sv = _ensure_seller_verification(request.user)
        if not sv.payout_ready:
            return Response(
                {
                    "detail": "Complete Stripe Connect onboarding and identity document approval before cashout.",
                    "payout_ready": False,
                },
                status=400,
            )
        acct = (sv.stripe_account_id or "").strip()
        if not acct.startswith("acct_"):
            return Response({"detail": "Connect a Stripe Express account first (stripe_account_id)."}, status=400)
        raw_amt = request.data.get("amount_usd")
        if raw_amt is not None and raw_amt != "":
            try:
                amount = Decimal(str(raw_amt))
            except Exception:
                return Response({"detail": "Invalid amount_usd."}, status=400)
        else:
            avail, err = get_connect_available_usd(stripe_account_id=acct)
            if err:
                return Response({"detail": err}, status=400)
            if avail is None or avail <= 0:
                return Response({"detail": "No available Stripe balance to pay out."}, status=400)
            amount = avail
        ok, err = payout_available_to_bank(stripe_account_id=acct, amount_usd=amount)
        if not ok:
            return Response({"detail": err or "Stripe payout failed."}, status=400)
        return Response({"detail": "Payout submitted to your bank.", "amount_usd": str(amount), "payout_ready": True})


class QuoteAcceptCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quote_id: int):
        from messaging.models import Quote

        quote = get_object_or_404(
            Quote.objects.select_related("thread", "vehicle_part", "thread__buyer"),
            pk=quote_id,
        )
        if quote.thread.buyer_id != request.user.id:
            return Response({"detail": "Only the quote buyer can accept this quote."}, status=403)
        part = quote.vehicle_part
        if not part:
            return Response({"detail": "Quote is not tied to a part."}, status=400)
        if part.effective_listing_state != VehiclePart.ListingState.BUY_NOW:
            return Response({"detail": "Quoted part must be Buy Now before checkout."}, status=400)
        if quote.status == Quote.Status.ACCEPTED:
            return Response({"detail": "Quote already accepted."}, status=409)
        mode = (request.data.get("shipping_mode") or "standard").strip().lower()
        bz = str(request.data.get("buyer_zip") or "").strip()
        if mode != "pickup" and not bz:
            return Response({"detail": "ZIP is required for delivery."}, status=400)
        unit = _unit_price_for_part(part)
        if unit is None:
            return Response({"detail": "Part has no valid price."}, status=400)
        try:
            total, ship_total = _purchase_totals_unit_price(part, unit, 1, bz, mode)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        with transaction.atomic():
            quote.status = Quote.Status.ACCEPTED
            quote.save(update_fields=["status", "updated_at"])
            Quote.objects.filter(thread=quote.thread).exclude(pk=quote.pk).update(status=Quote.Status.REJECTED)
            order = _create_order_intent(
                buyer=request.user,
                part=part,
                amount=total,
                shipping_amount_usd=ship_total,
                shipping_mode=mode,
                source_quote_id=quote.id,
                buyer_state=str(request.data.get("buyer_state") or ""),
                buyer_zip=bz,
            )
        send_order_placed_notifications([order])
        return Response(CheckoutIntentResponseSerializer(order).data, status=201)


class SellerVerificationView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        sv = _ensure_seller_verification(request.user)

        def abs_media(f):
            if not f:
                return None
            try:
                u = f.url
            except ValueError:
                return None
            return request.build_absolute_uri(u) if request else u

        return Response(
            {
                "payout_ready": sv.payout_ready,
                "stripe_account_id": sv.stripe_account_id,
                "connect_onboarded_at": sv.connect_onboarded_at,
                "documents_review_status": sv.documents_review_status,
                "documents_submitted_at": sv.documents_submitted_at,
                "documents_approved_at": sv.documents_approved_at,
                "document_id_front_url": abs_media(sv.document_id_front),
                "document_id_back_url": abs_media(sv.document_id_back),
                "document_selfie_url": abs_media(sv.document_selfie),
                "id_verified_at": sv.id_verified_at,
                "ssn_verified_at": sv.ssn_verified_at,
                "first_sale_at": sv.first_sale_at,
            }
        )

    def post(self, request):
        sv = _ensure_seller_verification(request.user)
        uploaded = False
        if request.FILES.get("document_id_front"):
            sv.document_id_front = request.FILES["document_id_front"]
            uploaded = True
        if request.FILES.get("document_id_back"):
            sv.document_id_back = request.FILES["document_id_back"]
            uploaded = True
        if request.FILES.get("document_selfie"):
            sv.document_selfie = request.FILES["document_selfie"]
            uploaded = True
        if uploaded:
            sv.documents_submitted_at = timezone.now()
            sv.documents_review_status = SellerVerification.DocumentsReviewStatus.PENDING
            sv.save()
            send_seller_verification_submitted_email(sv)
            return self.get(request)
        account_id = (request.data.get("stripe_account_id") or "").strip()
        if account_id:
            sv.stripe_account_id = account_id
            sv.save(update_fields=["stripe_account_id", "updated_at"])
        return self.get(request)


class SellerConfirmOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order, pk=order_id, seller=request.user)
        ser = SellerConfirmSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        if order.state != Order.State.PAID_ESCROW:
            return Response({"detail": "Order is not awaiting seller confirmation."}, status=409)
        if order.seller_confirmation_due_at and order.seller_confirmation_due_at < timezone.now():
            return Response({"detail": "Confirmation window expired."}, status=409)
        order.state = Order.State.SELLER_CONFIRMED
        order.seller_confirmed_at = timezone.now()
        order.save(update_fields=["state", "seller_confirmed_at", "updated_at"])
        send_order_email(
            to_email=order.buyer.email,
            subject=f"Seller confirmed order #{order.id}",
            body="Seller confirmed the order and is preparing shipment.",
        )
        return Response(OrderSerializer(order, context={"request": request}).data)


class SellerActionQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(
            seller=request.user,
            state__in=[
                Order.State.PAID_ESCROW,
                Order.State.SELLER_CONFIRMED,
                Order.State.LABEL_PROCESSING,
                Order.State.SHIPPED,
            ],
        ).select_related("vehicle_part", "vehicle_part__vehicle")
        rows = []
        for o in qs:
            rows.append(
                {
                    "id": o.id,
                    "part": o.vehicle_part.label,
                    "state": o.state,
                    "seller_confirmation_due_at": o.seller_confirmation_due_at,
                    "tracking_number": o.tracking_number,
                    "needs_seller_confirm": False,
                    "needs_shipment": bool(
                        o.seller_confirmed_at and not o.tracking_number and o.state not in (Order.State.SHIPPED, Order.State.DELIVERED)
                    ),
                }
            )
        return Response(rows)


class SellerShippingPlanSuggestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(
            Order.objects.select_related("vehicle_part", "vehicle_part__part_family", "vehicle_part__vehicle"),
            pk=order_id,
            seller=request.user,
        )
        label = (order.vehicle_part.label or "").lower()
        cat = (order.vehicle_part.part_family.category.slug if order.vehicle_part.part_family else "").lower()
        # AI-like heuristic seed (replace with LLM call if needed).
        if any(k in label for k in ("hood", "bumper")):
            dims = {"l": Decimal("170"), "w": Decimal("80"), "h": Decimal("35"), "kg": Decimal("18")}
            source = "heuristic_large"
        elif any(k in cat for k in ("engine", "drivetrain")):
            dims = {"l": Decimal("55"), "w": Decimal("45"), "h": Decimal("40"), "kg": Decimal("14")}
            source = "heuristic_medium"
        else:
            dims = {"l": Decimal("38"), "w": Decimal("30"), "h": Decimal("20"), "kg": Decimal("4.5")}
            source = "heuristic_small"

        return Response(
            {
                "source": source,
                "package_length_in": str(cm_to_inches(dims["l"])),
                "package_width_in": str(cm_to_inches(dims["w"])),
                "package_height_in": str(cm_to_inches(dims["h"])),
                "package_weight_lb": str(kg_to_pounds(dims["kg"])),
            }
        )


class SellerShippingPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id: int):
        order = get_object_or_404(Order.objects.select_related("vehicle_part", "vehicle_part__vehicle"), pk=order_id, seller=request.user)
        ser = ShippingPlanSerializer(data=request.data, context={"order": order})
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        order.package_length_cm = vd["package_length_cm"]
        order.package_width_cm = vd["package_width_cm"]
        order.package_height_cm = vd["package_height_cm"]
        order.package_weight_kg = vd["package_weight_kg"]
        order.dimensions_confirmed_at = timezone.now()

        order.insurance_opt_in = bool(vd.get("insurance_opt_in"))
        order.pre_ship_checklist_complete_at = timezone.now()
        order.save(
            update_fields=[
                "package_length_cm",
                "package_width_cm",
                "package_height_cm",
                "package_weight_kg",
                "dimensions_confirmed_at",

                "insurance_opt_in",
                "pre_ship_checklist_complete_at",
                "updated_at",
            ]
        )
        # Notify admin that shipping details were submitted
        _notify_admin_shipping_needed(order)
        return Response(OrderSerializer(order, context={"request": request}).data)


def _notify_admin_shipping_needed(order):
    """Tell admin that a new order needs a shipping label."""
    try:
        from django.conf import settings as djsettings
        from django.core.mail import send_mail
        admin_email = (getattr(djsettings, "ORDER_ADMIN_EMAIL", "") or "").strip()
        if not admin_email:
            return
        send_mail(
            subject=f"Shipping label needed — Order #{order.id} — Partbridge",
            message=(
                f"Order #{order.id} needs a shipping label.\n\n"
                f"Buyer: {order.buyer.email}\n"
                f"Seller: {order.seller.email}\n"
                f"Part: {order.vehicle_part.label}\n"
                f"Package: {order.package_length_cm}×{order.package_width_cm}×{order.package_height_cm} cm, "
                f"{order.package_weight_kg} kg\n\n"
                "Please upload the label and tracking info in Django admin."
            ),
            from_email=djsettings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception:
        pass


class SellerPreShipChecklistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order, pk=order_id, seller=request.user)
        if order.state not in (Order.State.SELLER_CONFIRMED, Order.State.PAID_ESCROW):
            return Response({"detail": "Order is not ready for pre-ship checklist."}, status=409)
        ser = PreShipChecklistSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        now = timezone.now()
        order.pre_ship_photos = vd.get("pre_ship_photos") or []
        order.package_length_cm = vd["package_length_cm"]
        order.package_width_cm = vd["package_width_cm"]
        order.package_height_cm = vd["package_height_cm"]
        order.package_weight_kg = vd["package_weight_kg"]
        order.dimensions_confirmed_at = now
        order.insurance_opt_in = bool(vd.get("insurance_opt_in"))
        order.pre_ship_checklist_complete_at = now
        order.save(
            update_fields=[
                "pre_ship_photos",
                "package_length_cm",
                "package_width_cm",
                "package_height_cm",
                "package_weight_kg",
                "dimensions_confirmed_at",

                "insurance_opt_in",
                "pre_ship_checklist_complete_at",
                "updated_at",
            ]
        )
        return Response(OrderSerializer(order, context={"request": request}).data)


class SellerPurchaseLabelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order, pk=order_id, seller=request.user)
        ser = PurchaseLabelSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)

        if not order.seller_confirmed_at:
            return Response({"detail": "Seller confirmation is required first."}, status=409)
        if not order.pre_ship_checklist_complete_at:
            return Response({"detail": "Complete pre-ship checklist first."}, status=409)
        if not all([order.package_length_cm, order.package_width_cm, order.package_height_cm, order.package_weight_kg]):
            return Response({"detail": "Package dimensions/weight missing."}, status=409)

        base = 12.50
        weight_fee = float(order.package_weight_kg) * 1.7
        overage_risk = (
            float(order.package_length_cm) + float(order.package_width_cm) + float(order.package_height_cm)
        ) / 100
        cost = round(base + weight_fee + overage_risk, 2)
        carrier = (ser.validated_data.get("carrier") or "usps").strip().lower() or "usps"

        order.state = Order.State.LABEL_PROCESSING
        order.shipping_label_cost_usd = cost
        order.tracking_carrier = carrier
        order.tracking_status = "label_processing"
        order.last_tracking_at = timezone.now()
        order.save(
            update_fields=[
                "state",
                "shipping_label_cost_usd",
                "tracking_carrier",
                "tracking_status",
                "last_tracking_at",
                "updated_at",
            ]
        )
        # Notify admin to generate and upload a label
        _notify_admin_shipping_needed(order)
        return Response(OrderSerializer(order, context={"request": request}).data)


class TrackingWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        configured = (settings.TRACKING_WEBHOOK_SECRET or "").strip()
        provided = (request.headers.get("X-Tracking-Webhook-Secret") or "").strip()
        if configured and provided != configured:
            return Response({"detail": "Invalid webhook secret."}, status=403)

        ser = TrackingUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        order = None
        if vd.get("order_id"):
            order = Order.objects.filter(pk=vd["order_id"]).first()
        if order is None and vd.get("tracking_number"):
            order = Order.objects.filter(tracking_number=vd["tracking_number"]).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=404)
        at = vd.get("at") or timezone.now()
        order.tracking_status = vd["status"]
        if vd.get("carrier"):
            order.tracking_carrier = vd["carrier"]
        order.last_tracking_at = at
        if str(vd["status"]).lower() in {"delivered", "delivery_complete"}:
            order.state = Order.State.DELIVERED
            order.delivered_at = at
            order.released_to_seller_at = at
            order.funds_held_until_delivered = False
            send_order_email(
                to_email=order.buyer.email,
                subject=f"Order #{order.id} delivered",
                body="Carrier marked the order as delivered.",
            )
        elif str(vd["status"]).lower() in {"in_transit", "picked_up", "out_for_delivery"}:
            order.state = Order.State.SHIPPED
        order.save(
            update_fields=[
                "tracking_status",
                "tracking_carrier",
                "last_tracking_at",
                "state",
                "delivered_at",
                "released_to_seller_at",
                "funds_held_until_delivered",
                "updated_at",
            ]
        )
        return Response(OrderSerializer(order, context={"request": request}).data)


class TrackingAdminOverrideView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order, pk=order_id)
        ser = TrackingUpdateSerializer(data={**request.data, "order_id": order_id})
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        status_value = str(vd["status"]).strip()
        order.tracking_status = status_value
        if vd.get("carrier"):
            order.tracking_carrier = vd["carrier"]
        order.last_tracking_at = vd.get("at") or timezone.now()
        if status_value.lower() in {"delivered", "delivery_complete"}:
            order.state = Order.State.DELIVERED
            order.delivered_at = order.last_tracking_at
            order.released_to_seller_at = order.last_tracking_at
            order.funds_held_until_delivered = False
        elif status_value.lower() in {"in_transit", "picked_up", "out_for_delivery"}:
            order.state = Order.State.SHIPPED
        order.save(
            update_fields=[
                "tracking_status",
                "tracking_carrier",
                "last_tracking_at",
                "state",
                "delivered_at",
                "released_to_seller_at",
                "funds_held_until_delivered",
                "updated_at",
            ]
        )
        return Response(OrderSerializer(order, context={"request": request}).data)


class PurchaseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Order.objects.filter(buyer=request.user)
            .select_related("vehicle_part", "vehicle_part__vehicle", "seller")
            .prefetch_related("seller_review")
        )
        cache = _seller_ratings_cache({o.seller_id for o in qs})
        return Response(
            OrderSerializer(qs, many=True, context={"request": request, "seller_ratings_cache": cache}).data
        )


class SalesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Order.objects.filter(seller=request.user).select_related("vehicle_part", "vehicle_part__vehicle")
        cache = _seller_ratings_cache({o.seller_id for o in qs})
        return Response(
            OrderSerializer(qs, many=True, context={"request": request, "seller_ratings_cache": cache}).data
        )


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id: int):
        order = get_object_or_404(
            Order.objects.select_related("vehicle_part", "vehicle_part__vehicle", "seller", "buyer").prefetch_related(
                "seller_review"
            ),
            pk=order_id,
        )
        if request.user.id not in (order.buyer_id, order.seller_id):
            return Response({"detail": "Forbidden."}, status=403)
        cache = _seller_ratings_cache({order.seller_id})
        return Response(
            OrderSerializer(order, context={"request": request, "seller_ratings_cache": cache}).data
        )


class OrderReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id: int):
        order = get_object_or_404(
            Order.objects.select_related("vehicle_part", "vehicle_part__vehicle", "buyer", "seller"),
            pk=order_id,
        )
        if request.user.id not in (order.buyer_id, order.seller_id):
            return Response({"detail": "Forbidden."}, status=403)
        role = "buyer" if request.user.id == order.buyer_id else "seller"
        pdf_bytes = build_order_receipt_pdf(order, role=role)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="receipt-order-{order.id}.pdf"'
        return resp


class BuyerOrderInquiryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.select_related("vehicle_part"), pk=order_id, buyer=request.user)
        ser = BuyerOrderInquirySerializer(data=request.data, context={"request": request, "order": order})
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        send_buyer_order_inquiry_email(
            order=order,
            topic=vd["topic"],
            message=vd["message"],
            phone=vd.get("phone") or "",
        )
        return Response({"ok": True})


class SellerReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.select_related("vehicle_part"), pk=order_id, buyer=request.user)
        if order.state != Order.State.DELIVERED:
            return Response({"detail": "Reviews are available after the order is delivered."}, status=409)
        if SellerReview.objects.filter(order=order).exists():
            return Response({"detail": "You already submitted a review for this order."}, status=409)
        ser = SellerReviewCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        SellerReview.objects.create(
            order=order,
            buyer=request.user,
            seller_id=order.seller_id,
            rating=vd["rating"],
            comment=(vd.get("comment") or "").strip(),
        )
        return Response({"ok": True})
