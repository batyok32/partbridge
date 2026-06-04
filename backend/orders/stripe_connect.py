"""Stripe Connect Express account management for sellers."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _stripe():
    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not key:
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY missing).")
    try:
        import stripe  # type: ignore
        stripe.api_key = key
        return stripe
    except ImportError:
        raise RuntimeError("Stripe SDK not installed.")


def get_or_create_connect_account(user) -> str:
    """Return the seller's stripe_connect_account_id, creating an Express account if needed."""
    if user.stripe_connect_account_id:
        return user.stripe_connect_account_id
    stripe = _stripe()
    account = stripe.Account.create(
        type="express",
        email=user.email,
        capabilities={"transfers": {"requested": True}},
        metadata={"user_id": str(user.id)},
    )
    user.stripe_connect_account_id = account["id"]
    user.save(update_fields=["stripe_connect_account_id"])
    logger.info("Created Connect account %s for user=%s", account["id"], user.id)
    return account["id"]


def create_onboarding_link(account_id: str, *, return_url: str, refresh_url: str) -> str:
    """Return a one-time Stripe-hosted onboarding URL."""
    stripe = _stripe()
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link["url"]


def sync_account_status(user) -> dict:
    """
    Fetch the Connect account from Stripe and update the user's DB flags.
    Safe to call repeatedly; only writes when something changed.
    Returns a dict with current status or {"error": ...}.
    """
    if not user.stripe_connect_account_id:
        return {"details_submitted": False, "payouts_enabled": False}
    stripe = _stripe()
    try:
        account = stripe.Account.retrieve(user.stripe_connect_account_id)
    except Exception as exc:
        logger.warning("Account.retrieve failed user=%s: %s", user.id, exc)
        return {"error": str(exc)}

    from django.utils import timezone

    details = bool(account.get("details_submitted"))
    payouts = bool(account.get("payouts_enabled"))

    to_save = []
    if user.stripe_connect_details_submitted != details:
        user.stripe_connect_details_submitted = details
        to_save.append("stripe_connect_details_submitted")
    if user.stripe_connect_payouts_enabled != payouts:
        user.stripe_connect_payouts_enabled = payouts
        to_save.append("stripe_connect_payouts_enabled")
    if payouts and not user.stripe_connect_onboarded_at:
        user.stripe_connect_onboarded_at = timezone.now()
        to_save.append("stripe_connect_onboarded_at")
    if to_save:
        user.save(update_fields=to_save)

    return {"details_submitted": details, "payouts_enabled": payouts}
