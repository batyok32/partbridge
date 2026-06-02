from django.db import transaction

from .models import PartFamily, VehiclePart
from .variant_utils import label_for_part, variant_key_from_dict


def seed_parts_for_vehicle(vehicle):
    """Create VehiclePart rows from PartFamily catalog (skips buy_new_only)."""
    created = 0
    families = PartFamily.objects.filter(buy_new_only=False).select_related("category")
    rows = []
    for family in families:
        templates = family.variant_templates
        if not templates:
            templates = [{}]
        for tmpl in templates:
            if not isinstance(tmpl, dict):
                tmpl = {}
            vk = variant_key_from_dict(tmpl)
            label = label_for_part(family.name, tmpl)
            rows.append(
                VehiclePart(
                    vehicle=vehicle,
                    part_family=family,
                    variant_key=vk,
                    label=label,
                )
            )
    with transaction.atomic():
        for row in rows:
            _, was_created = VehiclePart.objects.get_or_create(
                vehicle=row.vehicle,
                part_family=row.part_family,
                variant_key=row.variant_key,
                defaults={"label": row.label},
            )
            if was_created:
                created += 1
    return created
