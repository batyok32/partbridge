# analytics/serializers.py
from rest_framework import serializers
from .models import (
    PartAnalysis,
    DashboardStats,
    AnalysisCarPhoto,
)
from django.utils import timezone
from datetime import datetime


# ============================================================================
# SINGLE PART ANALYSIS SERIALIZERS (Original)
# ============================================================================


class PartAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for both single and multi-part analysis"""
    duration = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PartAnalysis
        fields = [
            'id', 'user', 'vehicle', 'part_name', 'part_number', 'vehicle_year', 
            'vehicle_make', 'vehicle_model', 'time_period_days', 
            'is_multi_part', 'analysis_data', 
            'category_analysis', 'filtering_stats',
            'prompt_applied', 'prompt_text',
            'filtered_categories', 'filtered_part_out_summary',
            'status', 'error_message', 'created_at', 'completed_at',
            'duration', 'display_name'
        ]
        read_only_fields = [
            'id', 'user', 'vehicle', 'status', 'analysis_data', 
            'category_analysis', 'filtering_stats',
            'error_message', 'created_at', 'completed_at',
            'prompt_applied', 'prompt_text',
            'filtered_categories', 'filtered_part_out_summary',
        ]
    
    def get_duration(self, obj):
        """Calculate analysis duration in seconds"""
        if obj.completed_at and obj.created_at:
            delta = obj.completed_at - obj.created_at
            return int(delta.total_seconds())
        return None
    
    def get_display_name(self, obj):
        """Generate display name based on analysis type"""
        if obj.is_multi_part:
            return f"{obj.vehicle_year} {obj.vehicle_make} {obj.vehicle_model} (Multi-Part)"
        else:
            vehicle = f"{obj.vehicle_year} {obj.vehicle_make} {obj.vehicle_model}".strip()
            if vehicle:
                return f"{obj.part_name} - {vehicle}"
            return obj.part_name


class PartAnalysisRequestSerializer(serializers.Serializer):
    """Serializer for requesting part analysis - supports both modes"""
    
    # Part identification (required for single-part)
    part_name = serializers.CharField(
        max_length=200, 
        required=False, 
        allow_blank=True,
        help_text="Part name - required for single-part analysis"
    )
    part_number = serializers.CharField(
        max_length=100, 
        required=False, 
        allow_blank=True,
        help_text="OEM or aftermarket part number (optional)"
    )
    
    # Vehicle identification (required for multi-part)
    vehicle_year = serializers.IntegerField(
        required=False, 
        allow_null=True,
        help_text="Vehicle year - required for multi-part analysis"
    )
    vehicle_make = serializers.CharField(
        max_length=100, 
        required=False, 
        allow_blank=True,
        help_text="Vehicle make - required for multi-part analysis"
    )
    vehicle_model = serializers.CharField(
        max_length=100, 
        required=False, 
        allow_blank=True,
        help_text="Vehicle model - required for multi-part analysis"
    )
    
    # Analysis parameters
    time_period_days = serializers.IntegerField(
        default=90,
        help_text="Analysis time period in days (30, 60, 90, 180)"
    )
    
    # Analysis type
    is_multi_part = serializers.BooleanField(
        default=False,
        help_text="If true, analyzes all parts for vehicle. If false, analyzes single part."
    )
    
    
    # Configuration overrides
    config = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Optional configuration overrides (max_pages, use_ai, etc.)"
    )
    
    def validate(self, data):
        """
        Validate required fields based on analysis type
        """
        is_multi_part = data.get('is_multi_part', False)
        
        if is_multi_part:
            # Multi-part requires vehicle info
            missing_fields = []
            if not data.get('vehicle_year'):
                missing_fields.append('vehicle_year')
            if not data.get('vehicle_make'):
                missing_fields.append('vehicle_make')
            if not data.get('vehicle_model'):
                missing_fields.append('vehicle_model')
            
            if missing_fields:
                raise serializers.ValidationError({
                    'detail': f"Multi-part analysis requires: {', '.join(missing_fields)}",
                    'missing_fields': missing_fields
                })
        else:
            # Single-part requires part name
            if not data.get('part_name'):
                raise serializers.ValidationError({
                    'part_name': "Part name is required for single-part analysis"
                })
        
        # Validate time period
        valid_periods = [30, 60, 90, 180]
        time_period = data.get('time_period_days', 90)
        if time_period not in valid_periods:
            raise serializers.ValidationError({
                'time_period_days': f"Time period must be one of: {valid_periods}"
            })
        
        return data
    
    def validate_vehicle_year(self, value):
        """Validate vehicle year is reasonable"""
        if value is not None:
            current_year = datetime.now().year
            if value < 1990 or value > current_year + 1:
                raise serializers.ValidationError(
                    f"Vehicle year must be between 1990 and {current_year + 1}"
                )
        return value


# ============================================================================
# DASHBOARD SERIALIZERS
# ============================================================================

class DashboardStatsSerializer(serializers.ModelSerializer):
    """Serializer for dashboard statistics"""
    
    class Meta:
        model = DashboardStats
        fields = '__all__'

        read_only_fields = ['id', 'last_calculated_at']

# ============================================================================
# EXPORT SERIALIZERS
# ============================================================================

class ExportRequestSerializer(serializers.Serializer):
    """Serializer for export requests"""
    format = serializers.ChoiceField(
        choices=['json', 'csv'],
        default='json'
    )


class AnalysisCarPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisCarPhoto
        fields = [
            "id",
            "analysis",
            "side",
            "image",
            "image_url",
            "created_at",
        ]
        read_only_fields = ["id", "analysis", "image_url", "created_at"]

    def get_image_url(self, obj):
        if obj.image and hasattr(obj.image, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return ""


