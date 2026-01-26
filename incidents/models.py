import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver   


                                                                        
class Incident(models.Model):
    """
    Incident model representing security events detected by the system.
    """
    
    class IncidentType(models.TextChoices):
        MOTION = 'motion', _('Motion Detected')
        PERSON = 'person', _('Person Detected')
        VEHICLE = 'vehicle', _('Vehicle Detected')
        FACE = 'face', _('Face Recognized')
        WEAPON = 'weapon', _('Weapon Detected')
        CROWD = 'crowd', _('Crowd Detected')
        LOITERING = 'loitering', _('Loitering Detected')
        TRESPASSING = 'trespassing', _('Trespassing Detected')
        ABANDONED_OBJECT = 'abandoned_object', _('Abandoned Object')
        VIOLENCE = 'violence', _('Violence Detected')
        UNAUTHORIZED_ACCESS = 'unauthorized_access', _('Unauthorized Access')
        THEFT = 'theft', _('Theft/Suspicious Activity')
        VANDALISM = 'vandalism', _('Vandalism')
        OTHER = 'other', _('Other')
    
    class SeverityLevel(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        CRITICAL = 'critical', _('Critical')
    
    class Status(models.TextChoices):
        DETECTED = 'detected', _('Detected')
        ACKNOWLEDGED = 'acknowledged', _('Acknowledged')
        INVESTIGATING = 'investigating', _('Under Investigation')
        RESOLVED = 'resolved', _('Resolved')
        FALSE_ALARM = 'false_alarm', _('False Alarm')
        ESCALATED = 'escalated', _('Escalated to Authorities')
    
    # Identification
    incident_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_('Incident ID'),
        help_text=_('Unique identifier for the incident')
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name=_('Title'),
        help_text=_('Brief description of the incident')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of what happened')
    )
    
    incident_type = models.CharField(
        max_length=50,
        choices=IncidentType.choices,
        default=IncidentType.MOTION,
        verbose_name=_('Incident Type')
    )
    
    severity = models.CharField(
        max_length=50,
        choices=SeverityLevel.choices,
        default=SeverityLevel.MEDIUM,
        verbose_name=_('Severity Level')
    )
    
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.DETECTED,
        verbose_name=_('Status')
    )
    
    # Source
    camera = models.ForeignKey(
        'cameras.Camera',
        on_delete=models.CASCADE,
        related_name='incidents',
        verbose_name=_('Camera'),
        help_text=_('Camera that detected the incident')
    )
    
    video_file = models.ForeignKey(
        'cameras.VideoFile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name=_('Source Video'),
        help_text=_('Video file that was being analyzed (if applicable)')
    )
    
    # Evidence
    evidence_image = models.ImageField(
        upload_to='incidents/evidence/images/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_('Evidence Image'),
        help_text=_('Snapshot captured during the incident')
    )
    
    evidence_video_clip = models.FileField(
        upload_to='incidents/evidence/videos/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_('Evidence Video Clip'),
        help_text=_('Short video clip of the incident')
    )
    
    thumbnail = models.ImageField(
        upload_to='incidents/thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_('Thumbnail'),
        help_text=_('Thumbnail image for quick preview')
    )
    
    # Location Details
    location_description = models.TextField(
        blank=True,
        verbose_name=_('Location Description'),
        help_text=_('Detailed location information')
    )
    
    gps_coordinates = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('GPS Coordinates'),
        help_text=_('Latitude,Longitude (e.g., 6.5244,3.3792)')
    )
    
    # Detection Metadata (from OpenCV/AI)
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        verbose_name=_('Confidence Score'),
        help_text=_('AI/ML model confidence score (0.0 to 1.0)')
    )
    
    detection_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Detection Metadata'),
        help_text=_('Raw detection data from AI model (bounding boxes, timestamps, etc.)')
    )
    
    # Assignment & Tracking
    assigned_to = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_incidents',
        verbose_name=_('Assigned To'),
        help_text=_('Security personnel assigned to investigate')
    )
    
    acknowledged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_incidents',
        verbose_name=_('Acknowledged By')
    )
    
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_incidents',
        verbose_name=_('Resolved By')
    )
    
    # Timestamps
    detected_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Detected At'),
        help_text=_('When the incident was first detected')
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Acknowledged At')
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Resolved At')
    )
    
    # Additional Metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Tags'),
        help_text=_('Keywords for categorization (e.g., ["night", "theft", "hostel"])')
    )
    
    is_false_positive = models.BooleanField(
        default=False,
        verbose_name=_('False Positive'),
        help_text=_('Whether this was a false alarm')
    )
    
    requires_police_report = models.BooleanField(
        default=False,
        verbose_name=_('Requires Police Report')
    )
    
    police_report_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Police Report Number')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Investigation Notes'),
        help_text=_('Notes from investigation or resolution')
    )
    
    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Incident')
        verbose_name_plural = _('Incidents')
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['incident_id']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['camera', 'detected_at']),
            models.Index(fields=['incident_type', 'detected_at']),
        ]
    
    def __str__(self):
        return f"{self.incident_id}: {self.title}"
    
    def save(self, *args, **kwargs):
        """Generate incident ID if not set."""
        if not self.incident_id:
            date_str = timezone.now().strftime('%Y%m%d')
            last_incident = Incident.objects.filter(
                incident_id__startswith=f'INC-{date_str}'
            ).order_by('-incident_id').first()
            
            if last_incident:
                last_num = int(last_incident.incident_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.incident_id = f"INC-{date_str}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def get_status_color(self):
        """Get Bootstrap color for incident status."""
        colors = {
            'detected': 'warning',
            'acknowledged': 'info',
            'investigating': 'primary',
            'resolved': 'success',
            'false_alarm': 'secondary',
            'escalated': 'danger',
        }
        return colors.get(self.status, 'secondary')
    
    def get_severity_color(self):
        """Get Bootstrap color for incident severity."""
        colors = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark',
        }
        return colors.get(self.severity, 'secondary')
    
    def get_response_time(self):
        """Calculate time between detection and acknowledgment."""
        if self.acknowledged_at:
            return self.acknowledged_at - self.detected_at
        return None
    
    def get_resolution_time(self):
        """Calculate time between detection and resolution."""
        if self.resolved_at:
            return self.resolved_at - self.detected_at
        return None
    
    def can_be_acknowledged(self):
        """Check if incident can be acknowledged."""
        return self.status == self.Status.DETECTED
    
    def can_be_resolved(self):
        """Check if incident can be resolved."""
        return self.status in [self.Status.DETECTED, self.Status.ACKNOWLEDGED, self.Status.INVESTIGATING]
    
    def acknowledge(self, user):
        """Acknowledge the incident."""
        if self.can_be_acknowledged():
            self.status = self.Status.ACKNOWLEDGED
            self.acknowledged_by = user
            self.acknowledged_at = timezone.now()
            self.save()
            return True
        return False
    
    def resolve(self, user, notes='', is_false_positive=False):
        """Resolve the incident."""
        if self.can_be_resolved():
            self.status = self.Status.RESOLVED
            self.resolved_by = user
            self.resolved_at = timezone.now()
            self.notes = notes
            self.is_false_positive = is_false_positive
            self.save()
            return True
        return False
    
    def escalate(self):
        """Escalate incident to authorities."""
        self.status = self.Status.ESCALATED
        self.requires_police_report = True
        self.save()
        return True
    
    def mark_as_false_alarm(self, user):
        """Mark incident as false alarm."""
        self.status = self.Status.FALSE_ALARM
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.is_false_positive = True
        self.save()
        return True

