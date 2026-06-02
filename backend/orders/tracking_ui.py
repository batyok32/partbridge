"""Buyer-facing progress steps for an order (UI + API)."""

from __future__ import annotations

from .models import Order


def _step_index(state: str) -> int:
    """Map DB state to a 0-based step (payment → preparing → label → transit → delivered)."""
    st = state
    if st == Order.State.PAYMENT_PENDING:
        return 0
    if st in (Order.State.PAID_ESCROW, Order.State.SELLER_CONFIRMED):
        return 1
    if st == Order.State.LABEL_PURCHASED:
        return 2
    if st == Order.State.SHIPPED:
        return 3
    if st in (Order.State.DELIVERED, Order.State.AVAILABLE_FOR_PAYOUT):
        return 4
    if st in (Order.State.REFUND_PENDING, Order.State.HOLD):
        return 1
    return 1


def build_tracking_steps(order: Order) -> list[dict]:
    st = order.state
    if st in (Order.State.REFUNDED, Order.State.CANCELLED):
        return [
            {
                "key": "closed",
                "label": st.replace("_", " ").title(),
                "description": "This order is closed.",
                "complete": True,
                "current": True,
            }
        ]

    labels = [
        ("payment", "Payment", "Awaiting or confirming payment"),
        ("preparing", "Preparing", "Paid — seller packs and schedules carrier pickup"),
        ("label", "Pickup / label", "Label ready or carrier pickup scheduled"),
        ("transit", "On the way", "Shipped / in transit to you"),
        ("delivered", "Delivered", "Delivery complete"),
    ]
    si = _step_index(st)

    out = []
    for i, (key, title, desc) in enumerate(labels):
        out.append(
            {
                "key": key,
                "label": title,
                "description": desc,
                "complete": i < si,
                "current": i == si,
            }
        )
    return out
