"""AI helpers for buyer car/part discovery (Phase 6 extension)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from django.conf import settings


def _extract_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _int_or_none(v: Any) -> int | None:
    try:
        if v is None or v == "":
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def normalize_candidate_vehicle(raw: Any) -> dict[str, Any] | None:
    """
    Normalize AI vehicle rows to include year_range_start / year_range_end (inclusive model years).

    Accepts legacy shapes with only `year` (single model year → range of one year).
    """
    if not isinstance(raw, dict):
        return None
    make = str(raw.get("make") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not make or not model:
        return None
    trim = str(raw.get("trim") or "").strip()
    reason = str(raw.get("reason") or "").strip()[:90]

    ys = _int_or_none(raw.get("year_range_start"))
    ye = _int_or_none(raw.get("year_range_end"))
    y_one = _int_or_none(raw.get("year"))

    if ys is not None and ye is not None:
        if ys > ye:
            ys, ye = ye, ys
    elif y_one is not None:
        ys = ye = y_one
    else:
        ys = ye = None

    out: dict[str, Any] = {
        "year_range_start": ys,
        "year_range_end": ye,
        "make": make,
        "model": model,
        "trim": trim,
        "reason": reason,
    }
    return out


def normalize_candidate_vehicles(vehicles: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in vehicles:
        n = normalize_candidate_vehicle(v)
        if n:
            out.append(n)
    return out[:8]


def _fallback_vehicle_suggestions(
    *,
    buyer_year: int | None,
    buyer_make: str,
    buyer_model: str,
    part_query: str,
) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    bm = (buyer_make or "").strip()
    bmd = (buyer_model or "").strip()
    if buyer_year is not None and bm and bmd:
        by = int(buyer_year)
        y0 = max(1980, by - 2)
        y1 = by + 2
        suggestions.append(
            {
                "year_range_start": y0,
                "year_range_end": y1,
                "make": bm,
                "model": bmd,
                "trim": "",
                "reason": f"Heuristic window around your model year for {part_query}"[:90],
            }
        )
    elif bm and bmd:
        suggestions.append(
            {
                "year_range_start": None,
                "year_range_end": None,
                "make": bm,
                "model": bmd,
                "trim": "",
                "reason": f"Same make/model; match inventory rows to a year for {part_query}"[:90],
            }
        )
    norm = normalize_candidate_vehicles(suggestions)
    return {
        "normalized_part_query": part_query.strip(),
        "suggested_category_name": "",
        "candidate_vehicles": norm,
        "source": "fallback",
    }


def deepseek_refine_part_phrase(
    *,
    raw_text: str,
    buyer_year: int | None,
    buyer_make: str,
    buyer_model: str,
) -> dict[str, Any]:
    """
    Rewrite a buyer's free-text part request into a clear inventory search phrase.
    Uses DeepSeek when DEEPSEEK_API_KEY is configured; otherwise returns trimmed input.
    """
    text = (raw_text or "").strip()
    if not text:
        return {"refined_query": "", "note": "", "source": "none"}

    api_key = (settings.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        return {
            "refined_query": text,
            "note": "Add DEEPSEEK_API_KEY for AI rewriting.",
            "source": "fallback",
        }

    system = (
        "You help buyers search used auto parts. "
        "Rewrite the user's request into ONE short, specific phrase a parts catalog would use "
        "(e.g. 'left headlight assembly', 'alternator', 'rear brake caliper driver side'). "
        "No sentences — phrase only. "
        "Return JSON only: {\"refined_query\": string, \"note\": string (one short tip for the buyer, may be empty)}"
    )
    user = (
        f"Vehicle: year={buyer_year or 'unknown'}, make={buyer_make}, model={buyer_model}. "
        f"Buyer wrote: {text}"
    )
    try:
        with httpx.Client(timeout=22) as client:
            r = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat"),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.2,
                },
            )
            r.raise_for_status()
            body = r.json()
    except Exception:
        return {"refined_query": text, "note": "", "source": "fallback"}

    content = (
        ((body or {}).get("choices") or [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    parsed = _extract_json_block(content) or {}
    refined = str(parsed.get("refined_query") or text).strip()
    note = str(parsed.get("note") or "").strip()
    if not refined:
        refined = text
    return {"refined_query": refined[:200], "note": note[:300], "source": "deepseek"}


def suggest_cars_and_part_phrase(
    *,
    buyer_year: int | None,
    buyer_make: str,
    buyer_model: str,
    part_query: str,
) -> dict[str, Any]:
    api_key = (settings.PERPLEXITY_API_KEY or "").strip()
    if not api_key:
        return _fallback_vehicle_suggestions(
            buyer_year=buyer_year,
            buyer_make=buyer_make,
            buyer_model=buyer_model,
            part_query=part_query,
        )

    prompt = (
        "You are an automotive fitment assistant. "
        "Given the buyer vehicle and one requested part, return compact JSON only.\n"
        "Schema:\n"
        "{"
        '"normalized_part_query": string, '
        '"suggested_category_name": string, '
        '"candidate_vehicles": ['
        '{"year_range_start": number|null, "year_range_end": number|null, '
        '"make": string, "model": string, "trim": string, "reason": string}'
        "]"
        "}\n"
        "Each candidate_vehicles entry is ONE generation or platform: set year_range_start and year_range_end to "
        "the inclusive US model years where that part commonly cross-fits (e.g. 2014-2019). "
        "If only one year applies, use the same value for both. "
        "Do not list one row per year — use a range. "
        "candidate_vehicles max 8; reason max 90 chars."
    )
    user_text = (
        f"Buyer car: year={buyer_year or 'unknown'}, make={buyer_make}, model={buyer_model}. "
        f"Requested part: {part_query}."
    )
    try:
        with httpx.Client(timeout=18) as client:
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
                        {"role": "user", "content": user_text},
                    ],
                    "temperature": 0.1,
                },
            )
            r.raise_for_status()
            body = r.json()
    except Exception:
        return _fallback_vehicle_suggestions(
            buyer_year=buyer_year,
            buyer_make=buyer_make,
            buyer_model=buyer_model,
            part_query=part_query,
        )

    content = (
        ((body or {}).get("choices") or [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    parsed = _extract_json_block(content) or {}
    vehicles = parsed.get("candidate_vehicles") if isinstance(parsed.get("candidate_vehicles"), list) else []
    norm = normalize_candidate_vehicles(vehicles)
    return {
        "normalized_part_query": str(parsed.get("normalized_part_query") or part_query).strip(),
        "suggested_category_name": str(parsed.get("suggested_category_name") or "").strip(),
        "candidate_vehicles": norm,
        "source": "perplexity",
    }
