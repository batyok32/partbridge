import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_cart_and_order_buyer_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="source_cart_item",
            field=models.ForeignKey(
                blank=True,
                help_text="Cart line this order was created from; cleared from cart after payment succeeds.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders_from_checkout",
                to="orders.cartitem",
            ),
        ),
    ]