class IncidentComment(models.Model):
    """
    Comments and updates on incidents.
    """
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Incident')
    )
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        verbose_name=_('User')
    )
    
    comment = models.TextField(
        verbose_name=_('Comment'),
        help_text=_('Comment text')
    )
    
    attachment = models.FileField(
        upload_to='incidents/comments/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_('Attachment'),
        help_text=_('Optional file attachment')
    )
    
    is_internal = models.BooleanField(
        default=False,
        verbose_name=_('Internal Note'),
        help_text=_('Whether this is an internal note (not shown to all users)')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Incident Comment')
        verbose_name_plural = _('Incident Comments')
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user} on {self.incident.incident_id}"

class IncidentActionLog(models.Model):
    """
    Audit trail for all actions performed on incidents.
    """
    class ActionType(models.TextChoices):
        CREATED = 'created', _('Created')
        UPDATED = 'updated', _('Updated')
        ACKNOWLEDGED = 'acknowledged', _('Acknowledged')
        ASSIGNED = 'assigned', _('Assigned')
        RESOLVED = 'resolved', _('Resolved')
        ESCALATED = 'escalated', _('Escalated')
        COMMENT_ADDED = 'comment_added', _('Comment Added')
        EVIDENCE_ADDED = 'evidence_added', _('Evidence Added')
        STATUS_CHANGED = 'status_changed', _('Status Changed')
        SEVERITY_CHANGED = 'severity_changed', _('Severity Changed')
        FALSE_ALARM = 'false_alarm', _('Marked as False Alarm')
    
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='action_logs',
        verbose_name=_('Incident')
    )
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('User')
    )
    
    action = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        verbose_name=_('Action')
    )
    
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Details'),
        help_text=_('Additional action details in JSON format')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Incident Action Log')
        verbose_name_plural = _('Incident Action Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['incident', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} on {self.incident.incident_id} by {self.user}"

class Evidence(models.Model):
    """
    Additional evidence files for incidents.
    """
    class EvidenceType(models.TextChoices):
        IMAGE = 'image', _('Image')
        VIDEO = 'video', _('Video')
        AUDIO = 'audio', _('Audio')
        DOCUMENT = 'document', _('Document')
        OTHER = 'other', _('Other')
    
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='additional_evidence',
        verbose_name=_('Incident')
    )
    
    evidence_type = models.CharField(
        max_length=50,
        choices=EvidenceType.choices,
        default=EvidenceType.IMAGE,
        verbose_name=_('Evidence Type')
    )
    
    file = models.FileField(
        upload_to='incidents/additional_evidence/%Y/%m/%d/',
        verbose_name=_('File')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Description of this evidence')
    )
    
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        verbose_name=_('Uploaded By')
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Evidence')
        verbose_name_plural = _('Evidence')
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.get_evidence_type_display()} for {self.incident.incident_id}"
    
    def get_file_extension(self):
        """Get file extension."""
        import os
        return os.path.splitext(self.file.name)[1].lower()
    
    def is_image(self):
        """Check if file is an image."""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        return self.get_file_extension() in image_extensions
    
    def is_video(self):
        """Check if file is a video."""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
        return self.get_file_extension() in video_extensions

