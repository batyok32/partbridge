from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_cartbundle_shipping_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="payout_transferred",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="transfer_eligible_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
