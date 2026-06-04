from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_tax"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartbundle",
            name="shipping_mode",
            field=models.CharField(
                choices=[("standard", "Standard"), ("economy", "Economy")],
                default="standard",
                max_length=16,
            ),
        ),
    ]
