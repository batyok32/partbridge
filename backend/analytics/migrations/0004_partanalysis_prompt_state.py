from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0003_analysiscarphoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="partanalysis",
            name="prompt_applied",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="partanalysis",
            name="prompt_text",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="partanalysis",
            name="filtered_categories",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="partanalysis",
            name="filtered_part_out_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

