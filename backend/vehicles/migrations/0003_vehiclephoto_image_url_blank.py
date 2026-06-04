from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0002_vehicle_seller_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclephoto",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="vehicle_photos/"),
        ),
        migrations.AlterField(
            model_name="vehiclephoto",
            name="url",
            field=models.CharField(blank=True, max_length=1024),
        ),
    ]
