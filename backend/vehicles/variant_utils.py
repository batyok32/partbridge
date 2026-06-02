import json


def variant_key_from_dict(data):
    return json.dumps(data or {}, sort_keys=True, separators=(",", ":"))


def label_for_part(family_name, variant):
    if not variant:
        return family_name
    bits = [f"{k}: {v}" for k, v in sorted(variant.items())]
    return f"{family_name} — {', '.join(bits)}"
