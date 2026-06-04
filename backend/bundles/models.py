from django.db import models


class BundleCategory(models.Model):
    class BundleType(models.TextChoices):
        ASSEMBLY = "assembly", "Assembly"
        DISCOUNT = "discount", "Discount"

    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=BundleType.choices, default=BundleType.DISCOUNT)
    image = models.ImageField(upload_to="bundle_categories/", null=True, blank=True)

    class Meta:
        verbose_name_plural = "Bundle categories"

    def __str__(self):
        return f"{self.name} ({self.type})"


class Bundle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISBANDED = "disbanded", "Disbanded"

    bundle_category = models.ForeignKey(BundleCategory, on_delete=models.CASCADE, related_name="bundles")
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        "parts.Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assembly_bundles",
        help_text="Category for the synthetic assembly item. Required for assembly bundles.",
    )
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fixed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="bundle_items")
    item = models.ForeignKey("parts.Item", on_delete=models.CASCADE, related_name="bundle_items")

    class Meta:
        unique_together = [("bundle", "item")]

    def __str__(self):
        return f"BundleItem bundle={self.bundle_id} item={self.item_id}"
