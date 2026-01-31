# smart_surveillance/alerts/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

class Alert(models.Model):
    """
    Alert model for notifications triggered by incidents from live cameras.
    """
    class AlertType(models.TextChoices):
        INCIDENT_DETECTED = 'incident_detected', _('Incident Detected')
        CAMERA_OFFLINE = 'camera_offline', _('Camera Offline')
        SYSTEM_ALERT = 'system_alert', _('System Alert')
        MAINTENANCE_REMINDER = 'maintenance_reminder', _('Maintenance Reminder')
    
    class AlertChannel(models.TextChoices):
        EMAIL = 'email', _('Email')
        IN_APP = 'in_app', _('In-App Notification')
        SMS = 'sms', _('SMS')  # Future implementation
        PUSH = 'push', _('Push Notification')  # Future implementation
    
    class AlertStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENT = 'sent', _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        FAILED = 'failed', _('Failed')
        READ = 'read', _('Read')  # For in-app notifications
    
    # Alert identification
    alert_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_('Alert ID'),
        help_text=_('Unique identifier for the alert')
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name=_('Title'),
        help_text=_('Alert title/subject')
    )
    
    message = models.TextField(
        verbose_name=_('Message'),
        help_text=_('Detailed alert message')
    )
    
    alert_type = models.CharField(
        max_length=50,
        choices=AlertType.choices,
        default=AlertType.INCIDENT_DETECTED,
        verbose_name=_('Alert Type')
    )
    
    # Source (only for camera incidents)
    incident = models.ForeignKey(
        'incidents.Incident',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts',
        verbose_name=_('Incident'),
        help_text=_('Incident that triggered this alert (for camera incidents only)')
    )
    
    camera = models.ForeignKey(
        'cameras.Camera',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='alerts',
        verbose_name=_('Camera'),
        help_text=_('Camera that triggered the alert')
    )
    
    # Recipients
    recipient = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='received_alerts',
        verbose_name=_('Recipient'),
        help_text=_('User who receives this alert')
    )
    
    # Delivery channels
    channels = models.JSONField(
        default=list,
        verbose_name=_('Channels'),
        help_text=_('List of delivery channels used: ["email", "in_app"]')
    )
    
    # Status tracking
    status = models.CharField(
        max_length=50,
        choices=AlertStatus.choices,
        default=AlertStatus.PENDING,
        verbose_name=_('Status')
    )
    
    delivery_status = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Delivery Status'),
        help_text=_('Status per channel: {"email": "sent", "in_app": "pending"}')
    )
    
    # Delivery timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Sent At'))
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Delivered At'))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Read At'))
    
    # For email alerts
    email_sent = models.BooleanField(default=False, verbose_name=_('Email Sent'))
    email_message_id = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Email Message ID'),
        help_text=_('ID from email service provider')
    )
    
    # For in-app alerts
    is_read = models.BooleanField(default=False, verbose_name=_('Is Read'))
    
    # Retry logic
    retry_count = models.IntegerField(default=0, verbose_name=_('Retry Count'))
    last_retry_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Last Retry At'))
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional alert data (severity, priority, etc.)')
    )
    
    class Meta:
        verbose_name = _('Alert')
        verbose_name_plural = _('Alerts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['alert_id']),
            models.Index(fields=['recipient', 'status', 'created_at']),
            models.Index(fields=['alert_type', 'created_at']),
            models.Index(fields=['camera', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.alert_id}: {self.title}"
    
    def save(self, *args, **kwargs):
        """Generate alert ID if not set."""
        if not self.alert_id:
            date_str = timezone.now().strftime('%Y%m%d')
            last_alert = Alert.objects.filter(
                alert_id__startswith=f'ALT-{date_str}'
            ).order_by('-alert_id').first()
            
            if last_alert:
                last_num = int(last_alert.alert_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.alert_id = f"ALT-{date_str}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def mark_as_sent(self, channel):
        """Mark alert as sent for a specific channel."""
        if not self.delivery_status:
            self.delivery_status = {}
        
        self.delivery_status[channel] = 'sent'
        
        # Update overall status if all channels sent
        if all(status == 'sent' for status in self.delivery_status.values()):
            self.status = self.AlertStatus.SENT
            self.sent_at = timezone.now()
        
        self.save()
    
    def mark_as_delivered(self, channel):
        """Mark alert as delivered for a specific channel."""
        if not self.delivery_status:
            self.delivery_status = {}
        
        self.delivery_status[channel] = 'delivered'
        
        # Update overall status if all channels delivered
        if all(status == 'delivered' for status in self.delivery_status.values()):
            self.status = self.AlertStatus.DELIVERED
            self.delivered_at = timezone.now()
        
        self.save()
    
    def mark_as_failed(self, channel, error_message=None):
        """Mark alert as failed for a specific channel."""
        if not self.delivery_status:
            self.delivery_status = {}
        
        self.delivery_status[channel] = 'failed'
        self.status = self.AlertStatus.FAILED
        
        if error_message:
            if 'errors' not in self.metadata:
                self.metadata['errors'] = []
            self.metadata['errors'].append({
                'channel': channel,
                'message': error_message,
                'timestamp': timezone.now().isoformat()
            })
        
        self.save()
    
    def mark_as_read(self):
        """Mark in-app alert as read."""
        if 'in_app' in self.channels:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = self.AlertStatus.READ
            self.save()
    
    def get_severity_color(self):
        """Get Bootstrap color based on metadata severity."""
        severity = self.metadata.get('severity', 'medium')
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark',
        }
        return colors.get(severity, 'warning')
    
    def can_retry(self):
        """Check if alert can be retried."""
        return (
            self.status in [self.AlertStatus.FAILED, self.AlertStatus.PENDING] and
            self.retry_count < 3  # Max 3 retries
        )
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1
        self.last_retry_at = timezone.now()
        self.save()

class AlertRule(models.Model):
    """
    Rules for when and how to send alerts for camera incidents.
    """
    class TriggerType(models.TextChoices):
        INCIDENT_SEVERITY = 'incident_severity', _('Incident Severity')
        INCIDENT_TYPE = 'incident_type', _('Incident Type')
        CAMERA_STATUS = 'camera_status', _('Camera Status')
        TIME_SCHEDULE = 'time_schedule', _('Time Schedule')
    
    class ConditionOperator(models.TextChoices):
        EQUALS = 'equals', _('Equals')
        GREATER_THAN = 'greater_than', _('Greater Than')
        LESS_THAN = 'less_than', _('Less Than')
        CONTAINS = 'contains', _('Contains')
        STARTS_WITH = 'starts_with', _('Starts With')
    
    # Rule configuration
    name = models.CharField(
        max_length=200,
        verbose_name=_('Rule Name'),
        help_text=_('Descriptive name for this alert rule')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('What this rule does')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this rule is active')
    )
    
    # Trigger configuration
    trigger_type = models.CharField(
        max_length=50,
        choices=TriggerType.choices,
        default=TriggerType.INCIDENT_SEVERITY,
        verbose_name=_('Trigger Type')
    )
    
    condition_operator = models.CharField(
        max_length=50,
        choices=ConditionOperator.choices,
        default=ConditionOperator.EQUALS,
        verbose_name=_('Condition Operator')
    )
    
    condition_value = models.CharField(
        max_length=200,
        verbose_name=_('Condition Value'),
        help_text=_('Value to compare against')
    )
    
    # Filtering (optional)
    incident_types = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Incident Types'),
        help_text=_('Specific incident types (empty for all)')
    )
    
    severity_levels = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Severity Levels'),
        help_text=_('Specific severity levels (empty for all)')
    )
    
    camera_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Camera IDs'),
        help_text=_('Specific cameras (empty for all)')
    )
    
    location_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Location IDs'),
        help_text=_('Specific locations (empty for all)')
    )
    
    # Time restrictions
    start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('Start Time'),
        help_text=_('Only trigger after this time (optional)')
    )
    
    end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('End Time'),
        help_text=_('Only trigger before this time (optional)')
    )
    
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Days of Week'),
        help_text=_('Days when rule applies (0=Sunday, 1=Monday, etc.)')
    )
    
    # Action configuration
    channels = models.JSONField(
        default=list,
        verbose_name=_('Channels'),
        help_text=_('Channels to use: ["email", "in_app"]')
    )
    
    message_template = models.TextField(
        verbose_name=_('Message Template'),
        help_text=_('Alert message template. Use {incident_id}, {camera_name}, etc.')
    )
    
    email_template = models.TextField(
        blank=True,
        verbose_name=_('Email Template'),
        help_text=_('HTML email template (optional, uses message_template if empty)')
    )
    
    # Recipients
    recipient_roles = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Recipient Roles'),
        help_text=_('User roles to receive alerts: ["security_manager", "security_guard"]')
    )
    
    specific_recipients = models.ManyToManyField(
        'accounts.User',
        blank=True,
        verbose_name=_('Specific Recipients'),
        help_text=_('Specific users to receive alerts (overrides roles)')
    )
    
    # Rate limiting
    cooldown_minutes = models.IntegerField(
        default=5,
        verbose_name=_('Cooldown Minutes'),
        help_text=_('Minutes between alerts for same trigger')
    )
    
    max_alerts_per_day = models.IntegerField(
        default=50,
        verbose_name=_('Max Alerts Per Day'),
        help_text=_('Maximum number of alerts per day (0 = unlimited)')
    )
    
    # Metadata
    priority = models.IntegerField(
        default=1,
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High'), (4, 'Critical')],
        verbose_name=_('Priority')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Alert Rule')
        verbose_name_plural = _('Alert Rules')
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return self.name
    
    def get_recipients(self):
        """Get all users who should receive alerts from this rule."""
        from accounts.models import User
        
        # If specific recipients are set, use them
        if self.specific_recipients.exists():
            return self.specific_recipients.all()
        
        # Otherwise, get users by role
        if self.recipient_roles:
            return User.objects.filter(role__in=self.recipient_roles, is_active=True)
        
        # Default: all security staff
        return User.objects.filter(
            role__in=['security_manager', 'security_guard'],
            is_active=True
        )
    
    def should_trigger(self, incident=None, camera=None):
        """Check if rule should trigger for given incident/camera."""
        from django.utils import timezone
        
        # Check if rule is active
        if not self.is_active:
            return False
        
        current_time = timezone.now()
        
        # Check time restrictions
        if self.start_time and self.end_time:
            current_time_only = current_time.time()
            if not (self.start_time <= current_time_only <= self.end_time):
                return False
        
        # Check days of week
        if self.days_of_week:
            current_day = current_time.weekday()  # Monday=0, Sunday=6
            if current_day not in self.days_of_week:
                return False
        
        # Check rate limiting
        if self.max_alerts_per_day > 0:
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            today_alerts = Alert.objects.filter(
                incident=incident,
                camera=camera,
                created_at__gte=today_start
            ).count()
            if today_alerts >= self.max_alerts_per_day:
                return False
        
        # Check cooldown
        if self.cooldown_minutes > 0 and incident:
            last_alert = Alert.objects.filter(
                incident=incident,
                camera=camera,
                created_at__gte=current_time - timezone.timedelta(minutes=self.cooldown_minutes)
            ).exists()
            if last_alert:
                return False
        
        # Check filters
        if incident:
            if self.incident_types and incident.incident_type not in self.incident_types:
                return False
            
            if self.severity_levels and incident.severity not in self.severity_levels:
                return False
        
        if camera and self.camera_ids and str(camera.id) not in self.camera_ids:
            return False
        
        if camera and self.location_ids and str(camera.location_id) not in self.location_ids:
            return False
        
        return True
    
    def format_message(self, incident=None, camera=None):
        """Format message using template."""
        context = {
            'incident_id': incident.incident_id if incident else 'N/A',
            'incident_title': incident.title if incident else 'N/A',
            'incident_type': incident.get_incident_type_display() if incident else 'N/A',
            'incident_severity': incident.get_severity_display() if incident else 'N/A',
            'camera_name': camera.name if camera else 'N/A',
            'camera_location': camera.location.name if camera and camera.location else 'N/A',
            'detected_at': incident.detected_at.strftime('%Y-%m-%d %H:%M:%S') if incident else timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        message = self.message_template
        for key, value in context.items():
            message = message.replace(f'{{{key}}}', str(value))
        
        return message

class NotificationPreference(models.Model):
    """
    User preferences for notifications.
    """
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences_obj',
        verbose_name=_('User')
    )
    
    # Channel preferences
    email_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Email Notifications')
    )
    
    in_app_enabled = models.BooleanField(
        default=True,
        verbose_name=_('In-App Notifications')
    )
    
    # Incident type preferences
    incident_type_preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Incident Type Preferences'),
        help_text=_('Which incident types to receive notifications for')
    )
    
    # Severity preferences
    severity_preferences = models.JSONField(
        default=['medium', 'high', 'critical'],
        verbose_name=_('Severity Preferences'),
        help_text=_('Which severity levels to receive notifications for')
    )
    
    # Quiet hours
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('Quiet Hours Start')
    )
    
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_('Quiet Hours End')
    )
    
    # Digest options
    receive_digest = models.BooleanField(
        default=False,
        verbose_name=_('Receive Daily Digest')
    )
    
    digest_time = models.TimeField(
        default='08:00',
        verbose_name=_('Digest Time')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Notification Preference')
        verbose_name_plural = _('Notification Preferences')
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
    
    def is_quiet_hours(self):
        """Check if currently in quiet hours."""
        from django.utils import timezone
        
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        current_time = timezone.now().time()
        return self.quiet_hours_start <= current_time <= self.quiet_hours_end
    
    def should_receive_alert(self, alert_type, severity):
        """Check if user should receive this type/severity of alert."""
        # Check quiet hours
        if self.is_quiet_hours():
            return False
        
        # Check severity preferences
        if severity not in self.severity_preferences:
            return False
        
        # Check incident type preferences
        if alert_type in self.incident_type_preferences:
            return self.incident_type_preferences[alert_type]
        
        return True  # Default to True if not specified