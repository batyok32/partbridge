from django.conf import settings
from django.db import models
from django.utils import timezone


class ReturnPolicy(models.TextChoices):
    RED = "red", "Final sale — as-is (no returns)"
    YELLOW = "yellow", "Partial returns — restocking fee may apply"
    GREEN = "green", "30-day buyer protection (full refund)"


class PartCategory(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    sort_order = models.PositiveSmallIntegerField(default=0)
    illustration_key = models.SlugField(
        max_length=64,
        help_text="Stable key for SVG/illustration lookup (e.g. engine, brakes).",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Part categories"

    def __str__(self):
        return self.name


class PartFamily(models.Model):
    category = models.ForeignKey(
        PartCategory,
        on_delete=models.CASCADE,
        related_name="part_families",
    )
    slug = models.SlugField(max_length=96)
    name = models.CharField(max_length=255)
    buy_new_only = models.BooleanField(
        default=False,
        help_text="If true, never offered to sellers (belts, pads, etc.).",
    )
    variant_templates = models.JSONField(
        default=list,
        blank=True,
        help_text='List of dicts, e.g. [{"side": "left"}, {"side": "right"}] or [] for one row.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_part_families",
    )

    class Meta:
        ordering = ["category__sort_order", "name"]
        verbose_name_plural = "Part families"
        unique_together = [("category", "slug")]

    def __str__(self):
        return f"{self.category.name} · {self.name}"


class Vehicle(models.Model):
    class AnalyticsStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    vin = models.CharField(max_length=17)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    make = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=64, blank=True)
    trim = models.CharField(max_length=128, blank=True)
    engine = models.CharField(max_length=255, blank=True)
    transmission = models.CharField(max_length=128, blank=True)
    drivetrain = models.CharField(max_length=64, blank=True)
    body_style = models.CharField(max_length=64, blank=True)
    color = models.CharField(max_length=64, blank=True)
    interior_color = models.CharField(max_length=64, blank=True)
    exterior_color_code = models.CharField(max_length=32, blank=True)
    interior_color_code = models.CharField(max_length=32, blank=True)
    paint_code = models.CharField(max_length=32, blank=True)
    location_state = models.CharField(max_length=2, blank=True)
    location_zip = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    condition_description = models.TextField(blank=True)
    pickup_allowed = models.BooleanField(default=False)
    pickup_address = models.TextField(blank=True)
    return_policy_default = models.CharField(
        max_length=16,
        choices=ReturnPolicy.choices,
        default=ReturnPolicy.GREEN,
    )
    has_damage = models.BooleanField(default=False)
    damage_items = models.JSONField(default=list, blank=True)
    # AI-generated full description from uploaded images
    ai_image_description = models.TextField(
        blank=True,
        help_text="Detailed AI-generated description of all visible parts and their condition.",
    )
    analytics_status = models.CharField(
        max_length=32,
        choices=AnalyticsStatus.choices,
        default=AnalyticsStatus.PENDING,
    )
    analytics_last_completed_at = models.DateTimeField(null=True, blank=True)
    analytics_next_refresh_at = models.DateTimeField(null=True, blank=True)
    odometer_miles = models.PositiveIntegerField(null=True, blank=True)
    mileage_unavailable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        bits = [self.year, self.make, self.model]
        return " ".join(str(b) for b in bits if b) or self.vin

    def can_refresh_market_analytics(self) -> bool:
        if self.analytics_status == self.AnalyticsStatus.PROCESSING:
            return False
        if self.analytics_next_refresh_at is None:
            return True
        return timezone.now() >= self.analytics_next_refresh_at


class VehiclePhoto(models.Model):
    """Categorized donor-car photo. section drives primary photo selection for parts."""

    class Section(models.TextChoices):
        # Exterior
        FRONT_DRIVER_CORNER = "front_driver_corner", "Front-Driver's Corner (3/4 view)"
        REAR_PASSENGER_CORNER = "rear_passenger_corner", "Rear-Passenger's Corner (3/4 view)"
        DRIVER_SIDE_PROFILE = "driver_side_profile", "Driver's Side Profile"
        PASSENGER_SIDE_PROFILE = "passenger_side_profile", "Passenger's Side Profile"
        DIRECT_FRONT = "direct_front", "Direct Front"
        DIRECT_REAR = "direct_rear", "Direct Rear"
        WHEELS = "wheels", "All Four Wheels/Tires"
        DAMAGED_AREAS = "damaged_areas", "Damaged Areas"
        # Interior
        FRONT_COCKPIT = "front_cockpit", "Front Cockpit (Dashboard)"
        DRIVER_SEAT = "driver_seat", "Driver's Seat"
        PASSENGER_SEAT = "passenger_seat", "Passenger Seat"
        REAR_SEATS = "rear_seats", "Rear Seats"
        DASHBOARD = "dashboard", "Dashboard and Steering Wheel"
        ODOMETER = "odometer", "Odometer"
        CENTER_CONSOLE = "center_console", "Center Console/Infotainment"
        TRUNK = "trunk", "Trunk/Cargo Area"
        ENGINE_BAY = "engine_bay", "Engine Bay"
        OTHER = "other", "Other"

    # Legacy — kept for backward compat; new uploads use section only
    kind = models.CharField(max_length=32, blank=True, default="")
    section = models.CharField(
        max_length=32,
        choices=Section.choices,
        default=Section.OTHER,
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="vehicle_photos/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


# Maps part label keywords → preferred primary photo section
PART_PRIMARY_SECTION_MAP = {
    "headlight": VehiclePhoto.Section.FRONT_DRIVER_CORNER,
    "headlamp": VehiclePhoto.Section.FRONT_DRIVER_CORNER,
    "front bumper": VehiclePhoto.Section.DIRECT_FRONT,
    "grille": VehiclePhoto.Section.DIRECT_FRONT,
    "hood": VehiclePhoto.Section.DIRECT_FRONT,
    "fender": VehiclePhoto.Section.DRIVER_SIDE_PROFILE,
    "door": VehiclePhoto.Section.DRIVER_SIDE_PROFILE,
    "mirror": VehiclePhoto.Section.DRIVER_SIDE_PROFILE,
    "tail light": VehiclePhoto.Section.DIRECT_REAR,
    "taillight": VehiclePhoto.Section.DIRECT_REAR,
    "tail lamp": VehiclePhoto.Section.DIRECT_REAR,
    "rear bumper": VehiclePhoto.Section.DIRECT_REAR,
    "trunk": VehiclePhoto.Section.DIRECT_REAR,
    "wheel": VehiclePhoto.Section.WHEELS,
    "tire": VehiclePhoto.Section.WHEELS,
    "rim": VehiclePhoto.Section.WHEELS,
    "engine": VehiclePhoto.Section.ENGINE_BAY,
    "motor": VehiclePhoto.Section.ENGINE_BAY,
    "transmission": VehiclePhoto.Section.ENGINE_BAY,
    "dashboard": VehiclePhoto.Section.DASHBOARD,
    "instrument": VehiclePhoto.Section.DASHBOARD,
    "steering": VehiclePhoto.Section.DASHBOARD,
    "seat": VehiclePhoto.Section.DRIVER_SEAT,
    "console": VehiclePhoto.Section.CENTER_CONSOLE,
    "radio": VehiclePhoto.Section.CENTER_CONSOLE,
    "infotainment": VehiclePhoto.Section.CENTER_CONSOLE,
    "odometer": VehiclePhoto.Section.ODOMETER,
}


def primary_section_for_part_label(label: str) -> str:
    """Return the best VehiclePhoto.Section for a part label."""
    label_lower = (label or "").lower()
    for keyword, section in PART_PRIMARY_SECTION_MAP.items():
        if keyword in label_lower:
            return section
    return VehiclePhoto.Section.FRONT_DRIVER_CORNER


class PartOptionSet(models.Model):
    """
    Options scraped from car-part.com for a (vehicle, part_family) combination.
    One row per lookup; options within it are PartOption rows.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FOUND = "found", "Options found"
        NO_OPTIONS = "no_options", "No options (All)"
        YEAR_RANGE = "year_range", "Year range shown (car-part.com unknown)"
        UNDEFINED = "undefined", "car-part.com doesn't know this part"
        FAILED = "failed", "Scrape failed"

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="part_option_sets",
    )
    part_family = models.ForeignKey(
        PartFamily,
        on_delete=models.CASCADE,
        related_name="option_sets",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    raw_options = models.JSONField(default=list, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("vehicle", "part_family")]

    def __str__(self):
        return f"OptionSet v={self.vehicle_id} pf={self.part_family_id} ({self.status})"


class PartOption(models.Model):
    """
    One selectable option for a part on a specific vehicle.
    E.g. Left / Right, LCI / Pre-LCI, LED / Halogen.
    """

    option_set = models.ForeignKey(
        PartOptionSet,
        on_delete=models.CASCADE,
        related_name="options",
    )
    option_key = models.CharField(max_length=64)
    option_label = models.CharField(max_length=128)
    confidence = models.FloatField(
        default=1.0,
        help_text="AI confidence 0–1 that this option applies to the vehicle.",
    )
    needs_manual_check = models.BooleanField(
        default=False,
        help_text="True when confidence < 0.9 and seller must verify.",
    )
    is_applicable = models.BooleanField(
        default=True,
        help_text="False if AI determined the vehicle doesn't have this option.",
    )
    source = models.CharField(
        max_length=32,
        default="car_part_com",
        help_text="car_part_com | perplexity | manual | all",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("option_set", "option_key")]

    def __str__(self):
        return f"Option {self.option_label} (conf={self.confidence:.0%})"


class PartCompatibility(models.Model):
    """Compatible donor vehicles for a specific part option (from Perplexity)."""

    option = models.ForeignKey(
        PartOption,
        on_delete=models.CASCADE,
        related_name="compatibilities",
    )
    make = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    year_range_start = models.PositiveSmallIntegerField()
    year_range_end = models.PositiveSmallIntegerField()
    trim = models.CharField(max_length=128, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["make", "model", "year_range_start"]

    def __str__(self):
        return f"{self.make} {self.model} {self.year_range_start}–{self.year_range_end}"


class VehiclePart(models.Model):
    class ListingState(models.TextChoices):
        DRAFT = "draft", "Draft (not priced)"
        MESSAGE_ONLY = "message_only", "Message seller"
        BUY_NOW = "buy_now", "Buy now"
        SOLD = "sold", "Sold"
        UNAVAILABLE = "unavailable", "Unavailable"
        SOLD_ELSEWHERE = "sold_elsewhere", "Sold elsewhere"

    class ConditionDraft(models.TextChoices):
        OEM_UNTESTED = "oem_untested", "OEM — untested"
        OEM_TESTED = "oem_tested", "OEM — tested working"
        AFTERMARKET = "aftermarket", "Aftermarket"
        NEW = "new", "New"
        USED = "used", "Used"

    class Grade(models.TextChoices):
        A = "A", "Grade A — Excellent (< 60k miles or < 15k/yr)"
        B = "B", "Grade B — Good (60k–200k miles, minimal repair)"
        C = "C", "Grade C — Fair (> 200k miles or significant repair)"
        X = "X", "Grade X — Ungraded / insufficient info"

    class PackageSizeCategory(models.TextChoices):
        SMALL = "small", "Small (fits in box, ships parcel)"
        MEDIUM = "medium", "Medium (oversized box / freight)"
        LARGE = "large", "Large (pallet 48×48)"
        PALLET = "pallet", "Pallet"
        CRATE = "crate", "Crate"

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="parts",
    )
    part_family = models.ForeignKey(
        PartFamily,
        on_delete=models.CASCADE,
        related_name="vehicle_parts",
    )
    selected_option = models.ForeignKey(
        PartOption,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vehicle_parts",
        help_text="The specific part option (e.g. Left / LED) assigned to this listing.",
    )
    variant_key = models.CharField(max_length=256, default="", blank=True)
    label = models.CharField(max_length=512)
    listing_state = models.CharField(
        max_length=32,
        choices=ListingState.choices,
        default=ListingState.DRAFT,
    )
    condition_draft = models.CharField(
        max_length=32,
        choices=ConditionDraft.choices,
        blank=True,
        null=True,
    )
    grade = models.CharField(
        max_length=2,
        choices=Grade.choices,
        default=Grade.X,
        help_text="A/B/C/X based on mileage and AI condition analysis.",
    )
    color_override = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    condition_description = models.TextField(blank=True)
    ai_description = models.TextField(
        blank=True,
        help_text="AI-generated condition description derived from vehicle images.",
    )
    # Shipping options
    local_pickup_only = models.BooleanField(
        default=False,
        help_text="If true, buyer cannot purchase — contact seller for local pickup only.",
    )
    shipping_disabled = models.BooleanField(
        default=False,
        help_text="Shipping not available; local pickup only (no buy button).",
    )
    package_size_category = models.CharField(
        max_length=16,
        choices=PackageSizeCategory.choices,
        blank=True,
        help_text="AI-estimated packaging category; drives EasyShip vs FreightQuote routing.",
    )
    # Dimensions (actual part)
    size_length_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_width_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_height_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    # Packaged dimensions
    size_packaged_length_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_packaged_width_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_packaged_height_cm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_packaged_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    use_vehicle_location = models.BooleanField(default=True)
    location_note = models.CharField(max_length=255, blank=True)
    image_urls = models.JSONField(default=list, blank=True)
    primary_photo_section = models.CharField(
        max_length=32,
        blank=True,
        help_text="VehiclePhoto.Section key to use as the lead image in buyer-facing sliders.",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="USD; required for Buy Now listings.",
    )
    return_policy = models.CharField(
        max_length=16,
        choices=ReturnPolicy.choices,
        default=ReturnPolicy.GREEN,
    )
    buy_now_expires_at = models.DateTimeField(null=True, blank=True)
    offer_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    offer_source_quote = models.ForeignKey(
        "messaging.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_on_parts",
    )
    is_damaged = models.BooleanField(default=False)
    is_removed = models.BooleanField(default=False)
    # Pipeline tracking
    listing_pipeline_status = models.CharField(
        max_length=32,
        default="idle",
        help_text="idle | processing | done | failed",
    )
    listing_pipeline_started_at = models.DateTimeField(null=True, blank=True)
    listing_pipeline_completed_at = models.DateTimeField(null=True, blank=True)
    listing_pipeline_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["part_family__category__sort_order", "part_family__name", "variant_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "part_family", "variant_key"],
                name="uniq_vehicle_part_family_variant",
            ),
        ]

    def __str__(self):
        return f"{self.vehicle_id} · {self.label}"

    @property
    def effective_listing_state(self) -> str:
        if self.listing_state != self.ListingState.BUY_NOW:
            return self.listing_state
        if self.buy_now_expires_at and self.buy_now_expires_at < timezone.now():
            return self.ListingState.DRAFT
        return self.ListingState.BUY_NOW

    @property
    def effective_buy_price(self):
        now = timezone.now()
        if (
            self.offer_price_usd is not None
            and self.offer_expires_at
            and self.offer_expires_at > now
        ):
            return self.offer_price_usd
        return self.price

    def clear_expired_offer_if_needed(self) -> bool:
        if not self.offer_expires_at or self.offer_expires_at > timezone.now():
            return False
        self.offer_price_usd = None
        self.offer_expires_at = None
        self.offer_source_quote_id = None
        self.save(update_fields=["offer_price_usd", "offer_expires_at", "offer_source_quote", "updated_at"])
        return True

    def is_purchasable(self) -> bool:
        """Returns False if part is local-pickup-only or shipping disabled."""
        if self.local_pickup_only or self.shipping_disabled:
            return False
        return self.effective_listing_state == self.ListingState.BUY_NOW


class VehiclePartPhoto(models.Model):
    vehicle_part = models.ForeignKey(
        VehiclePart,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="vehicle_part_photos/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class BrowseErrorReport(models.Model):
    """Buyer-submitted flag: search result was wrong / inaccurate."""

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="browse_error_reports",
    )
    vehicle_part = models.ForeignKey(
        VehiclePart,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="error_reports",
    )
    search_query = models.CharField(max_length=512, blank=True)
    issue_description = models.TextField()
    contact_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"BrowseErrorReport #{self.id}"
