"""
AI services for part listing:

1. describe_vehicle_from_images() — Claude vision: full damage/condition description of all visible parts
2. select_part_options() — Claude: choose which car-part.com options apply to this vehicle
3. estimate_part_size() — Claude: estimate package size category and dimensions for a part
4. grade_part() — Derive A/B/C/X grade from mileage + AI description
5. get_option_compatibility() — Perplexity: compatible make/model/year ranges for a part option
6. headlight_type_from_google() — ScrapingBee Google AI: most popular headlight type for make/model/year
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def _claude_api_key() -> str:
    return (getattr(settings, "CLAUDE_API_KEY", "") or "").strip()


def _extract_json(text: str) -> dict | list | None:
    if not text:
        return None
    # Try full text first
    try:
        obj = json.loads(text)
        if isinstance(obj, (dict, list)):
            return obj
    except Exception:
        pass
    # Extract from code block
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Bare object/array
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


def _claude_vision(prompt: str, image_urls: list[str], max_tokens: int = 1500) -> str | None:
    """Call Claude claude-sonnet-4-6 with images."""
    api_key = _claude_api_key()
    if not api_key:
        return None
    content: list[dict] = []
    for url in image_urls[:8]:
        content.append({"type": "image", "source": {"type": "url", "url": url}})
    content.append({"type": "text", "text": prompt})
    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": content}],
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["content"][0]["text"]
    except Exception as exc:
        logger.warning("Claude vision failed: %s", exc)
        return None


def _claude_text(system: str, user: str, max_tokens: int = 800) -> str | None:
    api_key = _claude_api_key()
    if not api_key:
        return None
    try:
        with httpx.Client(timeout=45) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["content"][0]["text"]
    except Exception as exc:
        logger.warning("Claude text failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 1. Describe vehicle from images
# ---------------------------------------------------------------------------

def describe_vehicle_from_images(image_urls: list[str], vehicle_info: dict) -> str:
    """
    Send vehicle images to Claude and get a detailed description of every visible part
    and its condition (dents, scratches, fog, color mismatch, broken pieces, etc.).

    Returns a plain-text description string.
    """
    if not image_urls:
        return ""
    ymm = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}"
    prompt = (
        f"You are a professional auto parts inspector analyzing images of a {ymm.strip()} donor car.\n\n"
        "Examine every visible part and describe its condition in detail. Include:\n"
        "- Headlights: are they foggy, cracked, faded, lens color, LED/Halogen/HID, broken pieces?\n"
        "- Taillights: shape, color, cracked, broken, missing lenses?\n"
        "- Bumpers (front/rear): dents, scratches, cracks, color match to body, missing pieces?\n"
        "- Hood: dents, scratches, color match, rust, hail damage?\n"
        "- Fenders: dents, rust, scratches, color match?\n"
        "- Doors: dents, scratches, rust, window condition, mirror condition?\n"
        "- Roof: dents, rust, sunroof condition?\n"
        "- Frame: any visible damage, bends, or rust?\n"
        "- Windows/Glass: cracks, chips?\n"
        "- Wheels/Tires: curb rash, cracks, tread depth, size?\n"
        "- Body color: what color is the car, are any panels a different color?\n"
        "- Overall assessment: front-end damage, rear-end damage, side damage, rollover signs?\n\n"
        "Be specific and thorough. Note exactly which part is damaged and how.\n"
        "Format as a structured paragraph per section."
    )
    result = _claude_vision(prompt, image_urls, max_tokens=2000)
    return result or ""


# ---------------------------------------------------------------------------
# 2. Select applicable part options
# ---------------------------------------------------------------------------

def select_part_options(
    *,
    vehicle_info: dict,
    part_name: str,
    raw_options: list[dict],
    ai_description: str,
) -> list[dict]:
    """
    Given the scraped car-part.com options and the AI vehicle description,
    decide which options apply and at what confidence.

    Returns list of:
      {"key": str, "label": str, "confidence": float, "needs_manual_check": bool, "is_applicable": bool}
    """
    if not raw_options:
        return []

    ymm = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')} {vehicle_info.get('trim', '')}".strip()
    engine = vehicle_info.get("engine", "")
    transmission = vehicle_info.get("transmission", "")
    color = vehicle_info.get("color", "")

    options_text = "\n".join(f"- {o['label']}" for o in raw_options)
    system = (
        "You are an expert auto parts classifier. "
        "Given a vehicle's details and a list of part options from car-part.com, "
        "determine which options most likely apply to this specific vehicle. "
        "Return ONLY valid JSON matching this schema exactly:\n"
        '{"selected": [{"label": string, "confidence": float 0-1, "needs_manual_check": bool, "is_applicable": bool}]}'
    )
    user = (
        f"Vehicle: {ymm}\nEngine: {engine}\nTransmission: {transmission}\nColor: {color}\n\n"
        f"Part: {part_name}\n\n"
        f"Available options:\n{options_text}\n\n"
        f"Vehicle condition description:\n{ai_description[:800] if ai_description else 'Not available'}\n\n"
        "For each option:\n"
        "- Set is_applicable=true if this vehicle likely has/needs this option\n"
        "- confidence=1.0 if certain, lower if unsure\n"
        "- needs_manual_check=true if confidence < 0.9\n"
        "Return JSON only."
    )
    raw = _claude_text(system, user, max_tokens=600)
    parsed = _extract_json(raw or "") if raw else None
    if not isinstance(parsed, dict):
        return []
    selected = parsed.get("selected") or []
    if not isinstance(selected, list):
        return []

    result = []
    option_labels = {o["label"]: o["key"] for o in raw_options}
    for item in selected:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        key = option_labels.get(label, label.lower().replace(" ", "_"))
        confidence = float(item.get("confidence") or 0.5)
        needs_check = bool(item.get("needs_manual_check") or confidence < 0.9)
        applicable = bool(item.get("is_applicable", True))
        result.append({
            "key": key,
            "label": label,
            "confidence": confidence,
            "needs_manual_check": needs_check,
            "is_applicable": applicable,
        })
    return result


# ---------------------------------------------------------------------------
# 3. Estimate package size
# ---------------------------------------------------------------------------

def estimate_part_size(part_name: str, vehicle_info: dict) -> dict:
    """
    Ask Claude to estimate the packaging category and approximate dimensions for a part.

    Returns:
      {
        "size_category": "small"|"medium"|"large"|"pallet"|"crate",
        "packaged_length_cm": float,
        "packaged_width_cm": float,
        "packaged_height_cm": float,
        "packaged_weight_kg": float,
        "packaging_method": str,
        "notes": str,
      }
    """
    ymm = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}".strip()
    system = (
        "You are an expert auto parts shipper. Estimate the most likely packaged dimensions "
        "and weight for a used auto part. Return ONLY JSON:\n"
        '{"size_category": "small"|"medium"|"large"|"pallet"|"crate", '
        '"packaged_length_cm": number, "packaged_width_cm": number, '
        '"packaged_height_cm": number, "packaged_weight_kg": number, '
        '"packaging_method": string, "notes": string}'
    )
    user = (
        f"Part: {part_name}\nVehicle: {ymm}\n\n"
        "Guidelines:\n"
        "- small (≤50cm any side, ≤10kg): headlights, taillights, small brackets, sensors, modules\n"
        "- medium (≤120cm, ≤30kg): fenders, doors (packed flat), engines, transmissions in a crate\n"
        "- large (pallet 48×48 inches, >30kg): hoods, bumper assemblies, full doors\n"
        "- pallet: heavy items like engines/transmissions/axles that ship on a 48×48 pallet\n"
        "- crate: irregularly shaped large items\n\n"
        "Return only JSON. Be realistic for a used part."
    )
    raw = _claude_text(system, user, max_tokens=300)
    parsed = _extract_json(raw or "") if raw else None
    defaults = {
        "size_category": "small",
        "packaged_length_cm": 50.0,
        "packaged_width_cm": 40.0,
        "packaged_height_cm": 30.0,
        "packaged_weight_kg": 5.0,
        "packaging_method": "Box",
        "notes": "",
    }
    if not isinstance(parsed, dict):
        return defaults
    return {
        "size_category": str(parsed.get("size_category") or "small"),
        "packaged_length_cm": float(parsed.get("packaged_length_cm") or defaults["packaged_length_cm"]),
        "packaged_width_cm": float(parsed.get("packaged_width_cm") or defaults["packaged_width_cm"]),
        "packaged_height_cm": float(parsed.get("packaged_height_cm") or defaults["packaged_height_cm"]),
        "packaged_weight_kg": float(parsed.get("packaged_weight_kg") or defaults["packaged_weight_kg"]),
        "packaging_method": str(parsed.get("packaging_method") or "Box"),
        "notes": str(parsed.get("notes") or ""),
    }


# ---------------------------------------------------------------------------
# 4. Grade part from mileage + AI description
# ---------------------------------------------------------------------------

def grade_part(*, mileage: int | None, ai_description: str, part_name: str) -> str:
    """
    Derive A/B/C/X grade based on mileage and AI condition description.
    Uses heuristics first; falls back to Claude for ambiguous cases.
    """
    if mileage is None:
        # Check description for clues
        if not ai_description:
            return "X"
        desc_lower = ai_description.lower()
        if any(w in desc_lower for w in ("excellent", "perfect", "like new", "no damage", "pristine")):
            return "A"
        if any(w in desc_lower for w in ("significant damage", "major damage", "heavy rust", "frame damage")):
            return "C"
        return "X"

    # Grade by mileage primarily
    if mileage < 60000:
        grade = "A"
    elif mileage < 200000:
        grade = "B"
    else:
        grade = "C"

    # Downgrade if AI description shows damage relevant to this part
    desc_lower = (ai_description or "").lower()
    part_lower = (part_name or "").lower()
    if any(
        w in desc_lower
        for w in ("frame damage", "flood", "fire", "major damage", "write-off", "total loss")
    ):
        grade = "C"
    elif grade == "A" and any(
        w in desc_lower for w in ("dent", "scratch", "crack", "broken", "foggy", "rust")
    ):
        if any(kw in desc_lower for kw in part_lower.split()):
            grade = "B"

    return grade


# ---------------------------------------------------------------------------
# 5. Get compatible vehicles from Perplexity
# ---------------------------------------------------------------------------

def get_option_compatibility(
    *,
    vehicle_info: dict,
    part_name: str,
    option_label: str,
) -> list[dict]:
    """
    Ask Perplexity what other vehicles are compatible with this specific part option.

    Returns list of:
      {"make": str, "model": str, "year_range_start": int, "year_range_end": int, "trim": str, "notes": str}
    """
    api_key = (getattr(settings, "PERPLEXITY_API_KEY", "") or "").strip()
    if not api_key:
        return []

    ymm = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')} {vehicle_info.get('trim', '')}".strip()
    engine = vehicle_info.get("engine", "")
    transmission = vehicle_info.get("transmission", "")

    prompt = (
        "You are an automotive parts fitment expert. "
        "List all vehicle make/model/year ranges that are interchangeable with the given part. "
        "Return ONLY valid JSON:\n"
        '{"compatible": [{"make": string, "model": string, "year_range_start": number, '
        '"year_range_end": number, "trim": string, "notes": string}]}'
    )
    user = (
        f"Vehicle: {ymm}\nEngine: {engine}\nTransmission: {transmission}\n"
        f"Part: {part_name}\nSpecific option/variant: {option_label}\n\n"
        "List all vehicles this exact part will physically fit (same mounting, connectors, dimensions). "
        "Use year ranges, not individual years. Max 10 entries. Return JSON only."
    )
    try:
        with httpx.Client(timeout=25) as client:
            r = client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.1,
                },
            )
            r.raise_for_status()
            body = r.json()
    except Exception as exc:
        logger.warning("Perplexity compatibility failed: %s", exc)
        return []

    content = (((body or {}).get("choices") or [{}])[0].get("message", {}).get("content", ""))
    parsed = _extract_json(content) if content else None
    if not isinstance(parsed, dict):
        return []
    compat = parsed.get("compatible") or []
    if not isinstance(compat, list):
        return []
    result = []
    for item in compat[:10]:
        if not isinstance(item, dict):
            continue
        make = str(item.get("make") or "").strip()
        model = str(item.get("model") or "").strip()
        if not make or not model:
            continue
        try:
            ys = int(item.get("year_range_start") or 0)
            ye = int(item.get("year_range_end") or ys)
        except (TypeError, ValueError):
            continue
        if ys <= 0 or ye <= 0:
            continue
        result.append({
            "make": make,
            "model": model,
            "year_range_start": ys,
            "year_range_end": ye,
            "trim": str(item.get("trim") or "").strip(),
            "notes": str(item.get("notes") or "").strip()[:255],
        })
    return result


# ---------------------------------------------------------------------------
# 6. Headlight type from ScrapingBee Google AI
# ---------------------------------------------------------------------------

def headlight_type_from_google(*, year: int, make: str, model: str, engine: str = "") -> dict:
    """
    Use ScrapingBee to ask Google what headlight type is standard for this vehicle.

    Returns:
      {"option_label": str, "confidence": float, "needs_manual_check": bool}
    """
    api_key = (getattr(settings, "SCRAPING_BEE_API_KEY", "") or "").strip()
    if not api_key:
        return {"option_label": "", "confidence": 0.0, "needs_manual_check": True}

    query = f"{year} {make} {model} {engine} headlight type LED or Halogen standard".strip()
    google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    params = {
        "api_key": api_key,
        "url": google_url,
        "render_js": "false",
        "ai_query": (
            f"What type of headlight does the {year} {make} {model} come with standard? "
            "Is it LED, Halogen, HID/Xenon, or LED with Halogen accents? "
            "Give me just the type and your confidence level (high/medium/low)."
        ),
        "ai_selector": "body",
    }
    try:
        r = httpx.get("https://app.scrapingbee.com/api/v1/", params=params, timeout=30)
        r.raise_for_status()
        text = r.text
    except Exception as exc:
        logger.warning("ScrapingBee Google headlight query failed: %s", exc)
        return {"option_label": "", "confidence": 0.0, "needs_manual_check": True}

    text_lower = text.lower()
    if "led" in text_lower and "halogen" not in text_lower:
        return {"option_label": "LED", "confidence": 0.85, "needs_manual_check": False}
    if "halogen" in text_lower and "led" not in text_lower:
        return {"option_label": "Halogen", "confidence": 0.85, "needs_manual_check": False}
    if "hid" in text_lower or "xenon" in text_lower:
        return {"option_label": "HID/Xenon", "confidence": 0.80, "needs_manual_check": False}
    # Ambiguous — let Claude decide from the text
    system = (
        "Extract headlight type from search results. "
        'Return JSON only: {"option_label": string, "confidence": float 0-1}'
    )
    resp = _claude_text(system, f"Search results:\n{text[:2000]}\n\nVehicle: {year} {make} {model}", max_tokens=80)
    parsed = _extract_json(resp or "") if resp else None
    if isinstance(parsed, dict):
        conf = float(parsed.get("confidence") or 0.5)
        label = str(parsed.get("option_label") or "").strip()
        return {
            "option_label": label,
            "confidence": conf,
            "needs_manual_check": conf < 0.9,
        }
    return {"option_label": "", "confidence": 0.0, "needs_manual_check": True}
