from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0007_vehicle_part_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="condition_description",
            field=models.TextField(
                blank=True,
                help_text="Free-form condition notes for the vehicle (e.g. 'runs, but misfires').",
            ),
        ),
        migrations.AddField(
            model_name="vehiclepart",
            name="condition_description",
            field=models.TextField(
                blank=True,
                help_text="Free-form condition notes for this part (beyond the dropdown condition).",
            ),
        ),
    ]

