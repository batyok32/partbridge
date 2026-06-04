from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bundles", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="bundlecategory",
            name="category_filters",
        ),
        migrations.AddField(
            model_name="bundle",
            name="fixed_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
