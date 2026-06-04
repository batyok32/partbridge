from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="stripe_connect_account_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_connect_details_submitted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_connect_payouts_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_connect_onboarded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
