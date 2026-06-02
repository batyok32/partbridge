from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


def _order_amount_cents(amount) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


@dataclass
class PaymentIntentResult:
    payment_intent_id: str
    client_secret: str
    provider: str


def stripe_configured() -> bool:
    return bool((getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip())


def create_payment_intent(*, amount_cents: int, currency: str, order_id: int) -> PaymentIntentResult:
    """
    Stripe-style payment intent creation.
    Uses Stripe SDK if available and key configured; otherwise returns a local stub.
    """
    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if key:
        try:
            import stripe  # type: ignore

            stripe.api_key = key
            pi = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata={"order_id": str(order_id)},
                automatic_payment_methods={"enabled": True},
            )
            return PaymentIntentResult(
                payment_intent_id=str(pi["id"]),
                client_secret=str(pi["client_secret"]),
                provider="stripe",
            )
        except Exception as exc:
            logger.warning("Stripe PaymentIntent.create failed: %s", exc)

    stub_id = f"pi_stub_{order_id}_{secrets.token_hex(4)}"
    stub_secret = f"{stub_id}_secret_{secrets.token_hex(8)}"
    return PaymentIntentResult(
        payment_intent_id=stub_id,
        client_secret=stub_secret,
        provider="stub",
    )


def create_stripe_checkout_session_for_orders(orders) -> str:
    """
    Hosted Stripe Checkout for one or more pending orders (same buyer, same currency).
    The PaymentIntent is created when the buyer pays; metadata includes order_ids.
    Returns the hosted checkout URL.
    """
    order_list = list(orders)
    if not order_list:
        raise RuntimeError("No orders.")
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY).")
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Stripe SDK not installed.") from exc

    buyer_id = order_list[0].buyer_id
    currency = (getattr(order_list[0], "currency", None) or "usd").lower()
    for o in order_list:
        if o.buyer_id != buyer_id:
            raise RuntimeError("Orders must belong to the same buyer.")
        if (getattr(o, "currency", None) or "usd").lower() != currency:
            raise RuntimeError("Mixed currencies are not supported in one checkout.")

    stripe.api_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    frontend = (
        getattr(settings, "FRONTEND_URL", None)
        or getattr(settings, "FRONTEND_BASE_URL", "")
        or "http://localhost:3000"
    ).rstrip("/")

    ids_str = ",".join(str(o.id) for o in order_list)
    test_usd_raw = (getattr(settings, "STRIPE_CHECKOUT_TEST_AMOUNT_USD", "") or "").strip()
    if test_usd_raw:
        try:
            test_cents = int((Decimal(test_usd_raw) * 100).quantize(Decimal("1")))
        except Exception:
            test_cents = 100
        if test_cents < 50:
            logger.warning("STRIPE_CHECKOUT_TEST_AMOUNT_USD results in amount < $0.50; Stripe may reject.")
        line_items = [
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": max(test_cents, 50),
                    "product_data": {
                        "name": f"Test payment (${test_usd_raw}) — orders {ids_str}"[:120],
                    },
                },
                "quantity": 1,
            }
        ]
    else:
        line_items = []
        for order in order_list:
            label = (getattr(order.vehicle_part, "label", None) or "Order")[:120]
            amount_cents = _order_amount_cents(order.amount_usd)
            line_items.append(
                {
                    "price_data": {
                        "currency": currency,
                        "unit_amount": amount_cents,
                        "product_data": {"name": f"Order #{order.id} — {label}"},
                    },
                    "quantity": 1,
                }
            )

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        metadata={"order_ids": ids_str},
        payment_intent_data={"metadata": {"order_ids": ids_str}},
        client_reference_id=ids_str[:255],
        success_url=f"{frontend}/orders/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend}/purchases?payment_canceled=1",
    )
    url = session.get("url") if isinstance(session, dict) else getattr(session, "url", None)
    if not url:
        raise RuntimeError("Stripe did not return a checkout URL.")
    return str(url)


