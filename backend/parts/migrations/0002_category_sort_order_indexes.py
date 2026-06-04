from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="sort_order",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="category",
            options={"ordering": ["sort_order", "name"], "verbose_name_plural": "Categories"},
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(fields=["status", "category", "price"], name="parts_item_status_cat_price_idx"),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(fields=["status", "-created_at"], name="parts_item_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="itemcompatibility",
            index=models.Index(fields=["generation", "is_verified"], name="parts_ic_gen_verified_idx"),
        ),
        migrations.AddIndex(
            model_name="itemcompatibility",
            index=models.Index(fields=["item", "generation"], name="parts_ic_item_gen_idx"),
        ),
    ]
