from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from celery import shared_task

from orders.models import Order, SellerVerification
from vehicles.models import VehiclePart


@shared_task
def enforce_first_sale_verification_deadline() -> dict:
    """
    5-day reminder rule:
    - do not block fulfillment
    - keep payouts blocked and mark overdue until seller verification completes
    """
    now = timezone.now()
    affected_orders = Order.objects.filter(
        state__in=[
            Order.State.PAID_ESCROW,
            Order.State.SELLER_CONFIRMED,
            Order.State.LABEL_PURCHASED,
            Order.State.SHIPPED,
            Order.State.DELIVERED,
            Order.State.AVAILABLE_FOR_PAYOUT,
        ],
        payout_blocked=True,
        payout_block_deadline__isnull=False,
        payout_block_deadline__lt=now,
    ).select_related("seller")

    overdue = 0
    with transaction.atomic():
        for order in affected_orders:
            order.payout_block_reason = (
                "Cashout blocked: complete ID + SSN + Connect verification."
            )
            order.save(update_fields=["payout_block_reason", "updated_at"])
            overdue += 1

            ver = SellerVerification.objects.filter(user=order.seller).first()
            if ver and ver.payout_ready:
                continue
    return {"overdue_payout_blocks": overdue}


@shared_task
def auto_cancel_unconfirmed_paid_orders() -> dict:
    """
    Seller has 24h to confirm.
    If not confirmed in time: auto-cancel, refund, and deactivate listing.
    """
    now = timezone.now()
    qs = Order.objects.filter(
        state=Order.State.PAID_ESCROW,
        seller_confirmed_at__isnull=True,
        seller_confirmation_due_at__isnull=False,
        seller_confirmation_due_at__lt=now,
    ).select_related("vehicle_part")

    cancelled = 0
    with transaction.atomic():
        for order in qs:
            order.state = Order.State.REFUNDED
            order.cancelled_at = now
            order.refunded_at = now
            order.auto_cancelled_for_no_confirm_at = now
            order.save(
                update_fields=[
                    "state",
                    "cancelled_at",
                    "refunded_at",
                    "auto_cancelled_for_no_confirm_at",
                    "updated_at",
                ]
            )
            part = order.vehicle_part
            part.listing_state = VehiclePart.ListingState.UNAVAILABLE
            part.save(update_fields=["listing_state", "updated_at"])
            cancelled += 1

    return {"auto_cancelled_orders": cancelled}
