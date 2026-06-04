from django.db import models


class Make(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    country = models.CharField(max_length=64, blank=True)
    logo_url = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CarModel(models.Model):
    make = models.ForeignKey(Make, on_delete=models.CASCADE, related_name="car_models")
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("make", "slug")]

    def __str__(self):
        return f"{self.make.name} {self.name}"


class Generation(models.Model):
    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE, related_name="generations")
    make = models.ForeignKey(Make, on_delete=models.CASCADE, related_name="generations")
    chassis_codes = models.JSONField(default=list, blank=True, null=True)
    name = models.CharField(max_length=128, blank=True)
    body_style = models.CharField(max_length=64, blank=True)
    production_start = models.DateField()
    production_end = models.DateField(null=True, blank=True)
    region = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["production_start"]

    def __str__(self):
        name_part = f" {self.name}" if self.name else ""
        return f"{self.car_model}{name_part} ({self.production_start.year}–{self.production_end.year if self.production_end else ''})"


class Modification(models.Model):
    class FuelType(models.TextChoices):
        GASOLINE = "gasoline", "Gasoline"
        DIESEL = "diesel", "Diesel"
        HYBRID = "hybrid", "Hybrid"
        ELECTRIC = "electric", "Electric"
        OTHER = "other", "Other"

    class TransmissionType(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automatic"
        CVT = "cvt", "CVT"
        DCT = "dct", "DCT"
        OTHER = "other", "Other"

    class DriveType(models.TextChoices):
        FWD = "fwd", "FWD"
        RWD = "rwd", "RWD"
        AWD = "awd", "AWD"
        FOUR_WD = "4wd", "4WD"

    generation = models.ForeignKey(Generation, on_delete=models.CASCADE, related_name="modifications")
    code = models.CharField(max_length=64)
    variant_name = models.CharField(max_length=128, blank=True)
    engine_code = models.CharField(max_length=64, blank=True)
    engine_displacement_cc = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=16, choices=FuelType.choices, blank=True)
    transmission_type = models.CharField(max_length=16, choices=TransmissionType.choices, blank=True)
    transmission_detail = models.CharField(max_length=128, blank=True)
    cab_type = models.CharField(max_length=64, blank=True)
    drive_type = models.CharField(max_length=8, choices=DriveType.choices, blank=True)
    power_hp = models.PositiveIntegerField(null=True, blank=True)
    production_start = models.DateField()
    production_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.generation} — {self.code}"
