# analytics/admin.py (Extended with Multi-Part )
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PartAnalysis, 

    DashboardStats
)


@admin.register(PartAnalysis)
class PartAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'part_name', 'vehicle', 'user_email', 'status', 
        'time_period_days', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'time_period_days', 'created_at']
    search_fields = ['part_name', 'user__email', 'vehicle_make', 'vehicle_model', 'vehicle__vin']
    readonly_fields = ['id', 'created_at', 'completed_at', 'analysis_data_preview']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'user', 'vehicle', 'status')
        }),
        ('Part Details', {
            'fields': ('part_name', 'vehicle_year', 'vehicle_make', 'vehicle_model')
        }),
        ('Analysis', {
            'fields': ('time_period_days', 'analysis_data', 'analysis_data_preview', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    
    def analysis_data_preview(self, obj):
        if obj.analysis_data:
            rec = obj.analysis_data.get('recommendation', {})
            return format_html(
                '<strong>Status:</strong> {}<br>'
                '<strong>Price:</strong> ${}<br>'
                '<strong>Confidence:</strong> {}',
                rec.get('status', 'N/A'),
                rec.get('suggested_price', 'N/A'),
                rec.get('confidence', 'N/A')
            )
        return 'No data yet'
    analysis_data_preview.short_description = 'Analysis Summary'



@admin.register(DashboardStats)
class DashboardStatsAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'total_listings', 'active_listings', 
        'sold_listings', 'total_revenue',
        'last_calculated_at'
    ]
    list_filter = ['last_calculated_at']
    search_fields = ['user__email']
    readonly_fields = [
        'id', 'last_calculated_at', 'stats_summary'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Listing Stats', {
            'fields': (
                'total_listings', 'active_listings', 'sold_listings', 'draft_listings',
                'listings_this_month', 'sales_this_month'
            )
        }),
        ('Financial Stats', {
            'fields': (
                'total_revenue', 'revenue_this_month', 'avg_selling_price'
            )
        }),
        ('Engagement Stats', {
            'fields': (
                'total_views', 'total_watchers', 'conversion_rate'
            )
        }),
       
        ('Meta', {
            'fields': ('last_calculated_at', 'stats_summary')
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def stats_summary(self, obj):
        return format_html(
            '<h3>Summary</h3>'
            '<p><strong>Listings:</strong> {} total, {} active, {} sold</p>'
            '<p><strong>Revenue:</strong> ${:,.2f} total, ${:,.2f} this month</p>'
            '<p><strong>Conversion:</strong> {:.1f}%</p>',
            obj.total_listings, obj.active_listings, obj.sold_listings,
            obj.total_revenue, obj.revenue_this_month,
            obj.conversion_rate,
        )
    stats_summary.short_description = 'Statistics Summary'
