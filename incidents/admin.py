from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Incident, IncidentComment, IncidentActionLog, Evidence, IncidentStatistic

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    """Admin interface for Incident model."""
    
    list_display = (
        'incident_id', 'title', 'camera', 'incident_type', 
        'severity_badge', 'status_badge', 'detected_at',
        'assigned_to', 'response_time'
    )
    
    list_filter = (
        'status', 'severity', 'incident_type', 'camera__location',
        'detected_at', 'is_false_positive', 'requires_police_report'
    )
    
    search_fields = (
        'incident_id', 'title', 'description', 'camera__name',
        'assigned_to__email', 'assigned_to__first_name'
    )
    
    readonly_fields = (
        'incident_id', 'created_at', 'updated_at', 
        'detected_at', 'acknowledged_at', 'resolved_at',
        'status_badge_display', 'severity_badge_display'
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'incident_id', 'title', 'description', 'incident_type',
                'severity_badge_display', 'status_badge_display'
            )
        }),
        (_('Source & Location'), {
            'fields': (
                'camera', 'video_file', 'location_description',
                'gps_coordinates'
            )
        }),
        (_('Evidence'), {
            'fields': (
                'evidence_image', 'evidence_video_clip', 'thumbnail',
                'confidence_score', 'detection_metadata'
            )
        }),
        (_('Assignment & Tracking'), {
            'fields': (
                'assigned_to', 'acknowledged_by', 'resolved_by',
                'detected_at', 'acknowledged_at', 'resolved_at'
            )
        }),
        (_('Investigation'), {
            'fields': (
                'tags', 'is_false_positive', 'requires_police_report',
                'police_report_number', 'notes'
            )
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'acknowledge_incidents', 'resolve_incidents', 
        'mark_as_false_alarm', 'escalate_incidents'
    ]
    
    def severity_badge(self, obj):
        """Display severity as colored badge."""
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark',
        }
        color = colors.get(obj.severity, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_severity_display()
        )
    
    severity_badge.short_description = _('Severity')
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'detected': 'warning',
            'acknowledged': 'info',
            'investigating': 'primary',
            'resolved': 'success',
            'false_alarm': 'secondary',
            'escalated': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    
    status_badge.short_description = _('Status')
    
    def severity_badge_display(self, obj):
        """Display severity badge in detail view."""
        return self.severity_badge(obj)
    
    severity_badge_display.short_description = _('Severity')
    
    def status_badge_display(self, obj):
        """Display status badge in detail view."""
        return self.status_badge(obj)
    
    status_badge_display.short_description = _('Status')
    
    def response_time(self, obj):
        """Display response time in minutes."""
        response = obj.get_response_time()
        if response:
            minutes = response.total_seconds() / 60
            return f"{minutes:.1f} min"
        return "-"
    
    response_time.short_description = _('Response Time')
    
    def acknowledge_incidents(self, request, queryset):
        """Acknowledge selected incidents."""
        from django.utils import timezone
        updated = 0
        for incident in queryset.filter(status='detected'):
            incident.status = 'acknowledged'
            incident.acknowledged_by = request.user
            incident.acknowledged_at = timezone.now()
            incident.save()
            updated += 1
        self.message_user(request, f'{updated} incidents acknowledged.')
    
    acknowledge_incidents.short_description = _('Acknowledge selected incidents')
    
    def resolve_incidents(self, request, queryset):
        """Resolve selected incidents."""
        from django.utils import timezone
        updated = 0
        for incident in queryset.exclude(status='resolved'):
            incident.status = 'resolved'
            incident.resolved_by = request.user
            incident.resolved_at = timezone.now()
            incident.save()
            updated += 1
        self.message_user(request, f'{updated} incidents resolved.')
    
    resolve_incidents.short_description = _('Resolve selected incidents')
    
    def mark_as_false_alarm(self, request, queryset):
        """Mark selected incidents as false alarms."""
        from django.utils import timezone
        updated = 0
        for incident in queryset:
            incident.status = 'false_alarm'
            incident.resolved_by = request.user
            incident.resolved_at = timezone.now()
            incident.is_false_positive = True
            incident.save()
            updated += 1
        self.message_user(request, f'{updated} incidents marked as false alarms.')
    
    mark_as_false_alarm.short_description = _('Mark as false alarm')
    
    def escalate_incidents(self, request, queryset):
        """Escalate selected incidents."""
        updated = 0
        for incident in queryset:
            incident.status = 'escalated'
            incident.requires_police_report = True
            incident.save()
            updated += 1
        self.message_user(request, f'{updated} incidents escalated.')
    
    escalate_incidents.short_description = _('Escalate to authorities')

@admin.register(IncidentComment)
class IncidentCommentAdmin(admin.ModelAdmin):
    """Admin interface for IncidentComment model."""
    
    list_display = ('incident', 'user', 'truncated_comment', 'created_at', 'is_internal')
    list_filter = ('is_internal', 'created_at', 'user')
    search_fields = ('comment', 'incident__incident_id', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    def truncated_comment(self, obj):
        """Display truncated comment."""
        if len(obj.comment) > 50:
            return f"{obj.comment[:50]}..."
        return obj.comment
    
    truncated_comment.short_description = _('Comment')

@admin.register(IncidentActionLog)
class IncidentActionLogAdmin(admin.ModelAdmin):
    """Admin interface for IncidentActionLog model."""
    
    list_display = ('incident', 'user', 'action', 'created_at')
    list_filter = ('action', 'created_at', 'user')
    search_fields = ('incident__incident_id', 'user__email', 'details')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    """Admin interface for Evidence model."""
    
    list_display = ('incident', 'evidence_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('evidence_type', 'uploaded_at')
    search_fields = ('incident__incident_id', 'description', 'uploaded_by__email')
    readonly_fields = ('uploaded_at',)

@admin.register(IncidentStatistic)
class IncidentStatisticAdmin(admin.ModelAdmin):
    """Admin interface for IncidentStatistic model."""
    
    list_display = ('date', 'total_incidents', 'false_alarm_count', 'avg_response_time')
    list_filter = ('date',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'