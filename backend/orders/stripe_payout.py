"""Stripe Connect payouts to a connected account (real money movement)."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


def get_connect_available_usd(*, stripe_account_id: str) -> tuple[Decimal | None, str | None]:
    """
    Return available balance (USD) on the connected account, or (None, error).
    """
    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not key:
        return None, "Stripe is not configured."
    if not stripe_account_id or not str(stripe_account_id).startswith("acct_"):
        return None, "Seller has no Stripe Connect account id."
    try:
        import stripe  # type: ignore

        stripe.api_key = key
        bal = stripe.Balance.retrieve(stripe_account=stripe_account_id)
    except Exception as exc:
        logger.warning("Stripe Balance.retrieve failed: %s", exc)
        return None, f"Could not read Stripe balance: {exc}"

    available = bal.get("available") or []
    usd_cents = 0
    for row in available:
        if row.get("currency", "").lower() == "usd":
            usd_cents += int(row.get("amount") or 0)
            break
    return (Decimal(usd_cents) / Decimal(100)).quantize(Decimal("0.01")), None


def payout_available_to_bank(*, stripe_account_id: str, amount_usd: Decimal) -> tuple[bool, str | None]:
    """
    Create a Stripe payout from the connected account balance to the seller's default bank.
    amount_usd must be <= available balance.
    """
    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not key:
        return False, "Stripe is not configured."
    if not stripe_account_id:
        return False, "Missing Stripe Connect account id."
    cents = int((amount_usd * 100).quantize(Decimal("1")))
    if cents < 50:
        return False, "Minimum payout is $0.50."
    try:
        import stripe  # type: ignore

        stripe.api_key = key
        stripe.Payout.create(
            amount=cents,
            currency="usd",
            stripe_account=stripe_account_id,
        )
    except Exception as exc:
        logger.warning("Stripe Payout.create failed: %s", exc)
        return False, str(exc)
    return True, None
