"""Convert imperial package inputs to stored metric (cm / kg)."""

from __future__ import annotations

from decimal import Decimal

CM_PER_IN = Decimal("2.54")
KG_PER_LB = Decimal("0.45359237")
LB_PER_KG = Decimal("2.2046226218487757")


def inches_to_cm(inches: Decimal) -> Decimal:
    return (inches * CM_PER_IN).quantize(Decimal("0.01"))


def pounds_to_kg(lb: Decimal) -> Decimal:
    return (lb * KG_PER_LB).quantize(Decimal("0.01"))


def cm_to_inches(cm: Decimal | None) -> Decimal | None:
    if cm is None:
        return None
    return (cm / CM_PER_IN).quantize(Decimal("0.01"))


def kg_to_pounds(kg: Decimal | None) -> Decimal | None:
    if kg is None:
        return None
    return (kg * LB_PER_KG).quantize(Decimal("0.01"))
