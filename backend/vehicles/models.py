from django.conf import settings
from django.db import models
from django.utils import timezone


class Vehicle(models.Model):
    class Status(models.TextChoices):
        PENDING_RESEARCH = "pending_research", "Pending Research"
        RESEARCHING = "researching", "Researching"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    class Condition(models.TextChoices):
        EXCELLENT = "excellent", "Excellent"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        FOR_PARTS = "for_parts", "For Parts"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    generation = models.ForeignKey(
        "catalog.Generation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicles",
    )
    modification = models.ForeignKey(
        "catalog.Modification",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicles",
    )
    vin = models.CharField(max_length=17, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    color = models.CharField(max_length=64, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    condition = models.CharField(max_length=16, choices=Condition.choices, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_RESEARCH)
    seller_zip = models.CharField(max_length=10, blank=True)
    seller_state = models.CharField(max_length=2, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        bits = [str(p) for p in [self.year, self.generation] if p]
        return " ".join(bits) or f"Vehicle #{self.id}"


class VehiclePhoto(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="vehicle_photos/", null=True, blank=True)
    url = models.CharField(max_length=1024, blank=True)
    thumbnail_url = models.CharField(max_length=1024, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    label = models.CharField(max_length=128, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image and not self.url:
            self.url = self.image.url
            type(self).objects.filter(pk=self.pk).update(url=self.url)

    def __str__(self):
        return f"VehiclePhoto vehicle={self.vehicle_id} sort={self.sort_order}"
