# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_pickup_slot_sellerreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[("stripe", "Stripe"), ("cash", "Cash (test)")],
                default="stripe",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="document_id_front",
            field=models.ImageField(blank=True, upload_to="seller_verify/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="document_id_back",
            field=models.ImageField(blank=True, upload_to="seller_verify/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="document_selfie",
            field=models.ImageField(blank=True, upload_to="seller_verify/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="documents_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="documents_review_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="sellerverification",
            name="documents_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
