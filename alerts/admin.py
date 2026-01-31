# smart_surveillance/alerts/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from .models import Alert, AlertRule, NotificationPreference

# ============ Custom Filters ============

class AlertStatusFilter(admin.SimpleListFilter):
    """Filter alerts by status."""
    title = _('Status')
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Alert.AlertStatus.choices
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

class AlertTypeFilter(admin.SimpleListFilter):
    """Filter alerts by type."""
    title = _('Alert Type')
    parameter_name = 'alert_type'
    
    def lookups(self, request, model_admin):
        return Alert.AlertType.choices
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(alert_type=self.value())
        return queryset

class ReadStatusFilter(admin.SimpleListFilter):
    """Filter alerts by read status."""
    title = _('Read Status')
    parameter_name = 'is_read'
    
    def lookups(self, request, model_admin):
        return (
            ('read', _('Read')),
            ('unread', _('Unread')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'read':
            return queryset.filter(is_read=True)
        elif self.value() == 'unread':
            return queryset.filter(is_read=False)
        return queryset

class AlertRuleActiveFilter(admin.SimpleListFilter):
    """Filter alert rules by active status."""
    title = _('Active Status')
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', _('Active')),
            ('inactive', _('Inactive')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        elif self.value() == 'inactive':
            return queryset.filter(is_active=False)
        return queryset

# ============ Custom Admin Actions ============

def cleanup_old_alerts(modeladmin, request, queryset):
    """Clean up alerts older than 30 days."""
    from .services import AlertCleanupService
    count = AlertCleanupService.cleanup_old_alerts(30)
    modeladmin.message_user(request, f'Deleted {count} alerts older than 30 days.')
cleanup_old_alerts.short_description = 'Clean up alerts older than 30 days'

def mark_as_read(modeladmin, request, queryset):
    """Mark selected alerts as read."""
    from django.utils import timezone
    updated = queryset.update(
        is_read=True,
        read_at=timezone.now(),
        status='read'
    )
    modeladmin.message_user(request, f'{updated} alert(s) marked as read.')
mark_as_read.short_description = _('Mark selected alerts as read')

def mark_as_unread(modeladmin, request, queryset):
    """Mark selected alerts as unread."""
    from django.utils import timezone
    updated = queryset.update(
        is_read=False,
        read_at=None
    )
    # Update status back to delivered if it was read
    from .models import Alert
    queryset.filter(status='read').update(status='delivered')
    
    modeladmin.message_user(request, f'{updated} alert(s) marked as unread.')
mark_as_unread.short_description = _('Mark selected alerts as unread')

def retry_failed_alerts(modeladmin, request, queryset):
    """Retry sending failed alerts."""
    from .services import AlertService
    
    retried = 0
    for alert in queryset.filter(status='failed', retry_count__lt=3):
        try:
            AlertService._send_alert(alert)
            retried += 1
        except Exception as e:
            modeladmin.message_user(
                request,
                f'Failed to retry alert {alert.alert_id}: {str(e)}',
                level='ERROR'
            )
    
    modeladmin.message_user(request, f'Retried {retried} failed alert(s).')
retry_failed_alerts.short_description = _('Retry sending failed alerts')

def resend_alerts(modeladmin, request, queryset):
    """Resend selected alerts."""
    from .services import AlertService
    
    resent = 0
    for alert in queryset:
        try:
            AlertService._send_alert(alert)
            resent += 1
        except Exception as e:
            modeladmin.message_user(
                request,
                f'Failed to resend alert {alert.alert_id}: {str(e)}',
                level='ERROR'
            )
    
    modeladmin.message_user(request, f'Resent {resent} alert(s).')
resend_alerts.short_description = _('Resend selected alerts')

def toggle_alert_rules(modeladmin, request, queryset):
    """Toggle selected alert rules active status."""
    for rule in queryset:
        rule.is_active = not rule.is_active
        rule.save()
    
    activated = queryset.filter(is_active=True).count()
    deactivated = queryset.filter(is_active=False).count()
    
    if activated and deactivated:
        message = f'{activated} rule(s) activated, {deactivated} rule(s) deactivated.'
    elif activated:
        message = f'{activated} rule(s) activated.'
    else:
        message = f'{deactivated} rule(s) deactivated.'
    
    modeladmin.message_user(request, message)
toggle_alert_rules.short_description = _('Toggle active status of selected rules')

# ============ Admin Classes ============

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin interface for Alert model."""
    
    # Custom actions
    admin_actions = [  # Renamed from 'actions' to avoid conflict
        mark_as_read,
        mark_as_unread,
        retry_failed_alerts,
        resend_alerts,
        cleanup_old_alerts,
    ]
    
    def get_actions(self, request):
        """Get admin actions."""
        actions = super().get_actions(request)
        # Add custom actions
        for action_func in self.admin_actions:
            actions[action_func.__name__] = (
                action_func,
                action_func.__name__,
                action_func.short_description
            )
        return actions
    
    # List display
    list_display = (
        'alert_id',
        'title_truncated',
        'recipient_link',
        'alert_type_badge',
        'status_badge',
        'is_read_badge',
        'camera_link',
        'created_at_formatted',
        'action_buttons',  # Renamed from 'actions'
    )
    
    list_display_links = ('alert_id', 'title_truncated')
    
    # Filters
    list_filter = (
        AlertTypeFilter,
        AlertStatusFilter,
        ReadStatusFilter,
        'channels',
        'created_at',
        'camera',
    )
    
    # Search
    search_fields = (
        'alert_id',
        'title',
        'message',
        'recipient__email',
        'recipient__first_name',
        'recipient__last_name',
        'camera__name',
        'incident__incident_id',
    )
    
    # Date hierarchy
    date_hierarchy = 'created_at'
    
    # Pagination
    list_per_page = 50
    
    # Fieldsets for detail view
    fieldsets = (
        (_('Alert Information'), {
            'fields': (
                'alert_id',
                'title',
                'message',
                'alert_type',
                'status',
            )
        }),
        (_('Source Information'), {
            'fields': (
                'incident_link',
                'camera_link_field',
                'recipient_link_field',
            ),
            'classes': ('collapse',)
        }),
        (_('Delivery Information'), {
            'fields': (
                'channels',
                'delivery_status',
                'is_read',
                'read_at',
                'email_sent',
                'email_message_id',
            )
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'sent_at',
                'delivered_at',
            ),
            'classes': ('collapse',)
        }),
        (_('Technical Details'), {
            'fields': (
                'retry_count',
                'last_retry_at',
                'metadata',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Readonly fields
    readonly_fields = (
        'alert_id',
        'incident_link',
        'camera_link_field',
        'recipient_link_field',
        'created_at',
        'sent_at',
        'delivered_at',
        'read_at',
        'last_retry_at',
    )
    
    # Custom methods for list display
    def title_truncated(self, obj):
        """Display truncated title."""
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_truncated.short_description = _('Title')
    
    def recipient_link(self, obj):
        """Display recipient as link."""
        if obj.recipient:
            url = reverse('admin:accounts_user_change', args=[obj.recipient.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.recipient.get_full_name() or obj.recipient.email
            )
        return '-'
    recipient_link.short_description = _('Recipient')
    
    def alert_type_badge(self, obj):
        """Display alert type as badge."""
        colors = {
            'incident_detected': 'blue',
            'camera_offline': 'orange',
            'system_alert': 'red',
            'maintenance_reminder': 'green',
        }
        color = colors.get(obj.alert_type, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            obj.get_alert_type_display()
        )
    alert_type_badge.short_description = _('Type')
    
    def status_badge(self, obj):
        """Display status as badge."""
        colors = {
            'pending': 'gray',
            'sent': 'blue',
            'delivered': 'green',
            'failed': 'red',
            'read': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def is_read_badge(self, obj):
        """Display read status as badge."""
        if obj.is_read:
            return format_html(
                '<span class="badge" style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px;">✓ Read</span>'
            )
        else:
            return format_html(
                '<span class="badge" style="background-color: orange; color: white; padding: 2px 6px; border-radius: 3px;">● Unread</span>'
            )
    is_read_badge.short_description = _('Read')
    
    def camera_link(self, obj):
        """Display camera as link."""
        if obj.camera:
            url = reverse('admin:cameras_camera_change', args=[obj.camera.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.camera.name
            )
        return '-'
    camera_link.short_description = _('Camera')
    
    def created_at_formatted(self, obj):
        """Format created date."""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = _('Created')
    
    def action_buttons(self, obj):  # Renamed from 'actions'
        """Display action buttons."""
        buttons = []
        
        # Mark as read/unread
        if not obj.is_read:
            read_url = reverse('admin:alerts_alert_mark_read', args=[obj.id])
            buttons.append(
                f'<a href="{read_url}" class="button" style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none;" title="Mark as read">✓</a>'
            )
        else:
            unread_url = reverse('admin:alerts_alert_mark_unread', args=[obj.id])
            buttons.append(
                f'<a href="{unread_url}" class="button" style="background-color: orange; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none;" title="Mark as unread">↺</a>'
            )
        
        # Retry if failed
        if obj.status == 'failed' and obj.retry_count < 3:
            retry_url = reverse('admin:alerts_alert_retry', args=[obj.id])
            buttons.append(
                f'<a href="{retry_url}" class="button" style="background-color: blue; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none;" title="Retry">↻</a>'
            )
        
        return format_html(' '.join(buttons))
    action_buttons.short_description = _('Actions')
    
    # Custom methods for readonly fields in detail view
    def incident_link(self, obj):
        """Display incident as link."""
        if obj.incident:
            url = reverse('admin:incidents_incident_change', args=[obj.incident.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.incident.incident_id
            )
        return '-'
    incident_link.short_description = _('Incident')
    
    def camera_link_field(self, obj):
        """Display camera as link in detail view."""
        return self.camera_link(obj)
    camera_link_field.short_description = _('Camera')
    
    def recipient_link_field(self, obj):
        """Display recipient as link in detail view."""
        return self.recipient_link(obj)
    recipient_link_field.short_description = _('Recipient')
    
    # Custom URLs for actions
    def get_urls(self):
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:alert_id>/mark-read/',
                self.admin_site.admin_view(self.mark_read_view),
                name='alerts_alert_mark_read',
            ),
            path(
                '<int:alert_id>/mark-unread/',
                self.admin_site.admin_view(self.mark_unread_view),
                name='alerts_alert_mark_unread',
            ),
            path(
                '<int:alert_id>/retry/',
                self.admin_site.admin_view(self.retry_view),
                name='alerts_alert_retry',
            ),
        ]
        return custom_urls + urls
    
    def mark_read_view(self, request, alert_id):
        """Mark single alert as read."""
        from django.shortcuts import redirect, get_object_or_404
        
        alert = get_object_or_404(Alert, id=alert_id)
        alert.mark_as_read()
        self.message_user(request, f'Alert {alert.alert_id} marked as read.')
        
        return redirect('admin:alerts_alert_changelist')
    
    def mark_unread_view(self, request, alert_id):
        """Mark single alert as unread."""
        from django.shortcuts import redirect, get_object_or_404
        
        alert = get_object_or_404(Alert, id=alert_id)
        alert.is_read = False
        alert.read_at = None
        if alert.status == 'read':
            alert.status = 'delivered'
        alert.save()
        self.message_user(request, f'Alert {alert.alert_id} marked as unread.')
        
        return redirect('admin:alerts_alert_changelist')
    
    def retry_view(self, request, alert_id):
        """Retry single failed alert."""
        from django.shortcuts import redirect, get_object_or_404
        from .services import AlertService
        
        alert = get_object_or_404(Alert, id=alert_id)
        if alert.status == 'failed' and alert.retry_count < 3:
            try:
                AlertService._send_alert(alert)
                self.message_user(request, f'Alert {alert.alert_id} retried successfully.')
            except Exception as e:
                self.message_user(
                    request,
                    f'Failed to retry alert {alert.alert_id}: {str(e)}',
                    level='ERROR'
                )
        
        return redirect('admin:alerts_alert_changelist')
    
    # Statistics
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist."""
        response = super().changelist_view(request, extra_context)
        
        try:
            if hasattr(response, 'context_data'):
                # Get statistics
                total_alerts = Alert.objects.count()
                unread_alerts = Alert.objects.filter(is_read=False).count()
                failed_alerts = Alert.objects.filter(status='failed').count()
                today_alerts = Alert.objects.filter(
                    created_at__date=timezone.now().date()
                ).count()
                
                # Add to context
                response.context_data.update({
                    'total_alerts': total_alerts,
                    'unread_alerts': unread_alerts,
                    'failed_alerts': failed_alerts,
                    'today_alerts': today_alerts,
                })
        except Exception:
            pass
        
        return response

@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    """Admin interface for AlertRule model."""
    
    # Custom actions
    admin_actions = [toggle_alert_rules]  # Renamed from 'actions' to avoid conflict
    
    def get_actions(self, request):
        """Get admin actions."""
        actions = super().get_actions(request)
        # Add custom actions
        for action_func in self.admin_actions:
            actions[action_func.__name__] = (
                action_func,
                action_func.__name__,
                action_func.short_description
            )
        return actions
    
    # List display
    list_display = (
        'name',
        'trigger_type_badge',
        'is_active_badge',
        'priority_badge',
        'recipients_count',
        'channels_list',
        'created_at',
        'action_buttons',  # Renamed from 'actions'
    )
    
    list_display_links = ('name',)
    
    # Filters
    list_filter = (
        AlertRuleActiveFilter,
        'trigger_type',
        'priority',
        'created_at',
    )
    
    # Search
    search_fields = (
        'name',
        'description',
        'message_template',
    )
    
    # Fieldsets for detail view
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name',
                'description',
                'is_active',
                'priority',
            )
        }),
        (_('Trigger Configuration'), {
            'fields': (
                'trigger_type',
                'condition_operator',
                'condition_value',
            )
        }),
        (_('Filters'), {
            'fields': (
                'incident_types',
                'severity_levels',
                'camera_ids',
                'location_ids',
            ),
            'description': _('Leave empty to apply to all'),
            'classes': ('collapse',)
        }),
        (_('Time Restrictions'), {
            'fields': (
                'start_time',
                'end_time',
                'days_of_week',
            ),
            'classes': ('collapse',)
        }),
        (_('Action Configuration'), {
            'fields': (
                'channels',
                'message_template',
                'email_template',
            )
        }),
        (_('Recipients'), {
            'fields': (
                'recipient_roles',
                'specific_recipients',
            )
        }),
        (_('Rate Limiting'), {
            'fields': (
                'cooldown_minutes',
                'max_alerts_per_day',
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Readonly fields
    readonly_fields = ('created_at', 'updated_at')
    
    # Filter horizontal for many-to-many
    filter_horizontal = ('specific_recipients',)
    
    # Custom methods for list display
    def trigger_type_badge(self, obj):
        """Display trigger type as badge."""
        colors = {
            'incident_severity': 'blue',
            'incident_type': 'purple',
            'camera_status': 'orange',
            'time_schedule': 'green',
        }
        color = colors.get(obj.trigger_type, 'gray')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            obj.get_trigger_type_display()
        )
    trigger_type_badge.short_description = _('Trigger')
    
    def is_active_badge(self, obj):
        """Display active status as badge."""
        if obj.is_active:
            return format_html(
                '<span class="badge" style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px;">Active</span>'
            )
        else:
            return format_html(
                '<span class="badge" style="background-color: gray; color: white; padding: 2px 6px; border-radius: 3px;">Inactive</span>'
            )
    is_active_badge.short_description = _('Status')
    
    def priority_badge(self, obj):
        """Display priority as badge."""
        colors = {
            1: 'green',    # Low
            2: 'blue',     # Medium
            3: 'orange',   # High
            4: 'red',      # Critical
        }
        color = colors.get(obj.priority, 'gray')
        priority_text = dict(obj._meta.get_field('priority').choices).get(obj.priority, 'Unknown')
        return format_html(
            '<span class="badge" style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            priority_text
        )
    priority_badge.short_description = _('Priority')
    
    def recipients_count(self, obj):
        """Display count of recipients."""
        count = obj.get_recipients().count()
        url = reverse('admin:alerts_alertrule_preview', args=[obj.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            f'{count} recipient(s)'
        )
    recipients_count.short_description = _('Recipients')
    
    def channels_list(self, obj):
        """Display channels as badges."""
        badges = []
        for channel in obj.channels:
            color = 'blue' if channel == 'email' else 'purple'
            text = 'Email' if channel == 'email' else 'In-App'
            badges.append(
                f'<span class="badge" style="background-color: {color}; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 2px;">{text}</span>'
            )
        return format_html(' '.join(badges))
    channels_list.short_description = _('Channels')
    
    def action_buttons(self, obj):  # Renamed from 'actions'
        """Display action buttons."""
        buttons = []
        
        # Toggle active
        toggle_url = reverse('admin:alerts_alertrule_toggle', args=[obj.id])
        toggle_text = 'Deactivate' if obj.is_active else 'Activate'
        toggle_color = 'orange' if obj.is_active else 'green'
        
        buttons.append(
            f'<a href="{toggle_url}" class="button" style="background-color: {toggle_color}; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none;" title="{toggle_text}">⏻</a>'
        )
        
        # Preview
        preview_url = reverse('admin:alerts_alertrule_preview', args=[obj.id])
        buttons.append(
            f'<a href="{preview_url}" class="button" style="background-color: blue; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none;" title="Preview">👁</a>'
        )
        
        return format_html(' '.join(buttons))
    action_buttons.short_description = _('Actions')
    
    # Custom URLs
    def get_urls(self):
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:rule_id>/preview/',
                self.admin_site.admin_view(self.preview_view),
                name='alerts_alertrule_preview',
            ),
            path(
                '<int:rule_id>/toggle/',
                self.admin_site.admin_view(self.toggle_view),
                name='alerts_alertrule_toggle',
            ),
        ]
        return custom_urls + urls
    
    def preview_view(self, request, rule_id):
        """Preview rule recipients and settings."""
        from django.shortcuts import render, get_object_or_404
        
        rule = get_object_or_404(AlertRule, id=rule_id)
        recipients = rule.get_recipients()
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Preview: {rule.name}',
            'rule': rule,
            'recipients': recipients,
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/alerts/alertrule_preview.html', context)
    
    def toggle_view(self, request, rule_id):
        """Toggle rule active status."""
        from django.shortcuts import redirect, get_object_or_404
        
        rule = get_object_or_404(AlertRule, id=rule_id)
        rule.is_active = not rule.is_active
        rule.save()
        
        status = "activated" if rule.is_active else "deactivated"
        self.message_user(request, f'Alert rule "{rule.name}" {status}.')
        
        return redirect('admin:alerts_alertrule_changelist')

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for NotificationPreference model."""
    
    # List display
    list_display = (
        'user_link',
        'email_enabled_badge',
        'in_app_enabled_badge',
        'receive_digest_badge',
        'quiet_hours',
        'severity_preferences_display',
        'updated_at',
    )
    
    list_display_links = ('user_link',)
    
    # Search
    search_fields = (
        'user__email',
        'user__first_name',
        'user__last_name',
    )
    
    # Filters
    list_filter = (
        'email_enabled',
        'in_app_enabled',
        'receive_digest',
    )
    
    # Fieldsets for detail view
    fieldsets = (
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Channel Preferences'), {
            'fields': (
                'email_enabled',
                'in_app_enabled',
            )
        }),
        (_('Content Preferences'), {
            'fields': (
                'severity_preferences',
                'incident_type_preferences',
            )
        }),
        (_('Quiet Hours'), {
            'fields': (
                'quiet_hours_start',
                'quiet_hours_end',
            ),
            'description': _('Notifications will be suppressed during these hours'),
            'classes': ('collapse',)
        }),
        (_('Digest Options'), {
            'fields': (
                'receive_digest',
                'digest_time',
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Readonly fields
    readonly_fields = (
        'created_at',
        'updated_at',
    )
    
    # Custom methods
    def user_link(self, obj):
        """Display user as link."""
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.user.get_full_name() or obj.user.email
            )
        return '-'
    user_link.short_description = _('User')
    
    def email_enabled_badge(self, obj):
        """Display email enabled status."""
        if obj.email_enabled:
            return format_html(
                '<span class="badge" style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px;">✓ Email</span>'
            )
        else:
            return format_html(
                '<span class="badge" style="background-color: red; color: white; padding: 2px 6px; border-radius: 3px;">✗ Email</span>'
            )
    email_enabled_badge.short_description = _('Email')
    
    def in_app_enabled_badge(self, obj):
        """Display in-app enabled status."""
        if obj.in_app_enabled:
            return format_html(
                '<span class="badge" style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px;">✓ In-App</span>'
            )
        else:
            return format_html(
                '<span class="badge" style="background-color: red; color: white; padding: 2px 6px; border-radius: 3px;">✗ In-App</span>'
            )
    in_app_enabled_badge.short_description = _('In-App')
    
    def receive_digest_badge(self, obj):
        """Display digest status."""
        if obj.receive_digest:
            return format_html(
                '<span class="badge" style="background-color: blue; color: white; padding: 2px 6px; border-radius: 3px;">✓ Digest</span>'
            )
        else:
            return format_html(
                '<span class="badge" style="background-color: gray; color: white; padding: 2px 6px; border-radius: 3px;">✗ Digest</span>'
            )
    receive_digest_badge.short_description = _('Digest')
    
    def quiet_hours(self, obj):
        """Display quiet hours."""
        if obj.quiet_hours_start and obj.quiet_hours_end:
            return f"{obj.quiet_hours_start.strftime('%H:%M')} - {obj.quiet_hours_end.strftime('%H:%M')}"
        return '-'
    quiet_hours.short_description = _('Quiet Hours')
    
    def severity_preferences_display(self, obj):
        """Display severity preferences."""
        from incidents.models import Incident
        severity_map = dict(Incident.SeverityLevel.choices)
        
        badges = []
        for severity in obj.severity_preferences:
            color = {
                'low': 'green',
                'medium': 'blue',
                'high': 'orange',
                'critical': 'red',
            }.get(severity, 'gray')
            
            text = severity_map.get(severity, severity)
            badges.append(
                f'<span class="badge" style="background-color: {color}; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 2px;">{text}</span>'
            )
        
        if badges:
            return format_html(' '.join(badges))
        return '-'
    severity_preferences_display.short_description = _('Severity Preferences')