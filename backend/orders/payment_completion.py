from __future__ import annotations

import logging

from django.db import transaction

from vehicles.models import VehiclePart

from .models import CartItem, Order
from .notifications import send_order_email, send_order_sms
from .payments import verify_payment_intent_succeeded

logger = logging.getLogger(__name__)


def finalize_order_payment(*, order_id: int, payment_intent_id: str) -> tuple[str, str | None]:
    """
    After Stripe reports success, verify the PaymentIntent and move the order into escrow.

    Idempotent: if the order is no longer PAYMENT_PENDING, returns ("already_done", None)
    without sending notifications again.

    Returns:
        ("completed", None) on success
        ("already_done", None) if the order was already finalized
        ("error", message) on verification or unexpected failure
    """
    pi_id = (payment_intent_id or "").strip()
    ok, err = verify_payment_intent_succeeded(
        payment_intent_id=pi_id,
        expected_order_id=order_id,
    )
    if not ok:
        return "error", err or "Payment verification failed."

    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .select_related("vehicle_part")
            .get(pk=order_id)
        )
        if order.state != Order.State.PAYMENT_PENDING:
            return "already_done", None

        order.enter_escrow()
        part = order.vehicle_part
        part.listing_state = VehiclePart.ListingState.SOLD
        part.save(update_fields=["listing_state", "updated_at"])
        if order.source_cart_item_id:
            CartItem.objects.filter(pk=order.source_cart_item_id, user_id=order.buyer_id).delete()

    _notify_seller_paid(order)
    return "completed", None


def _notify_seller_paid(order: Order) -> None:
    send_order_email(
        to_email=order.seller.email,
        subject=f"Buyer paid — order #{order.id}",
        body=(
            f"Buyer paid for {order.vehicle_part.label} (order #{order.id}).\n"
            "Open Sales & fulfillment to enter package size (in / lb) and schedule a carrier pickup window.\n"
        ),
    )
    send_order_sms(
        to_phone=order.seller.phone,
        message=f"Paid order #{order.id}. Schedule pickup in your seller dashboard.",
    )
