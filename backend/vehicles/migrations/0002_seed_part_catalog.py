from django.db import migrations


def seed_catalog(apps, schema_editor):
    PartCategory = apps.get_model("vehicles", "PartCategory")
    PartFamily = apps.get_model("vehicles", "PartFamily")

    categories = [
        ("engine", "Engine", 10, "engine"),
        ("drivetrain", "Drivetrain", 20, "drivetrain"),
        ("suspension", "Suspension", 30, "suspension"),
        ("brakes", "Brakes", 40, "brakes"),
        ("body_exterior", "Body exterior", 50, "body_exterior"),
        ("body_interior", "Body interior", 60, "body_interior"),
        ("electrical", "Electrical", 70, "electrical"),
        ("hvac", "HVAC", 80, "hvac"),
        ("fuel_system", "Fuel system", 90, "fuel_system"),
        ("exhaust", "Exhaust", 100, "exhaust"),
    ]
    cat_map = {}
    for slug, name, order, ill in categories:
        c, _ = PartCategory.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "sort_order": order, "illustration_key": ill},
        )
        cat_map[slug] = c

    # (category_slug, family_slug, name, buy_new_only, variant_templates)
    families = [
        ("engine", "alternator", "Alternator", False, []),
        ("engine", "starter", "Starter", False, []),
        ("engine", "radiator", "Radiator", False, []),
        ("engine", "serpentine_belt", "Serpentine belt", True, []),
        ("engine", "battery", "Battery", False, []),
        ("drivetrain", "cv_axle", "CV axle", False, [{"side": "left"}, {"side": "right"}]),
        ("suspension", "strut", "Strut", False, [{"side": "left"}, {"side": "right"}]),
        ("brakes", "brake_pads_front", "Brake pads (front)", True, []),
        ("brakes", "brake_caliper", "Brake caliper", False, [{"side": "left"}, {"side": "right"}]),
        ("body_exterior", "headlight", "Headlight", False, [{"side": "left"}, {"side": "right"}]),
        ("body_exterior", "tail_light", "Tail light", False, [{"side": "left"}, {"side": "right"}]),
        ("body_exterior", "front_bumper", "Front bumper", False, []),
        ("body_exterior", "rear_bumper", "Rear bumper", False, []),
        ("body_exterior", "hood", "Hood", False, []),
        ("body_exterior", "door", "Door", False, [{"side": "left"}, {"side": "right"}]),
        ("body_interior", "seat", "Seat", False, [{"side": "left"}, {"side": "right"}]),
        ("electrical", "mirror", "Mirror", False, [{"side": "left"}, {"side": "right"}]),
        ("hvac", "blower_motor", "Blower motor", False, []),
        ("fuel_system", "fuel_pump", "Fuel pump", False, []),
        ("exhaust", "catalytic_converter", "Catalytic converter", False, []),
    ]

    for cat_slug, slug, name, buy_new, variants in families:
        PartFamily.objects.update_or_create(
            category=cat_map[cat_slug],
            slug=slug,
            defaults={
                "name": name,
                "buy_new_only": buy_new,
                "variant_templates": variants,
            },
        )


def unseed_catalog(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalog, unseed_catalog),
    ]
