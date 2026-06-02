"""Payment completion — v4 stub (old Stripe flow removed with model rewrite)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def finalize_order_payment(*, order_id: int, payment_intent_id: str) -> tuple[str, str | None]:
    """Stub — implement with new Payment model."""
    return "error", "Not implemented in v4."
