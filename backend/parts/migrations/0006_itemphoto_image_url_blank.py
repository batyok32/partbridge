from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parts", "0005_optionvalue_cleanup_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemphoto",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="item_photos/"),
        ),
        migrations.AlterField(
            model_name="itemphoto",
            name="url",
            field=models.CharField(blank=True, max_length=1024),
        ),
    ]
