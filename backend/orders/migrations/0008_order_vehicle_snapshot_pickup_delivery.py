from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_order_source_cart_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="vehicle_snapshot",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="VIN / YMM at order time for receipts (denormalized).",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_completion_photos",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Photo URLs when pickup is completed (admin/seller).",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_photos",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Proof-of-delivery photo URLs emailed to buyer.",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_notes",
            field=models.TextField(
                blank=True,
                help_text="Notes included with delivery notification to buyer.",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="funds_held_until_delivered",
            field=models.BooleanField(
                default=True,
                help_text="When True, seller payout is conceptually held until delivered (escrow).",
            ),
        ),
    ]
