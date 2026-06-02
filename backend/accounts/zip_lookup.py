"""US ZIP → city/state using Zippopotam public API (no key)."""

from __future__ import annotations

import re

import httpx


def lookup_us_zip_digits(zip_code: str) -> dict | None:
    """
    Return primary city/state for a US ZIP (5 digits).
    Response includes up to 5 alternate places when the ZIP spans multiple cities.
    """
    raw = (zip_code or "").strip()
    m = re.search(r"(\d{5})", raw)
    if not m:
        return None
    z = m.group(1)
    try:
        r = httpx.get(f"https://api.zippopotam.us/us/{z}", timeout=5.0)
    except httpx.RequestError:
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    places = data.get("places") or []
    if not places:
        return None
    pc = str(data.get("post code") or z).strip()
    pc5 = re.search(r"(\d{5})", pc)
    postal = pc5.group(1) if pc5 else z

    def place_row(pl: dict) -> dict:
        return {
            "city": (pl.get("place name") or "").strip(),
            "state": (pl.get("state abbreviation") or "").strip().upper()[:2],
        }

    rows = []
    for pl in places[:8]:
        row = place_row(pl)
        if row["city"] and row["state"]:
            rows.append(row)
    if not rows:
        return None
    primary = rows[0]
    return {
        "postal_code": postal,
        "city": primary["city"],
        "state": primary["state"],
        "places": rows,
    }
