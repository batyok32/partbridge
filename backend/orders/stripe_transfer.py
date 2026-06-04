"""Transfer seller earnings from the platform Stripe account to their Connect account."""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


def _fee_rate() -> Decimal:
    return Decimal(str(getattr(settings, "PLATFORM_FEE_RATE", "0.05")))


def transfer_order_item_to_seller(order_item) -> tuple[bool, str | None]:
    """
    Transfer the seller's share (price minus platform fee) to their Connect account.
    Called when an order is marked delivered. Returns (success, error_message).
    """
    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not key:
        return False, "Stripe not configured."
    try:
        import stripe  # type: ignore
        stripe.api_key = key
    except ImportError:
        return False, "Stripe SDK not installed."

    try:
        seller = order_item.item.vehicle.seller
    except AttributeError:
        return False, "Cannot determine seller from order item."

    connect_id = getattr(seller, "stripe_connect_account_id", "")
    if not connect_id:
        logger.info("No Connect account for seller=%s — transfer deferred", seller.id)
        return False, "Seller has no Connect account yet."

    if not getattr(seller, "stripe_connect_payouts_enabled", False):
        logger.info("Connect account not ready for seller=%s — transfer deferred", seller.id)
        return False, "Seller Connect account not fully onboarded."

    amount = Decimal(str(order_item.price_at_purchase))
    fee = (amount * _fee_rate()).quantize(Decimal("0.01"))
    seller_amount = (amount - fee).quantize(Decimal("0.01"))
    cents = int(seller_amount * 100)

    if cents < 50:
        return False, f"Transfer amount {seller_amount} is below Stripe minimum."

    part_title = ""
    try:
        part_title = order_item.item.title or ""
    except Exception:
        pass

    try:
        transfer = stripe.Transfer.create(
            amount=cents,
            currency="usd",
            destination=connect_id,
            metadata={
                "order_id": str(order_item.order_id),
                "order_item_id": str(order_item.id),
                "seller_id": str(seller.id),
                "part": part_title[:100],
                "platform_fee_usd": str(fee),
            },
        )
        logger.info(
            "Transfer %s: order_item=%s seller=%s seller_amount=%s fee=%s",
            transfer["id"], order_item.id, seller.id, seller_amount, fee,
        )
        return True, None
    except Exception as exc:
        logger.warning("Transfer.create failed order_item=%s: %s", order_item.id, exc)
        return False, str(exc)
