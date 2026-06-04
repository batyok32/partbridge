from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def finalize_order_payment(*, order_id: int, payment_intent_id: str) -> tuple[str, str | None]:
    from .models import CartBundle, CartItem, Order, Payment
    from bundles.models import Bundle
    from parts.models import Item

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None:
            return "error", "Order not found."
        if order.status == Order.Status.CONFIRMED:
            return "already_done", None
        if order.status != Order.Status.PENDING:
            return "error", f"Order status is {order.status}."

        item_ids = list(order.order_items.values_list("item_id", flat=True))
        Item.objects.filter(id__in=item_ids).update(status=Item.Status.SOLD)

        for oi in order.order_items.select_related("item__assembly_bundle").prefetch_related(
            "item__assembly_bundle__bundle_items"
        ).all():
            if oi.item and oi.item.assembly_bundle_id:
                assem = oi.item.assembly_bundle
                comp_ids = list(assem.bundle_items.values_list("item_id", flat=True))
                Item.objects.filter(id__in=comp_ids).update(status=Item.Status.SOLD)
                Bundle.objects.filter(pk=assem.pk).update(status=Bundle.Status.DISBANDED)

        Payment.objects.update_or_create(
            order=order,
            provider_reference=payment_intent_id,
            defaults={
                "status": Payment.Status.CAPTURED,
                "amount": order.total,
                "provider": "stripe",
                "paid_at": timezone.now(),
            },
        )

        order.status = Order.Status.CONFIRMED
        order.save(update_fields=["status"])

        CartItem.objects.filter(user_id=order.buyer_id).delete()
        CartBundle.objects.filter(user_id=order.buyer_id).delete()

    return "completed", None
