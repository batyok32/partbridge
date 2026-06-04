from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def auto_deliver_shipped_orders() -> dict:
    """
    Auto-mark shipped orders as delivered after AUTO_DELIVER_DAYS days from placed_at.
    Runs periodically via Celery Beat.
    """
    from .models import Order
    from .views import _mark_order_delivered

    days = int(getattr(settings, "AUTO_DELIVER_DAYS", 7))
    cutoff = timezone.now() - timedelta(days=days)

    candidates = Order.objects.filter(
        status=Order.Status.SHIPPED,
        placed_at__lte=cutoff,
    ).prefetch_related("order_items")

    delivered = 0
    for order in candidates:
        try:
            _mark_order_delivered(order)
            delivered += 1
            logger.info("Auto-delivered order %s", order.id)
        except Exception as exc:
            logger.warning("Auto-deliver failed order=%s: %s", order.id, exc)

    return {"auto_delivered": delivered}


@shared_task
def process_seller_payouts() -> dict:
    """
    Transfer earnings to sellers for OrderItems whose hold period has elapsed.
    Skips already-transferred items and items whose seller hasn't connected Stripe.
    """
    from .models import Order, OrderItem
    from .stripe_transfer import transfer_order_item_to_seller

    now = timezone.now()
    eligible = (
        OrderItem.objects.filter(
            payout_transferred=False,
            transfer_eligible_at__lte=now,
            order__status=Order.Status.DELIVERED,
        )
        .select_related("item__vehicle__seller")
    )

    transferred = deferred = errors = 0
    for oi in eligible:
        ok, err = transfer_order_item_to_seller(oi)
        if ok:
            oi.payout_transferred = True
            oi.save(update_fields=["payout_transferred"])
            transferred += 1
        elif err and ("No Connect account" in err or "not fully onboarded" in err):
            deferred += 1
            logger.info("Payout deferred order_item=%s: %s", oi.id, err)
        else:
            errors += 1
            logger.warning("Payout failed order_item=%s: %s", oi.id, err)

    logger.info("process_seller_payouts: transferred=%s deferred=%s errors=%s", transferred, deferred, errors)
    return {"transferred": transferred, "deferred": deferred, "errors": errors}


# ── Legacy stubs (referenced by existing beat schedule entries) ────────────────

@shared_task
def enforce_first_sale_verification_deadline() -> dict:
    return {}


@shared_task
def auto_cancel_unconfirmed_paid_orders() -> dict:
    return {}
