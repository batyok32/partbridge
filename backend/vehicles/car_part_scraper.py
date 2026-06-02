"""
Scrape car-part.com for part options using ScrapingBee.

Flow:
1. GET the search form page for the given year/make/model/part/zip
2. POST the search form
3. Parse radio-button options from the result
4. Return status + list of option labels

Returns a dict:
  {
    "status": "found" | "no_options" | "year_range" | "undefined" | "failed",
    "options": [{"key": str, "label": str, "value": str}],
    "raw_html_snippet": str,
  }
"""
from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE = "https://www.car-part.com"
_SEARCH_CGI = f"{_BASE}/cgi-bin/search.cgi"


def _bee_get(url: str, render_js: bool = False) -> str | None:
    api_key = (getattr(settings, "SCRAPING_BEE_API_KEY", "") or "").strip()
    if not api_key:
        return None
    params: dict = {
        "api_key": api_key,
        "url": url,
        "render_js": "true" if render_js else "false",
        "block_ads": "true",
    }
    try:
        r = httpx.get("https://app.scrapingbee.com/api/v1/", params=params, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logger.warning("ScrapingBee GET failed url=%s: %s", url, exc)
        return None


def _bee_post(url: str, payload: dict) -> str | None:
    api_key = (getattr(settings, "SCRAPING_BEE_API_KEY", "") or "").strip()
    if not api_key:
        return None
    params = {
        "api_key": api_key,
        "url": url,
        "render_js": "false",
        "block_ads": "true",
    }
    try:
        r = httpx.post(
            "https://app.scrapingbee.com/api/v1/",
            params=params,
            data=payload,
            timeout=40,
        )
        r.raise_for_status()
        return r.text
    except Exception as exc:
        logger.warning("ScrapingBee POST failed url=%s: %s", url, exc)
        return None


def _parse_model_options(html: str) -> list[str]:
    """Extract option values from select#model."""
    opts = re.findall(r'<option\s+value="([^"]+)"', html, re.IGNORECASE)
    return [o for o in opts if o and o.lower() not in ("", "select", "none")]


def _make_model_value(make: str, model: str) -> str:
    """
    car-part.com uses "MAKE MODEL" as the option value inside select#model.
    We try an exact match; callers should fall back to prefix search if needed.
    """
    return f"{make.upper()} {model.upper()}"


def _parse_radio_options(html: str) -> list[dict]:
    """
    Parse <input type="radio" name="dummyVar" ...> <label>...</label> pairs.
    Returns [{"key": "0", "label": "1.3L (MX, hybrid)", "value": "BEFEE..."}]
    """
    pattern = re.compile(
        r'<input\s[^>]*type=["\']radio["\'][^>]*id="(\d+)"[^>]*value="([^"]+)"[^>]*>.*?'
        r'<label\s+for="\1">\s*(.*?)\s*</label>',
        re.IGNORECASE | re.DOTALL,
    )
    results = []
    for m in pattern.finditer(html):
        idx, value, label_raw = m.group(1), m.group(2), m.group(3)
        label = re.sub(r"<[^>]+>", "", label_raw).strip()
        if label and value and value.lower() != "none":
            results.append({"key": idx, "label": label, "value": value})
    return results


def _detect_year_range(html: str) -> bool:
    """Check if car-part.com showed a 'Non-Interchange search' year-range selector."""
    return bool(re.search(r"Non-Interchange search using", html, re.IGNORECASE))


def scrape_part_options(
    *,
    year: int,
    make: str,
    model: str,
    part_name: str,
    zip_code: str = "90210",
) -> dict:
    """
    Scrape car-part.com for options for the given vehicle + part.

    Returns:
      {
        "status": "found"|"no_options"|"year_range"|"undefined"|"failed",
        "options": [{"key", "label", "value"}],
        "raw_html_snippet": str,
      }
    """
    result = {"status": "failed", "options": [], "raw_html_snippet": ""}

    # Step 1 — load the form page to see available models
    home_html = _bee_get(_BASE)
    if not home_html:
        logger.warning("car-part.com: could not load home page (no ScrapingBee key?)")
        result["status"] = "failed"
        return result

    # Build the POST payload matching the form fields described in the instructions
    model_value = _make_model_value(make, model)
    payload = {
        "userDate": str(year),
        "userModel": model_value,
        "userPart": part_name,
        "userCountry": "US",
        "userZip": zip_code,
        "action": "Search Car Part Inventory",
    }

    # Step 2 — POST to search
    html = _bee_post(_SEARCH_CGI, payload)
    if not html:
        result["status"] = "failed"
        return result

    result["raw_html_snippet"] = html[:4000]

    # Step 3 — Detect what happened
    if _detect_year_range(html):
        result["status"] = "year_range"
        return result

    radio_opts = _parse_radio_options(html)
    if not radio_opts:
        # Check if we went straight to results (no options page)
        if "searchresults" in html.lower() or "listing" in html.lower() or "Add to Cart" in html:
            result["status"] = "no_options"
            result["options"] = [{"key": "all", "label": "All", "value": "all"}]
        else:
            # car-part.com doesn't know this part
            result["status"] = "undefined"
        return result

    result["status"] = "found"
    result["options"] = radio_opts
    return result