def _parse_order_ids_from_checkout_metadata(meta, client_reference_id) -> list[int]:
    if hasattr(meta, "get"):
        raw = meta.get("order_ids") or meta.get("order_id")
    else:
        raw = getattr(meta, "order_ids", None) or getattr(meta, "order_id", None)
    if not raw and client_reference_id:
        raw = client_reference_id
    if not raw:
        return []
    s = str(raw).strip()
    if "," in s:
        out = []
        for x in s.split(","):
            x = x.strip()
            if not x:
                continue
            try:
                out.append(int(x))
            except ValueError:
                return []
        return out
    try:
        return [int(s)]
    except (TypeError, ValueError):
        return []


def verify_checkout_session_and_finalize(*, session_id: str, buyer_id: int) -> tuple[str, str | None, int | None]:
    """
    After redirect from Stripe Checkout, retrieve the session and finalize every order in the session.
    Returns (status, error_message_or_none, first_order_id_or_none).
    """
    if not stripe_configured():
        return "error", "Stripe is not configured.", None
    if not session_id or not str(session_id).startswith("cs_"):
        return "error", "Invalid session.", None
    try:
        import stripe  # type: ignore
    except ImportError:
        return "error", "Stripe SDK not installed.", None

    stripe.api_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        logger.warning("Stripe Session.retrieve failed: %s", exc)
        return "error", "Could not verify checkout session.", None

    meta = getattr(session, "metadata", None) or {}
    cref = getattr(session, "client_reference_id", None)
    order_ids = _parse_order_ids_from_checkout_metadata(meta, cref)
    if not order_ids:
        return "error", "Checkout session is missing order reference.", None

    from .models import Order

    pay_status = getattr(session, "payment_status", None)
    if pay_status != "paid":
        return "error", "Payment is not complete yet.", None

    pi_id = getattr(session, "payment_intent", None)
    if not pi_id:
        return "error", "Checkout session has no payment intent.", None

    from .payment_completion import finalize_order_payment

    first_id: int | None = None
    for oid in order_ids:
        order = Order.objects.filter(pk=oid, buyer_id=buyer_id).first()
        if order is None:
            return "error", "Order not found or access denied.", None
        st, err = finalize_order_payment(order_id=order.id, payment_intent_id=str(pi_id))
        if st == "error":
            return "error", err or "Verification failed.", None
        if first_id is None:
            first_id = order.id
    return "completed", None, first_id


def verify_payment_intent_succeeded(*, payment_intent_id: str, expected_order_id: int) -> tuple[bool, str]:
    """
    When Stripe is configured, confirms the PaymentIntent exists, succeeded, and matches the order
    (single order_id or multi order_ids metadata from Checkout).
    """
    pi_id = (payment_intent_id or "").strip()
    if not pi_id:
        if stripe_configured():
            return False, "Missing payment intent."
        return True, ""

    if pi_id.startswith("pi_stub_"):
        if stripe_configured():
            return False, "Invalid payment reference."
        return True, ""

    key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not key:
        return True, ""
    try:
        import stripe  # type: ignore

        stripe.api_key = key
        pi = stripe.PaymentIntent.retrieve(pi_id)
    except Exception as exc:
        logger.warning("Stripe PaymentIntent.retrieve failed: %s", exc)
        return False, "Could not verify payment with Stripe."
    if pi.status != "succeeded":
        return False, "Payment has not completed successfully."
    md = getattr(pi, "metadata", None) or {}
    order_id_meta = md.get("order_id") if hasattr(md, "get") else getattr(md, "order_id", None)
    order_ids_meta = md.get("order_ids") if hasattr(md, "get") else getattr(md, "order_ids", None)
    if order_ids_meta:
        ids = []
        for x in str(order_ids_meta).split(","):
            x = x.strip()
            if not x:
                continue
            try:
                ids.append(int(x))
            except ValueError:
                return False, "Payment does not match this order."
        if expected_order_id in ids:
            return True, ""
        return False, "Payment does not match this order."
    if str(order_id_meta or "") == str(expected_order_id):
        return True, ""
    return False, "Payment does not match this order."
