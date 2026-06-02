from django.conf import settings
from django.db import models


class Category(models.Model):
    class ShippingSize(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"
        XL = "xl", "XL"

    name = models.CharField(max_length=128)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    slug = models.SlugField(max_length=128, unique=True)
    shipping_size_default = models.CharField(max_length=8, choices=ShippingSize.choices, default=ShippingSize.MEDIUM)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class OptionCategory(models.Model):
    class OptionType(models.TextChoices):
        SIDE = "side", "Side"
        ENGINE = "engine", "Engine"
        TRANSMISSION = "transmission", "Transmission"
        TRIM = "trim", "Trim"
        OTHER = "other", "Other"

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="option_categories")
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=OptionType.choices, default=OptionType.OTHER)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Option categories"

    def __str__(self):
        return f"{self.category.name} — {self.name}"


def _calculate_shipping_size(weight_lbs, dim_l, dim_w, dim_h):
    w = float(weight_lbs or 0)
    l = float(dim_l or 0)
    wi = float(dim_w or 0)
    h = float(dim_h or 0)

    if w > 150 or l > 96:
        return "xl"
    if l > 48 or (l + wi + h) > 84 or w > 40:
        return "large"
    if l > 12 or wi > 12 or h > 12 or w > 10:
        return "medium"
    return "small"


class Item(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SOLD = "sold", "Sold"
        REMOVED = "removed", "Removed"
        HIDDEN_IN_ASSEMBLY = "hidden_in_assembly", "Hidden in Assembly"

    class Condition(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        FOR_PARTS = "for_parts", "For Parts"

    class ShippingSize(models.TextChoices):
        SMALL = "small", "Small"
        MEDIUM = "medium", "Medium"
        LARGE = "large", "Large"
        XL = "xl", "XL"

    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    condition = models.CharField(max_length=16, choices=Condition.choices)
    weight_lbs = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dim_l_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dim_w_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dim_h_in = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    shipping_size = models.CharField(max_length=8, choices=ShippingSize.choices, default=ShippingSize.MEDIUM)
    oem_part_number = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Item #{self.id}: {self.title}"

    def compute_shipping_size(self):
        return _calculate_shipping_size(self.weight_lbs, self.dim_l_in, self.dim_w_in, self.dim_h_in)

    def save(self, *args, **kwargs):
        self.shipping_size = self.compute_shipping_size()
        super().save(*args, **kwargs)


class ItemOptionConfig(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="option_configs")
    option_category = models.ForeignKey(OptionCategory, on_delete=models.CASCADE, related_name="item_configs")
    is_buyer_question = models.BooleanField(default=False)
    surviving_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("item", "option_category")]

    def __str__(self):
        return f"ItemOptionConfig item={self.item_id} cat={self.option_category_id}"


class Option(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="options")
    option_category = models.ForeignKey(OptionCategory, on_delete=models.CASCADE, related_name="options")
    value = models.CharField(max_length=255)
    is_ai_eliminated = models.BooleanField(default=False)
    elimination_reason = models.TextField(blank=True)

    def __str__(self):
        return f"Option item={self.item_id} cat={self.option_category_id} val={self.value}"


class Variation(models.Model):
    class AIConfidence(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.CASCADE, related_name="variations")
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name="variations")
    item_snapshot = models.JSONField(default=dict, blank=True)
    ai_confidence = models.CharField(max_length=8, choices=AIConfidence.choices, default=AIConfidence.LOW)
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Variation #{self.id} vehicle={self.vehicle_id} status={self.review_status}"


class ItemCompatibility(models.Model):
    class CompatLevel(models.TextChoices):
        GENERATION = "generation", "Generation"
        MODIFICATION = "modification", "Modification"

    class Source(models.TextChoices):
        AI = "ai", "AI"
        MANUAL = "manual", "Manual"
        OEM_DATA = "oem_data", "OEM Data"

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="compatibilities")
    generation = models.ForeignKey("catalog.Generation", on_delete=models.CASCADE, related_name="item_compatibilities")
    modification = models.ForeignKey(
        "catalog.Modification", null=True, blank=True, on_delete=models.SET_NULL, related_name="item_compatibilities"
    )
    compat_level = models.CharField(max_length=16, choices=CompatLevel.choices, default=CompatLevel.GENERATION)
    year_from = models.PositiveIntegerField(null=True, blank=True)
    year_to = models.PositiveIntegerField(null=True, blank=True)
    confidence_score = models.FloatField(default=0.0)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.AI)
    is_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ItemCompatibility item={self.item_id} gen={self.generation_id}"

    def save(self, *args, **kwargs):
        if self.confidence_score >= 0.85:
            self.is_verified = True
        super().save(*args, **kwargs)


class ItemPhoto(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="photos")
    url = models.CharField(max_length=1024)
    thumbnail_url = models.CharField(max_length=1024, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    label = models.CharField(max_length=128, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"ItemPhoto item={self.item_id} sort={self.sort_order}"
