from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parts", "0006_itemphoto_image_url_blank"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="categories/"),
        ),
    ]