class IncidentStatistic(models.Model):
    """
    Daily aggregated statistics for incidents.
    """
    date = models.DateField(
        unique=True,
        verbose_name=_('Date')
    )
    
    # Counts by type
    total_incidents = models.IntegerField(default=0, verbose_name=_('Total Incidents'))
    motion_incidents = models.IntegerField(default=0, verbose_name=_('Motion Incidents'))
    person_incidents = models.IntegerField(default=0, verbose_name=_('Person Incidents'))
    vehicle_incidents = models.IntegerField(default=0, verbose_name=_('Vehicle Incidents'))
    trespassing_incidents = models.IntegerField(default=0, verbose_name=_('Trespassing Incidents'))
    
    # Counts by severity
    low_severity = models.IntegerField(default=0, verbose_name=_('Low Severity'))
    medium_severity = models.IntegerField(default=0, verbose_name=_('Medium Severity'))
    high_severity = models.IntegerField(default=0, verbose_name=_('High Severity'))
    critical_severity = models.IntegerField(default=0, verbose_name=_('Critical Severity'))
    
    # Counts by status
    detected_count = models.IntegerField(default=0, verbose_name=_('Detected'))
    acknowledged_count = models.IntegerField(default=0, verbose_name=_('Acknowledged'))
    resolved_count = models.IntegerField(default=0, verbose_name=_('Resolved'))
    false_alarm_count = models.IntegerField(default=0, verbose_name=_('False Alarms'))
    
    # Performance metrics
    avg_response_time = models.FloatField(default=0.0, verbose_name=_('Average Response Time (minutes)'))
    avg_resolution_time = models.FloatField(default=0.0, verbose_name=_('Average Resolution Time (minutes)'))
    false_positive_rate = models.FloatField(default=0.0, verbose_name=_('False Positive Rate (%)'))
    
    # Camera metrics
    cameras_with_incidents = models.IntegerField(default=0, verbose_name=_('Cameras with Incidents'))
    most_active_camera = models.CharField(max_length=200, blank=True, verbose_name=_('Most Active Camera'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Incident Statistic')
        verbose_name_plural = _('Incident Statistics')
        ordering = ['-date']
    
    def __str__(self):
        return f"Incident Stats for {self.date}"
    
    def get_false_positive_percentage(self):
        """Calculate false positive percentage."""
        if self.total_incidents == 0:
            return 0
        return round((self.false_alarm_count / self.total_incidents) * 100, 2)
    
    
@receiver(post_save, sender='incidents.Incident')
def create_alert_for_camera_incident(sender, instance, created, **kwargs):
    """
    Signal handler to create alerts when incidents are created from cameras.
    """
    if created and instance.camera and not instance.video_file:
        # This is a camera incident (not from video upload)
        # Import here to avoid circular imports
        try:
            from alerts.services import AlertService
            AlertService.create_incident_alert(instance, instance.camera)
        except Exception as e:
            # Log error but don't crash the app
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create alert for incident {instance.incident_id}: {str(e)}")