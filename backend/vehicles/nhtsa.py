"""
NHTSA vPIC — decode VIN (free public API).
https://vpic.nhtsa.dot.gov/api/
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any

import certifi

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{vin}?format=json"

# NHTSA returns placeholders that are not real values.
_SKIP_VALUES = frozenset(
    {
        "",
        "not applicable",
        "n/a",
        "null",
    }
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if s.lower() in _SKIP_VALUES:
        return ""
    return s


def _first_non_empty(row: dict, *keys: str) -> str:
    for k in keys:
        v = _clean(row.get(k))
        if v:
            return v
    return ""


def map_vpic_row_to_vehicle_fields(row: dict) -> dict[str, Any]:
    """Map vPIC decodevinvalues row to Vehicle model fields."""
    year_s = _first_non_empty(row, "ModelYear")
    year = None
    if year_s and year_s.isdigit():
        y = int(year_s)
        if 1900 <= y <= 2100:
            year = y

    disp = _clean(row.get("DisplacementL"))
    cyl = _clean(row.get("EngineCylinders"))
    eng_model = _clean(row.get("EngineModel"))
    fuel = _clean(row.get("FuelTypePrimary"))
    hp = _clean(row.get("EngineHP"))
    engine_bits = []
    if disp:
        engine_bits.append(f"{disp}L")
    if cyl:
        engine_bits.append(f"{cyl} cyl")
    if eng_model:
        engine_bits.append(eng_model)
    if fuel:
        engine_bits.append(fuel)
    if hp:
        engine_bits.append(f"{hp} hp")
    engine = " ".join(engine_bits)[:255]

    transmission = _first_non_empty(row, "TransmissionStyle", "TransmissionSpeeds")
    drivetrain = _first_non_empty(row, "DriveType")
    body_style = _first_non_empty(row, "BodyClass", "VehicleType")
    color = _first_non_empty(row, "ExteriorColor")

    return {
        "year": year,
        "make": _first_non_empty(row, "Make")[:64],
        "model": _first_non_empty(row, "Model")[:64],
        "trim": _first_non_empty(row, "Trim", "Trim2", "Series", "Series2")[:128],
        "engine": engine,
        "transmission": transmission[:128],
        "drivetrain": drivetrain[:64],
        "body_style": body_style[:64],
        "color": color[:64],
    }


def decode_vin(vin: str) -> dict[str, Any]:
    """
    Call NHTSA decodevinvalues. Always returns suggested fields when any data exists.
    Includes nhtsa_error_code / nhtsa_error_text when vPIC reports a non-zero code (often still usable).
    """
    vin = re.sub(r"\s+", "", (vin or "")).upper()
    if len(vin) != 17:
        raise ValueError("VIN must be exactly 17 characters.")
    if not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
        raise ValueError("VIN contains invalid characters (I, O, Q are not used).")

    url = VPIC_DECODE_URL.format(vin=vin)
    # Use certifi's CA bundle — avoids SSL verify failures on macOS / some Python builds
    # where the default store cannot validate api.nhtsa.dot.gov.
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl_ctx) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise ValueError(f"NHTSA request failed: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Could not reach NHTSA: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ValueError("Invalid response from NHTSA.") from e

    results = payload.get("Results") or []
    if not results:
        raise ValueError("No decode results from NHTSA.")
    row = results[0]

    err_code = _clean(row.get("ErrorCode"))
    err_text = _clean(row.get("ErrorText"))

    suggested = map_vpic_row_to_vehicle_fields(row)

    return {
        "vin": vin,
        "suggested": suggested,
        "nhtsa_error_code": err_code or None,
        "nhtsa_error_text": err_text or None,
        "nhtsa_warning": bool(err_code and err_code != "0"),
        "raw": row,
    }
