from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0008_condition_descriptions"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="pickup_allowed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="pickup_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="return_policy_default",
            field=models.CharField(
                choices=[
                    ("red", "Final sale — as-is (no returns)"),
                    ("yellow", "Partial returns — restocking fee may apply"),
                    ("green", "30-day buyer protection (full refund)"),
                ],
                default="green",
                max_length=16,
                help_text="Default return policy suggested for new/updated parts.",
            ),
        ),
    ]

