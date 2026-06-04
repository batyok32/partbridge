from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bundles.models import Bundle, BundleCategory
from parts.models import Item

from .models import CartBundle, CartItem, Dispute, DisputeMessage, Order, OrderItem, Payment, SellerReview

logger = logging.getLogger(__name__)
from .serializers import (
    CartBundleSerializer,
    CartItemSerializer,
    DisputeMessageSerializer,
    DisputeSerializer,
    OrderDetailSerializer,
    OrderSerializer,
    SellerOrderDetailSerializer,
    SellerReviewSerializer,
    SellerSaleSerializer,
)

STATE_ZONE = {
    "CA": 1, "OR": 1, "WA": 1, "NV": 1, "AZ": 1,
    "TX": 2, "FL": 2, "GA": 2, "NC": 2, "SC": 2, "VA": 2, "TN": 2,
    "LA": 2, "AL": 2, "MS": 2,
}

SHIPPING_MID = {"small": 11.0, "medium": 35.0, "large": 550.0}
SHIPPING_ECONOMY = {"large": 100.0, "xl": 150.0}

# State base sales tax rates (parts/tangible goods). 0 = no state sales tax.
STATE_TAX_RATES = {
    "AL": 0.04,   "AK": 0.00,   "AZ": 0.056,  "AR": 0.065,
    "CA": 0.0725, "CO": 0.029,  "CT": 0.0635, "DE": 0.00,
    "FL": 0.06,   "GA": 0.04,   "HI": 0.04,   "ID": 0.06,
    "IL": 0.0625, "IN": 0.07,   "IA": 0.06,   "KS": 0.065,
    "KY": 0.06,   "LA": 0.0445, "ME": 0.055,  "MD": 0.06,
    "MA": 0.0625, "MI": 0.06,   "MN": 0.06875,"MS": 0.07,
    "MO": 0.04225,"MT": 0.00,   "NE": 0.055,  "NV": 0.0685,
    "NH": 0.00,   "NJ": 0.06625,"NM": 0.05,   "NY": 0.04,
    "NC": 0.0475, "ND": 0.05,   "OH": 0.0575, "OK": 0.045,
    "OR": 0.00,   "PA": 0.06,   "RI": 0.07,   "SC": 0.06,
    "SD": 0.045,  "TN": 0.07,   "TX": 0.0625, "UT": 0.0485,
    "VT": 0.06,   "VA": 0.043,  "WA": 0.065,  "WV": 0.06,
    "WI": 0.05,   "WY": 0.04,   "DC": 0.06,
}


def _calculate_tax(subtotal: float, state: str) -> float:
    rate = STATE_TAX_RATES.get((state or "").upper().strip(), 0.0)
    return round(subtotal * rate, 2)


def _estimate_shipping(shipping_size, buyer_state, mode="standard"):
    # XL has no fast-freight rate yet — always charge economy flat rate
    if shipping_size == "xl":
        return SHIPPING_ECONOMY["xl"]
    if mode == "economy" and shipping_size == "large":
        return SHIPPING_ECONOMY["large"]
    zone = STATE_ZONE.get((buyer_state or "").upper()[:2], 3)
    factor = 1.0 if zone == 1 else 1.15 if zone == 2 else 1.3
    return round(SHIPPING_MID.get(shipping_size, 35.0) * factor, 2)


