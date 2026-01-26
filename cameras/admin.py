from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Camera, CameraGroup, CameraHealthLog

@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    """Admin interface for Camera model."""
    
    list_display = (
        'name', 'camera_id', 'location', 'camera_type', 
        'status_badge', 'is_active', 'last_ping', 'created_at'
    )
    
    list_filter = (
        'status', 'camera_type', 'is_active', 'location__institution',
        'has_night_vision', 'has_audio', 'created_at'
    )
    
    search_fields = (
        'name', 'camera_id', 'ip_address', 'serial_number',
        'manufacturer', 'model', 'location__name'
    )
    
    readonly_fields = (
        'camera_id', 'created_at', 'updated_at', 'last_ping',
        'status_badge_display'
    )
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name', 'camera_id', 'location', 'camera_type', 'status',
                'is_active', 'notes'
            )
        }),
        (_('Connection Details'), {
            'fields': (
                'connection_protocol', 'stream_url', 'ip_address', 'port',
                'username', 'password'
            )
        }),
        (_('Technical Specifications'), {
            'fields': (
                'resolution', 'fps', 'has_night_vision', 'has_audio',
                'field_of_view'
            )
        }),
        (_('Operational Settings'), {
            'fields': (
                'motion_detection_enabled', 'recording_enabled',
                'detection_zones'
            )
        }),
        (_('Maintenance Information'), {
            'fields': (
                'manufacturer', 'model', 'serial_number',
                'installation_date', 'warranty_expiry',
                'last_maintenance', 'next_maintenance'
            )
        }),
        (_('System Information'), {
            'fields': (
                'status_badge_display', 'created_at', 'updated_at', 'last_ping'
            )
        }),
    )
    
    actions = ['activate_cameras', 'deactivate_cameras', 'mark_for_maintenance']
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'active': 'success',
            'inactive': 'secondary',
            'maintenance': 'warning',
            'offline': 'danger',
            'error': 'dark',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    
    status_badge.short_description = _('Status')
    
    def status_badge_display(self, obj):
        """Display status badge in detail view."""
        return self.status_badge(obj)
    
    status_badge_display.short_description = _('Status')
    
    def activate_cameras(self, request, queryset):
        """Activate selected cameras."""
        updated = queryset.update(is_active=True, status=Camera.Status.ACTIVE)
        self.message_user(request, f'{updated} cameras activated.')
    
    activate_cameras.short_description = _('Activate selected cameras')
    
    def deactivate_cameras(self, request, queryset):
        """Deactivate selected cameras."""
        updated = queryset.update(is_active=False, status=Camera.Status.INACTIVE)
        self.message_user(request, f'{updated} cameras deactivated.')
    
    deactivate_cameras.short_description = _('Deactivate selected cameras')
    
    def mark_for_maintenance(self, request, queryset):
        """Mark selected cameras for maintenance."""
        updated = queryset.update(status=Camera.Status.MAINTENANCE)
        self.message_user(request, f'{updated} cameras marked for maintenance.')
    
    mark_for_maintenance.short_description = _('Mark for maintenance')

@admin.register(CameraGroup)
class CameraGroupAdmin(admin.ModelAdmin):
    """Admin interface for CameraGroup model."""
    
    list_display = ('name', 'camera_count', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('cameras',)
    
    def camera_count(self, obj):
        """Display count of cameras in group."""
        return obj.cameras.count()
    
    camera_count.short_description = _('Camera Count')

@admin.register(CameraHealthLog)
class CameraHealthLogAdmin(admin.ModelAdmin):
    """Admin interface for CameraHealthLog model."""
    
    list_display = (
        'camera', 'status_badge', 'uptime_percentage', 
        'packet_loss', 'response_time', 'recorded_at'
    )
    
    list_filter = ('status', 'camera__location', 'recorded_at')
    search_fields = ('camera__name', 'camera__camera_id')
    readonly_fields = ('recorded_at',)
    date_hierarchy = 'recorded_at'
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'active': 'success',
            'inactive': 'secondary',
            'maintenance': 'warning',
            'offline': 'danger',
            'error': 'dark',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    
    status_badge.short_description = _('Status')