"""Cash payment — v4 stub."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def finalize_cash_order_payment(*, order_id: int) -> tuple[str, str | None]:
    """Stub — implement with new Payment model."""
    return "error", "Not implemented in v4."
