# analytics/models.py (Extended with Multi-Part Analysis)
from django.db import models
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator

class PartAnalysis(models.Model):
    """eBay market scrape + AI categorisation (single part or whole-vehicle multi-part)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="part_analyses")
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="market_analyses",
    )
    
    # Part identification
    part_name = models.CharField(max_length=200, blank=True, null=True)
    vehicle_year = models.IntegerField(null=True, blank=True)
    vehicle_make = models.CharField(max_length=100, blank=True)
    vehicle_model = models.CharField(max_length=100, blank=True)
    
    is_multi_part = models.BooleanField(
        default=False,
        help_text="If True, analyzes all parts for the vehicle instead of single part"
    )
    # Analysis parameters
    time_period_days = models.IntegerField(default=90)
    
    
    # Results
    analysis_data = models.JSONField(default=dict)
    # NEW FIELD: Part number for more precise searches
    part_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="OEM or aftermarket part number"
    )
    
    # NEW FIELD: Category-based analysis results
    category_analysis = models.JSONField(
        default=dict,
        help_text="Analysis broken down by eBay category"
    )
    
    # NEW FIELD: Filtering statistics
    filtering_stats = models.JSONField(
        default=dict,
        help_text="Vehicle matching and relevance filtering statistics"
    )
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Saved prompt filtering state (do not mutate analysis_data)
    prompt_applied = models.BooleanField(default=False)
    prompt_text = models.TextField(blank=True)
    filtered_categories = models.JSONField(default=list, blank=True)
    filtered_part_out_summary = models.JSONField(default=dict, blank=True)
    filtered_categories_history = models.JSONField(default=list, blank=True)
    filtered_part_out_history = models.JSONField(default=list, blank=True)
    prompt_text_history = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'part_analyses'
        verbose_name_plural = "Part Analyses"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        if self.vehicle_id:
            return f"Market analysis for vehicle {self.vehicle_id}"
        return f"Analysis: {self.part_name} for {self.user.email}"


class AnalysisCarPhoto(models.Model):
    """Stores vehicle photos for analytics-driven listing workflows."""

    SIDE_CHOICES = [
        ("front_three_quarter", "Front 3/4 view"),
        ("rear_three_quarter", "Rear 3/4 view"),
        ("front_straight", "Straight-on front"),
        ("rear_straight", "Straight-on rear"),
        ("driver_side", "Driver side profile"),
        ("passenger_side", "Passenger side profile"),
        ("wheel_front_left", "Wheel/Rim - Front left"),
        ("wheel_front_right", "Wheel/Rim - Front right"),
        ("wheel_rear_left", "Wheel/Rim - Rear left"),
        ("wheel_rear_right", "Wheel/Rim - Rear right"),
        ("headlights", "Headlights"),
        ("taillights", "Taillights"),
        ("windshield", "Windshield"),
        ("windows", "All windows"),
        ("mirrors", "Mirrors"),
        ("door_handles", "Door handles/locks"),
        ("fuel_door", "Fuel door"),
        ("exhaust_tips", "Exhaust tips"),
        ("undercarriage", "Undercarriage"),
        ("roof", "Roof / Sunroof"),
        ("damage_closeups", "Scratches/dents close-ups"),
        ("paint_chips_rust", "Paint chips / rust"),
        ("panel_gaps", "Panel gaps/alignment"),
        ("license_plate_front", "License plate - front"),
        ("license_plate_rear", "License plate - rear"),
        ("vin_plate", "VIN plate"),
        ("dashboard_view", "Dashboard - wide"),
        ("instrument_cluster", "Instrument cluster / odometer"),
        ("center_console", "Center console / infotainment"),
        ("steering_wheel", "Steering wheel"),
        ("climate_controls", "Climate controls"),
        ("gear_shifter", "Gear shifter"),
        ("front_seats", "Front seats"),
        ("rear_seats", "Rear seats"),
        ("seat_controls", "Seat adjustments / controls"),
        ("headrests", "Headrests"),
        ("seatbelts", "Seatbelts / buckles"),
        ("trunk", "Trunk / cargo area"),
        ("under_trunk_floor", "Under trunk floor"),
        ("glove_compartment", "Glove compartment"),
        ("center_console_storage", "Center console storage"),
        ("door_pockets", "Door pockets"),
        ("overhead_storage", "Overhead storage"),
        ("headliner", "Headliner"),
        ("carpet_floor_mats", "Carpet / floor mats"),
        ("door_panels", "Door panels / armrests"),
        ("buttons_switches", "Buttons / switches"),
        ("pedals", "Pedals"),
        ("engine_bay_overview", "Engine bay overview"),
        ("engine_block", "Engine block / components"),
        ("fluid_reservoirs", "Fluid reservoirs"),
        ("battery", "Battery / terminals"),
        ("belts_hoses", "Belts / hoses"),
        ("leaks_corrosion", "Leaks / corrosion"),
        ("engine_bay_cleanliness", "Engine bay cleanliness"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="analysis_car_photos",
    )
    analysis = models.ForeignKey(
        "analytics.PartAnalysis",
        on_delete=models.CASCADE,
        related_name="car_photos",
    )
    side = models.CharField(max_length=64, choices=SIDE_CHOICES)
    image = models.ImageField(upload_to="analysis_car_photos/%Y/%m/%d/")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "analysis_car_photos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.analysis_id} - {self.side}"


class DashboardStats(models.Model):
    """Cached dashboard statistics for users"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='dashboard_stats')
    
    # Listing stats
    total_listings = models.IntegerField(default=0)
    active_listings = models.IntegerField(default=0)
    sold_listings = models.IntegerField(default=0)
    draft_listings = models.IntegerField(default=0)
    
    # Financial stats
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue_this_month = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    avg_selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Engagement stats
    total_views = models.IntegerField(default=0)
    total_watchers = models.IntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Time-based performance
    listings_this_month = models.IntegerField(default=0)
    sales_this_month = models.IntegerField(default=0)
    
    last_calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_stats'
        verbose_name_plural = "Dashboard Stats"
    
    def __str__(self):
        return f"Stats for {self.user.email}"