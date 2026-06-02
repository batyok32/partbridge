"""
MVP shipping / transit hints for buyer discovery (Phase 5).
Not a carrier quote — copy only until real rate shopping (Phase 8+).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any


def shipping_amount_for_mode(preview: dict[str, Any], mode: str) -> Decimal:
    """Resolve selected checkout/cart shipping line from a shipping_preview_stub dict."""
    m = (mode or "standard").strip().lower()
    if m == "pickup":
        if not (preview.get("pickup") or {}).get("available"):
            raise ValueError("Pickup is not available for this listing.")
        return Decimal("0")
    delivery = preview.get("delivery") or {}
    if m == "next_day":
        if delivery.get("next_day_usd") is None:
            raise ValueError("Next-day delivery is not available for this route.")
        return Decimal(str(delivery["next_day_usd"]))
    if m == "standard":
        return Decimal(str(delivery.get("standard_usd", 0)))
    raise ValueError("Invalid shipping mode.")


def mask_zip(zip_code: str | None) -> str:
    z = (zip_code or "").strip()
    if len(z) >= 5 and z[:5].isdigit():
        return z[:3] + "xx"
    if z:
        return z[: min(3, len(z))] + ("…" if len(z) > 3 else "")
    return ""


def _digits5(zip_code: str | None) -> str | None:
    if not zip_code:
        return None
    m = re.search(r"(\d{5})", zip_code.strip())
    return m.group(1) if m else None


def shipping_preview_stub(
    *,
    seller_state: str,
    seller_zip: str,
    buyer_zip: str,
    package_weight_kg: float | int | None = None,
    pickup_allowed: bool = False,
) -> dict[str, Any]:
    """
    Rough transit copy from seller origin to buyer ZIP (US only, MVP).
    Washington first: in-state / neighboring ZIP prefixes get shorter copy.
    """
    b = _digits5(buyer_zip)
    if not b:
        return {
            "available": False,
            "note": "Enter a valid US ZIP code to see a rough transit estimate.",
            "shipping_options": [],
        }

    ss = (seller_state or "").strip().upper() or "—"
    sz = mask_zip(seller_zip)
    pre = int(b[:3])
    in_wa = ss == "WA" and 980 <= pre <= 994
    close_wa = 980 <= pre <= 986

    lbs = (float(package_weight_kg or 0) * 2.20462) if package_weight_kg else 0.0
    if lbs <= 10:
        size = "small"
    elif lbs <= 50:
        size = "medium"
    else:
        size = "large"

    matrix = {
        "small": {"in_40": 12, "in_40_next": 24, "in_state_far": 20, "in_state_far_next": 35, "national": 20},
        "medium": {"in_40": 25, "in_40_next": 50, "in_state_far": 50, "in_state_far_next": 90, "national": 50},
        "large": {"in_40": 100, "in_40_next": 200, "in_state_far": 200, "in_state_far_next": 350, "national": 220},
    }
    m = matrix[size]

    if in_wa:
        if close_wa:
            delivery = {"standard_usd": m["in_40"], "next_day_usd": m["in_40_next"], "zone": "same_state_40mi"}
        else:
            delivery = {"standard_usd": m["in_state_far"], "next_day_usd": m["in_state_far_next"], "zone": "same_state_far"}
        estimate = "In-state shipments depart Wednesday and Saturday."
    else:
        delivery = {"standard_usd": m["national"], "next_day_usd": None, "zone": "national"}
        estimate = "National shipping can take up to 7 days."

    options = []
    if ss == "WA" and pickup_allowed:
        options.append(
            {
                "code": "pickup",
                "label": "Local pickup",
                "usd": 0,
                "note": "Coordinate pickup with seller after purchase.",
            }
        )
    options.append(
        {
            "code": "standard",
            "label": "Standard delivery",
            "usd": delivery["standard_usd"],
            "note": estimate,
        }
    )
    if delivery.get("next_day_usd") is not None:
        options.append(
            {
                "code": "next_day",
                "label": "Next-day delivery",
                "usd": delivery["next_day_usd"],
                "note": "Where available for this route.",
            }
        )

    return {
        "available": True,
        "seller_region": f"{ss} {sz}".strip(),
        "buyer_zip_prefix": b[:3] + "**",
        "estimate": estimate,
        "size_tier": size,
        "size_tier_label": {"small": "Small", "medium": "Medium", "large": "Large"}.get(size, size),
        "delivery": delivery,
        "pickup": {
            "available": ss == "WA" and pickup_allowed,
            "note": "Local pickup when the seller enables it for this vehicle.",
        },
        "shipping_options": options,
        "dispatch_days_in_state": ["Wednesday", "Saturday"] if ss == "WA" else [],
        "disclaimer": "Estimated shipping only. Final amount may vary by dimensions, weight, and carrier rules.",
    }