# ─── Cart ─────────────────────────────────────────────────────────────────────

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related("item")
        bundles = (
            CartBundle.objects.filter(user=request.user)
            .select_related("bundle__bundle_category")
            .prefetch_related(
                "bundle__bundle_items__item__vehicle__generation__car_model__make",
                "bundle__bundle_items__item__photos",
            )
        )
        ctx = {"request": request}
        return Response({
            "items": CartItemSerializer(items, many=True, context=ctx).data,
            "bundles": CartBundleSerializer(bundles, many=True, context=ctx).data,
        })

    def post(self, request):
        ser = CartItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = ser.validated_data["item"]

        if item.status == Item.Status.HIDDEN_IN_ASSEMBLY:
            return Response(
                {"detail": "This item is part of an assembly and cannot be added individually."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if item.status != Item.Status.ACTIVE:
            return Response(
                {"detail": "This item is no longer available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conflicting = (
            CartBundle.objects.filter(user=request.user, bundle__bundle_items__item=item)
            .select_related("bundle")
            .first()
        )
        if conflicting:
            return Response(
                {"detail": f"This item is already included in the '{conflicting.bundle.name}' bundle in your cart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj, created = CartItem.objects.get_or_create(user=request.user, item=item)
        return Response(CartItemSerializer(obj).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CartItemDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        cart_item = get_object_or_404(CartItem, pk=item_id, user=request.user)
        mode = request.data.get("shipping_mode")
        if mode not in CartItem.ShippingMode.values:
            return Response({"detail": "Invalid shipping_mode."}, status=status.HTTP_400_BAD_REQUEST)
        cart_item.shipping_mode = mode
        cart_item.save(update_fields=["shipping_mode"])
        return Response(CartItemSerializer(cart_item).data)

    def delete(self, request, item_id):
        cart_item = get_object_or_404(CartItem, pk=item_id, user=request.user)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddBundleToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, bundle_id):
        cart_bundle = get_object_or_404(CartBundle, bundle_id=bundle_id, user=request.user)
        mode = request.data.get("shipping_mode")
        if mode not in CartItem.ShippingMode.values:
            return Response({"detail": "Invalid shipping_mode."}, status=status.HTTP_400_BAD_REQUEST)
        cart_bundle.shipping_mode = mode
        cart_bundle.save(update_fields=["shipping_mode"])
        return Response(CartBundleSerializer(cart_bundle).data)

    def post(self, request, bundle_id):
        bundle = get_object_or_404(
            Bundle.objects.select_related("bundle_category"),
            pk=bundle_id, status=Bundle.Status.ACTIVE,
        )

        if bundle.bundle_category.type == BundleCategory.BundleType.ASSEMBLY:
            assembly_item = Item.objects.filter(assembly_bundle=bundle).first()
            if not assembly_item:
                return Response(
                    {"detail": "This assembly bundle has no purchasable item yet."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            obj, created = CartItem.objects.get_or_create(user=request.user, item=assembly_item)
            return Response(
                CartItemSerializer(obj).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        # Discount bundle: remove individual CartItems that overlap, then create CartBundle
        component_item_ids = list(bundle.bundle_items.values_list("item_id", flat=True))
        removed_qs = CartItem.objects.filter(user=request.user, item_id__in=component_item_ids)
        removed_ids = list(removed_qs.values_list("item_id", flat=True))
        removed_qs.delete()

        cart_bundle, created = CartBundle.objects.get_or_create(user=request.user, bundle=bundle)
        return Response(
            {
                "id": cart_bundle.id,
                "created": created,
                "removed_item_ids": removed_ids,
                "removed_count": len(removed_ids),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CartBundleDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, bundle_id):
        cart_bundle = get_object_or_404(CartBundle, bundle_id=bundle_id, user=request.user)
        cart_bundle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartPreviewCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        buyer_state = (request.data.get("buyer_state") or "").strip().upper()[:2]
        buyer_zip = (request.data.get("buyer_zip") or "").strip()

        cart_items = CartItem.objects.filter(user=request.user).select_related("item__vehicle__seller", "item__category")
        cart_bundles = CartBundle.objects.filter(user=request.user).select_related("bundle__bundle_category").prefetch_related(
            "bundle__bundle_items__item__category",
        )

        if not cart_items.exists() and not cart_bundles.exists():
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-remove items that became hidden in assembly (seller grouped them after buyer added them)
        hidden = [ci for ci in cart_items if ci.item.status == Item.Status.HIDDEN_IN_ASSEMBLY]
        if hidden:
            CartItem.objects.filter(pk__in=[ci.pk for ci in hidden]).delete()
            cart_items = CartItem.objects.filter(user=request.user).select_related("item__vehicle__seller", "item__category")

        unavailable = [{"id": ci.id, "label": ci.item.title} for ci in cart_items if ci.item.status != Item.Status.ACTIVE]
        if unavailable:
            return Response({"detail": "Some items are no longer available.", "unavailable": unavailable}, status=400)

        if not cart_items.exists() and not cart_bundles.exists():
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        lines, parts_total, shipping_total = [], 0.0, 0.0

        for ci in cart_items:
            parts_amount = float(ci.item.price)
            shipping_amount = _estimate_shipping(ci.item.shipping_size, buyer_state, ci.shipping_mode)
            line_total = parts_amount + shipping_amount
            lines.append({
                "type": "item",
                "cart_item_id": ci.id, "label": ci.item.title,
                "shipping_mode": ci.shipping_mode,
                "quantity": 1, "parts_subtotal": f"{parts_amount:.2f}",
                "shipping_quoted_usd": f"{shipping_amount:.2f}", "line_total_usd": f"{line_total:.2f}",
            })
            parts_total += parts_amount
            shipping_total += shipping_amount

        for cb in cart_bundles:
            bundle = cb.bundle
            active_bis = [bi for bi in bundle.bundle_items.all() if bi.item and bi.item.status == Item.Status.ACTIVE]
            if bundle.fixed_price:
                bundle_parts = float(bundle.fixed_price)
            else:
                discount = float(bundle.discount_pct or 0)
                bundle_parts = round(
                    sum(float(bi.item.price) for bi in active_bis) * (1 - discount / 100), 2
                )
            bundle_shipping = sum(_estimate_shipping(bi.item.shipping_size, buyer_state, cb.shipping_mode) for bi in active_bis)
            bundle_total = bundle_parts + bundle_shipping
            lines.append({
                "type": "bundle",
                "cart_bundle_id": cb.id, "bundle_id": bundle.id, "label": bundle.name,
                "item_count": len(active_bis), "shipping_mode": cb.shipping_mode, "quantity": 1,
                "parts_subtotal": f"{bundle_parts:.2f}",
                "shipping_quoted_usd": f"{bundle_shipping:.2f}",
                "line_total_usd": f"{bundle_total:.2f}",
            })
            parts_total += bundle_parts
            shipping_total += bundle_shipping

        tax_total = _calculate_tax(parts_total, buyer_state)
        tax_rate = STATE_TAX_RATES.get((buyer_state or "").upper().strip(), 0.0)
        return Response({
            "buyer_state": buyer_state, "buyer_zip": buyer_zip, "lines": lines,
            "parts_total": f"{parts_total:.2f}",
            "shipping_total": f"{shipping_total:.2f}",
            "tax_total": f"{tax_total:.2f}",
            "tax_rate_pct": f"{tax_rate * 100:.3f}".rstrip("0").rstrip("."),
            "grand_total": f"{parts_total + shipping_total + tax_total:.2f}",
        })


class CartCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from accounts.models import ShippingAddress

        buyer_state = (request.data.get("buyer_state") or "").strip().upper()[:2]
        buyer_zip = (request.data.get("buyer_zip") or "").strip()
        shipping_address_id = request.data.get("shipping_address_id")

        cart_items = CartItem.objects.filter(user=request.user).select_related("item__vehicle__seller", "item__category")
        cart_bundles = CartBundle.objects.filter(user=request.user).select_related("bundle__bundle_category").prefetch_related(
            "bundle__bundle_items__item__vehicle__seller",
            "bundle__bundle_items__item__category",
        )

        if not cart_items.exists() and not cart_bundles.exists():
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        hidden = [ci for ci in cart_items if ci.item.status == Item.Status.HIDDEN_IN_ASSEMBLY]
        if hidden:
            CartItem.objects.filter(pk__in=[ci.pk for ci in hidden]).delete()
            cart_items = CartItem.objects.filter(user=request.user).select_related("item__vehicle__seller", "item__category")

        unavailable = [{"id": ci.id, "label": ci.item.title} for ci in cart_items if ci.item.status != Item.Status.ACTIVE]
        if unavailable:
            return Response({"detail": "Some items are no longer available.", "unavailable": unavailable}, status=400)

        if not cart_items.exists() and not cart_bundles.exists():
            return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        address = None
        if shipping_address_id:
            address = ShippingAddress.objects.filter(pk=shipping_address_id, user=request.user).first()
        if not address:
            address = ShippingAddress.objects.filter(user=request.user, is_default=True).first()
        if not address:
            address = ShippingAddress.objects.filter(user=request.user).first()
        if not address:
            address = ShippingAddress.objects.create(
                user=request.user,
                full_name=request.user.get_full_name() or request.user.email.split("@")[0],
                line1="", city="", state=buyer_state or "XX", zip=buyer_zip or "00000", is_default=True,
            )

        order_lines: list = []

        for ci in cart_items:
            seller_id = ci.item.vehicle.seller_id if ci.item.vehicle else None
            order_lines.append((seller_id, ci.item, float(ci.item.price), None, ci.shipping_mode))

        for cb in cart_bundles:
            bundle = cb.bundle
            active_bis = [bi for bi in bundle.bundle_items.all() if bi.item and bi.item.status == Item.Status.ACTIVE]
            total_base = sum(float(bi.item.price) for bi in active_bis)
            for bi in active_bis:
                if bundle.fixed_price and total_base > 0:
                    proportion = float(bi.item.price) / total_base
                    price = round(float(bundle.fixed_price) * proportion, 2)
                else:
                    discount = float(bundle.discount_pct or 0)
                    price = round(float(bi.item.price) * (1 - discount / 100), 2)
                seller_id = bi.item.vehicle.seller_id if bi.item.vehicle else None
                order_lines.append((seller_id, bi.item, price, bundle, cb.shipping_mode))

        by_seller: dict = {}
        for seller_id, item, price, bundle, s_mode in order_lines:
            by_seller.setdefault(seller_id, []).append((item, price, bundle, s_mode))

        created_orders = []
        grand_total = Decimal("0")
        for seller_id, lines in by_seller.items():
            subtotal = sum(p for _, p, _, _ in lines)
            shipping_cost = sum(_estimate_shipping(item.shipping_size, buyer_state, s_mode) for item, _, _, s_mode in lines)
            tax = _calculate_tax(subtotal, buyer_state)
            total = subtotal + shipping_cost + tax
            grand_total += Decimal(str(total))

            order = Order.objects.create(
                buyer=request.user, shipping_address=address,
                status=Order.Status.PENDING, subtotal=subtotal,
                shipping_cost=shipping_cost, tax=tax, total=total,
            )
            for item, price, bundle, s_mode in lines:
                OrderItem.objects.create(
                    order=order, item=item,
                    bundle=bundle,
                    price_at_purchase=price,
                    item_snapshot={
                        "title": item.title, "price": str(price),
                        "condition": item.condition, "shipping_size": item.shipping_size,
                        "shipping_mode": s_mode,
                        "category_name": item.category.name if item.category else "",
                        "bundle_name": bundle.name if bundle else None,
                    },
                )
            created_orders.append(order)

        order_ids = [o.id for o in created_orders]
        ids_str = ",".join(str(i) for i in order_ids)
        amount_cents = int((grand_total * 100).quantize(Decimal("1")))
        logger.info("Checkout: orders=%s grand_total=%s amount_cents=%s", order_ids, grand_total, amount_cents)

        STRIPE_MINIMUM_CENTS = 50
        if amount_cents < STRIPE_MINIMUM_CENTS:
            Order.objects.filter(pk__in=order_ids).delete()
            return Response(
                {"detail": f"Order total ${grand_total:.2f} is below the minimum chargeable amount. Add more items or contact support."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
        pi_id = ""
        client_secret = ""
        provider = "stub"

        if stripe_key:
            try:
                import stripe  # type: ignore
                stripe.api_key = stripe_key
                pi = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency="usd",
                    metadata={"order_ids": ids_str},
                    automatic_payment_methods={"enabled": True},
                )
                pi_id = str(pi["id"])
                client_secret = str(pi["client_secret"])
                provider = "stripe"
            except Exception as exc:
                logger.error("Stripe PaymentIntent.create failed amount_cents=%s: %s", amount_cents, exc)
                Order.objects.filter(pk__in=order_ids).delete()
                return Response({"detail": "Could not initialize payment. Please try again."}, status=502)
        else:
            pi_id = f"pi_stub_{order_ids[0]}_{secrets.token_hex(4)}"
            client_secret = f"{pi_id}_secret_{secrets.token_hex(8)}"

        for order in created_orders:
            Payment.objects.create(
                order=order,
                status=Payment.Status.PENDING,
                amount=order.total,
                provider=provider,
                provider_reference=pi_id,
            )

        return Response({
            "order_ids": order_ids,
            "grand_total": str(grand_total),
            "client_secret": client_secret,
            "payment_intent_id": pi_id,
            "provider": provider,
        }, status=status.HTTP_201_CREATED)


class PaymentVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .payment_completion import finalize_order_payment
        from .payments import verify_payment_intent_succeeded

        pi_id = (request.data.get("payment_intent_id") or "").strip()
        if not pi_id:
            return Response({"detail": "Missing payment_intent_id."}, status=400)

        order_ids = request.data.get("order_ids") or []
        if not order_ids:
            order_ids = list(
                Payment.objects.filter(
                    provider_reference=pi_id,
                    order__buyer=request.user,
                ).values_list("order_id", flat=True)
            )
        if not order_ids:
            return Response({"detail": "No orders found for this payment."}, status=400)

        for oid in order_ids:
            ok, err = verify_payment_intent_succeeded(
                payment_intent_id=pi_id, expected_order_id=int(oid)
            )
            if not ok:
                return Response({"detail": err or "Payment not verified."}, status=400)
            st, err2 = finalize_order_payment(order_id=int(oid), payment_intent_id=pi_id)
            if st == "error":
                return Response({"detail": err2 or "Could not finalize order."}, status=400)

        return Response({"status": "confirmed", "order_ids": list(order_ids)})


# ─── Orders (buyer-facing) ────────────────────────────────────────────────────

class OrderListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related(
            "order_items__item__category",
            "order_items__item__photos",
            "order_items__shipping_requests",
            "order_items__disputes",
        )


class PurchasesListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related(
            "order_items__item__category",
            "order_items__item__photos",
            "order_items__shipping_requests",
            "order_items__disputes",
        )


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        return (
            Order.objects.filter(buyer=self.request.user)
            .select_related("shipping_address")
            .prefetch_related(
                "order_items__item__photos",
                "order_items__item__vehicle__seller",
                "order_items__shipping_requests",
                "order_items__seller_reviews",
                "order_items__disputes",
                "payments",
            )
        )


class BuyerConfirmDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, buyer=request.user)
        if order.status not in (Order.Status.SHIPPED, Order.Status.CONFIRMED):
            return Response(
                {"detail": "Order cannot be marked as delivered in its current state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _mark_order_delivered(order)
        return Response({"status": order.status})


def _mark_order_delivered(order: Order) -> None:
    """Mark an order delivered and schedule payout eligibility for each item."""
    from datetime import timedelta
    from django.utils import timezone

    now = timezone.now()
    hold_hours = int(getattr(settings, "PAYOUT_HOLD_HOURS", 24))
    eligible_at = now + timedelta(hours=hold_hours)

    order.status = Order.Status.DELIVERED
    order.delivered_at = now
    order.save(update_fields=["status", "delivered_at"])

    order.order_items.filter(payout_transferred=False).update(
        transfer_eligible_at=eligible_at
    )
    logger.info("Order %s marked delivered; payouts eligible at %s", order.id, eligible_at)


# ─── Disputes ─────────────────────────────────────────────────────────────────

class DisputeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        disputes = Dispute.objects.filter(buyer=request.user).prefetch_related("messages")
        return Response(DisputeSerializer(disputes, many=True).data)

    def post(self, request, order_item_id):
        order_item = get_object_or_404(OrderItem, pk=order_item_id, order__buyer=request.user)
        ser = DisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dispute = ser.save(
            order_item=order_item,
            buyer=request.user,
            seller=order_item.item.vehicle.seller,
        )
        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


class DisputeDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DisputeSerializer

    def get_queryset(self):
        from django.db.models import Q
        return Dispute.objects.filter(
            Q(buyer=self.request.user) | Q(seller=self.request.user)
        ).prefetch_related("messages__sender", "order_item__item")


class DisputeMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, dispute_id):
        dispute = get_object_or_404(Dispute, pk=dispute_id)
        if request.user not in (dispute.buyer, dispute.seller) and not request.user.is_staff:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        ser = DisputeMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if request.user == dispute.buyer:
            role = DisputeMessage.SenderRole.BUYER
        elif request.user == dispute.seller:
            role = DisputeMessage.SenderRole.SELLER
        else:
            role = DisputeMessage.SenderRole.SUPPORT
        msg = ser.save(dispute=dispute, sender=request.user, sender_role=role)
        return Response(DisputeMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class SellerReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_item_id):
        order_item = get_object_or_404(OrderItem, pk=order_item_id, order__buyer=request.user)
        ser = SellerReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        review = ser.save(
            order_item=order_item,
            buyer=request.user,
            seller=order_item.item.vehicle.seller,
        )
        return Response(SellerReviewSerializer(review).data, status=status.HTTP_201_CREATED)


# ─── Seller-facing ────────────────────────────────────────────────────────────

class SellerSalesListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SellerSaleSerializer

    def get_queryset(self):
        seller = self.request.user
        order_ids = OrderItem.objects.filter(
            item__vehicle__seller=seller
        ).values_list("order_id", flat=True).distinct()
        return (
            Order.objects.filter(id__in=order_ids)
            .select_related("shipping_address", "buyer")
            .prefetch_related("order_items__item__vehicle", "order_items__shipping_requests")
            .order_by("-placed_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["seller"] = self.request.user
        return ctx


class SellerOrderDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SellerOrderDetailSerializer

    def get_queryset(self):
        seller = self.request.user
        order_ids = OrderItem.objects.filter(
            item__vehicle__seller=seller
        ).values_list("order_id", flat=True).distinct()
        return (
            Order.objects.filter(id__in=order_ids)
            .select_related("shipping_address", "buyer")
            .prefetch_related(
                "order_items__item__photos",
                "order_items__item__vehicle__generation__car_model__make",
                "order_items__shipping_requests",
                "payments",
            )
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["seller"] = self.request.user
        return ctx


class SellerActionQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = (
            OrderItem.objects.filter(
                item__vehicle__seller=request.user,
                order__status__in=["confirmed", "shipped"],
            )
            .select_related("item", "order")
            .prefetch_related("shipping_requests")
        )
        queue = []
        for oi in items:
            sr = oi.shipping_requests.first()
            if not sr or not sr.tracking_number:
                queue.append({
                    "id": oi.order_id,
                    "part": oi.item.title if oi.item else "",
                    "state": oi.order.status,
                    "needs_shipment": True,
                    "needs_pickup_schedule": False,
                })
        return Response(queue)


class SellerShippingPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        oi = OrderItem.objects.filter(
            order=order, item__vehicle__seller=request.user
        ).select_related("item").first()
        if not oi:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        item = oi.item
        return Response({
            "package_length_in": str(float(item.dim_l_in or 16)),
            "package_width_in": str(float(item.dim_w_in or 12)),
            "package_height_in": str(float(item.dim_h_in or 8)),
            "package_weight_lb": str(float(item.weight_lbs or 11)),
        })

    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order_items = OrderItem.objects.filter(
            order=order, item__vehicle__seller=request.user
        ).prefetch_related("shipping_requests")
        if not order_items.exists():
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        tracking = (request.data.get("tracking_number") or "").strip()
        carrier = (request.data.get("carrier") or "").strip()

        for oi in order_items:
            sr = oi.shipping_requests.first()
            if sr and tracking:
                sr.tracking_number = tracking
                sr.carrier = carrier
                sr.save(update_fields=["tracking_number", "carrier"])

        if tracking and order.status == Order.Status.CONFIRMED:
            order.status = Order.Status.SHIPPED
            order.save(update_fields=["status"])

        return Response({"detail": "Saved."})


class SellerConnectOnboardView(APIView):
    """
    POST: Return a Stripe Connect Express onboarding URL.
    Creates the Connect account if the seller doesn't have one yet.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .stripe_connect import create_onboarding_link, get_or_create_connect_account
        seller = request.user
        frontend = (getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000") or "").rstrip("/")
        try:
            account_id = get_or_create_connect_account(seller)
            url = create_onboarding_link(
                account_id,
                return_url=f"{frontend}/money/connect/return",
                refresh_url=f"{frontend}/money/connect/return?refresh=1",
            )
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.error("Connect onboard error user=%s: %s", seller.id, exc)
            return Response({"detail": "Could not start onboarding."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"url": url})


class SellerConnectRefreshView(APIView):
    """
    POST: Re-fetch Connect account status from Stripe and update DB.
    Called after the seller returns from the Stripe onboarding flow.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .stripe_connect import sync_account_status
        seller = request.user
        if not seller.stripe_connect_account_id:
            return Response({"detail": "No Connect account found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            result = sync_account_status(seller)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if "error" in result:
            return Response({"detail": result["error"]}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({
            "details_submitted": result["details_submitted"],
            "payouts_enabled": result["payouts_enabled"],
        })


class SellerMoneySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from decimal import Decimal as D
        from django.db.models import Sum
        seller = request.user

        in_progress = OrderItem.objects.filter(
            item__vehicle__seller=seller,
            order__status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED],
        )
        in_escrow = in_progress.aggregate(s=Sum("price_at_purchase"))["s"] or 0

        # Available: query Stripe Connect balance if fully onboarded, else fall back to DB total
        net_available_usd = "0.00"
        if seller.stripe_connect_payouts_enabled and seller.stripe_connect_account_id:
            from .stripe_payout import get_connect_available_usd
            try:
                bal, err = get_connect_available_usd(stripe_account_id=seller.stripe_connect_account_id)
                if bal is not None:
                    net_available_usd = str(bal)
            except Exception:
                pass
        else:
            # Show DB-calculated total for delivered orders (not yet transferred)
            delivered = OrderItem.objects.filter(
                item__vehicle__seller=seller, order__status=Order.Status.DELIVERED
            )
            total_earned = delivered.aggregate(s=Sum("price_at_purchase"))["s"] or 0
            fee_rate = D(str(getattr(settings, "PLATFORM_FEE_RATE", "0.05")))
            net = D(str(total_earned)) * (D("1") - fee_rate)
            net_available_usd = str(net.quantize(D("0.01")))

        recent = (
            OrderItem.objects.filter(item__vehicle__seller=seller)
            .select_related("order", "item__vehicle__generation__car_model__make")
            .order_by("-order__placed_at")[:25]
        )
        lines = []
        for oi in recent:
            item = oi.item
            v = item.vehicle if item else None
            gen = v.generation if v else None
            make = gen.car_model.make.name if gen else ""
            model = gen.car_model.name if gen else ""
            lines.append({
                "order_id": oi.order_id,
                "part_label": item.title if item else "",
                "vin": v.vin if v else "",
                "vehicle_title": f"{v.year or ''} {make} {model}".strip() if v else "",
                "amount_usd": str(oi.price_at_purchase),
                "state": oi.order.status,
            })

        payout_ready = (
            seller.stripe_connect_payouts_enabled
            and float(net_available_usd) > 0
        )

        return Response({
            "balance": {
                "escrow_total_usd": str(round(float(in_escrow), 2)),
                "net_available_usd": net_available_usd,
            },
            "connect": {
                "account_id": seller.stripe_connect_account_id or None,
                "details_submitted": seller.stripe_connect_details_submitted,
                "payouts_enabled": seller.stripe_connect_payouts_enabled,
                "onboarded_at": seller.stripe_connect_onboarded_at,
            },
            "platform_fee_rate": str(getattr(settings, "PLATFORM_FEE_RATE", "0.05")),
            "earnings_lines": lines,
            "payout_ready": payout_ready,
        })


class SellerVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Legacy stub kept for backwards compatibility
        return Response({"detail": "Use /orders/connect/onboard/ for Stripe Connect onboarding."})


class SellerCashoutView(APIView):
    """
    POST: Trigger an on-demand payout from the seller's Connect account to their bank.
    Stripe Express accounts auto-pay on a schedule; this is for manual on-demand requests.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal as D
        from .stripe_payout import get_connect_available_usd, payout_available_to_bank
        seller = request.user

        if not seller.stripe_connect_account_id:
            return Response({"detail": "No Connect account. Complete onboarding first."}, status=status.HTTP_400_BAD_REQUEST)
        if not seller.stripe_connect_payouts_enabled:
            return Response({"detail": "Connect account not fully verified yet."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            available, err = get_connect_available_usd(stripe_account_id=seller.stripe_connect_account_id)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if err:
            return Response({"detail": err}, status=status.HTTP_502_BAD_GATEWAY)
        if available is None or available <= D("0"):
            return Response({"detail": "No available balance to pay out."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ok, err = payout_available_to_bank(
                stripe_account_id=seller.stripe_connect_account_id,
                amount_usd=available,
            )
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not ok:
            return Response({"detail": err or "Payout failed."}, status=status.HTTP_400_BAD_REQUEST)

        logger.info("Cashout triggered user=%s amount=%s", seller.id, available)
        return Response({"detail": f"Payout of ${available} initiated to your bank account."})
