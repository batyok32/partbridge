"""Finalize orders paid with cash (test flow — no Stripe charge)."""

from __future__ import annotations

import logging

from django.db import transaction

from vehicles.models import VehiclePart

from .models import CartItem, Order

logger = logging.getLogger(__name__)


def finalize_cash_order_payment(*, order_id: int) -> tuple[str, str | None]:
    """
    Move a cash payment_method order from PAYMENT_PENDING into escrow (same as paid).
    Returns ("completed", None) or ("already_done", None) or ("error", message).
    """
    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .select_related("vehicle_part")
            .get(pk=order_id)
        )
        if order.payment_method != Order.PaymentMethod.CASH:
            return "error", "This order is not a cash test checkout."
        if order.state != Order.State.PAYMENT_PENDING:
            return "already_done", None

        order.enter_escrow()
        part = order.vehicle_part
        part.listing_state = VehiclePart.ListingState.SOLD
        part.save(update_fields=["listing_state", "updated_at"])
        if order.source_cart_item_id:
            CartItem.objects.filter(pk=order.source_cart_item_id, user_id=order.buyer_id).delete()

    return "completed", None
