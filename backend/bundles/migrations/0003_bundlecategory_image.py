from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bundles", "0002_remove_bundlecategory_category_filters_bundle_fixed_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="bundlecategory",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="bundle_categories/"),
        ),
    ]
