# Generated manually

import datetime
from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def backfill_pickup_slots(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    from django.utils import timezone as dj_tz  # noqa: PLC0415

    for o in Order.objects.exclude(pickup_scheduled_at=None).iterator():
        loc = dj_tz.localtime(o.pickup_scheduled_at)
        start = loc.time().replace(second=0, microsecond=0)
        end_dt = loc + timedelta(hours=4)
        end = end_dt.time().replace(second=0, microsecond=0)
        if end <= start:
            end = datetime.time(17, 0, 0, 0)
        o.pickup_slot_start = start
        o.pickup_slot_end = end
        o.save(update_fields=["pickup_slot_start", "pickup_slot_end"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0008_order_vehicle_snapshot_pickup_delivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="pickup_slot_start",
            field=models.TimeField(blank=True, null=True, help_text="Local pickup window start (same day as pickup_window_start)."),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_slot_end",
            field=models.TimeField(blank=True, null=True, help_text="Local pickup window end."),
        ),
        migrations.CreateModel(
            name="SellerReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveSmallIntegerField()),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seller_reviews_written",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seller_review",
                        to="orders.order",
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seller_reviews_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(backfill_pickup_slots, migrations.RunPython.noop),
    ]
