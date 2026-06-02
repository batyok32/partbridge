from .models import VehiclePart


def apply_damage_notes_stub(vehicle, damage_notes):
    """
    Rule-based stub for 'AI' damage inference: marks likely affected parts damaged + unavailable.
    """
    text = " ".join(damage_notes or []).lower()
    if not text.strip():
        return 0
    affected = 0
    for part in vehicle.parts.select_related("part_family", "part_family__category"):
        if part.is_removed:
            continue
        slug = part.part_family.slug
        cat = part.part_family.category.slug
        mark = False
        if any(w in text for w in ("front", "head", "nose")) and (
            (cat in ("body_exterior", "electrical") and any(x in slug for x in ("headlight", "hood", "bumper", "fender", "grille")))
            or (cat == "engine" and any(x in slug for x in ("radiator", "condenser")))
        ):
            mark = True
        if any(w in text for w in ("rear", "back", "tail")) and cat == "body_exterior" and any(
            x in slug for x in ("tail", "rear", "bumper")
        ):
            mark = True
        if "side" in text and "door" in slug and cat == "body_exterior":
            mark = True
        if any(w in text for w in ("engine", "motor", "under hood")) and cat == "engine":
            mark = True
        if mark:
            part.is_damaged = True
            part.listing_state = VehiclePart.ListingState.UNAVAILABLE
            part.save(update_fields=["is_damaged", "listing_state", "updated_at"])
            affected += 1
    return affected
