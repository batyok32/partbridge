from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0005_phase4_listing_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="has_damage",
            field=models.BooleanField(
                default=False,
                help_text="Whether the seller has reported known damage on this vehicle.",
            ),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="damage_items",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of damage type strings (pre-set options or custom descriptions).",
            ),
        ),
    ]
