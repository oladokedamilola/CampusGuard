# smart_surveillance/reports/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import IncidentCategory, IncidentLocation, IncidentReport, IncidentImage, IncidentUpdate

@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')

@admin.register(IncidentLocation)
class IncidentLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'campus_zone')
    list_filter = ('building', 'campus_zone')
    search_fields = ('name', 'building', 'description')

class IncidentImageInline(admin.TabularInline):
    model = IncidentImage
    extra = 0
    readonly_fields = ('uploaded_at', 'faces_blurred', 'has_analysis')
    
    def has_analysis(self, obj):
        return bool(obj.ai_analysis)
    has_analysis.boolean = True
    has_analysis.short_description = 'AI Analysis'

class IncidentUpdateInline(admin.TabularInline):
    model = IncidentUpdate
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_reporter', 'category', 'location', 
                   'status_badge', 'priority_badge', 'created_at', 'image_count')
    list_filter = ('status', 'priority', 'category', 'location', 'created_at')
    search_fields = ('title', 'description', 'reporter__email', 'reporter__first_name')
    readonly_fields = ('created_at', 'updated_at', 'display_reporter')
    inlines = [IncidentImageInline, IncidentUpdateInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'reporter', 'display_reporter', 'anonymous')
        }),
        ('Classification', {
            'fields': ('category', 'location', 'priority', 'status')
        }),
        ('Timestamps', {
            'fields': ('incident_date', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'processing': 'blue',
            'resolved': 'green',
            'closed': 'black'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'low': 'green',
            'medium': 'orange',
            'high': 'red',
            'critical': 'darkred'
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Images'

@admin.register(IncidentImage)
class IncidentImageAdmin(admin.ModelAdmin):
    list_display = ('incident', 'image_preview', 'has_analysis', 'faces_blurred', 'uploaded_at')
    list_filter = ('faces_blurred', 'analysis_requested', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'analyzed_at', 'ai_analysis_preview')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height: 50px;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Preview'
    
    def ai_analysis_preview(self, obj):
        if obj.ai_analysis:
            return format_html('<pre>{}</pre>', str(obj.ai_analysis)[:500])
        return "-"
    ai_analysis_preview.short_description = 'AI Analysis'