from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

from django.db.models.signals import post_save
from django.dispatch import receiver

class Camera(models.Model):
    """
    Camera model representing surveillance cameras in the system.
    """
    
    class CameraType(models.TextChoices):
        IP = 'ip', _('IP Camera')
        CCTV = 'cctv', _('CCTV Camera')
        USB = 'usb', _('USB Webcam')
        THERMAL = 'thermal', _('Thermal Camera')
        PTZ = 'ptz', _('PTZ Camera')
        DOME = 'dome', _('Dome Camera')
        BULLET = 'bullet', _('Bullet Camera')
    
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        MAINTENANCE = 'maintenance', _('Under Maintenance')
        OFFLINE = 'offline', _('Offline')
        ERROR = 'error', _('Error')
    
    class ConnectionProtocol(models.TextChoices):
        RTSP = 'rtsp', _('RTSP')
        HTTP = 'http', _('HTTP')
        HTTPS = 'https', _('HTTPS')
        ONVIF = 'onvif', _('ONVIF')
        RSTP = 'rstp', _('RSTP')
    
    # Basic Information
    name = models.CharField(
        max_length=200,
        verbose_name=_('Camera Name'),
        help_text=_('Descriptive name for the camera')
    )
    
    camera_id = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4,
        verbose_name=_('Camera ID'),
        help_text=_('Unique identifier for the camera')
    )
    
    location = models.ForeignKey(
        'core.Location',
        on_delete=models.CASCADE,
        related_name='cameras',
        verbose_name=_('Location'),
        help_text=_('Physical location of the camera')
    )
    
    camera_type = models.CharField(
        max_length=50,
        choices=CameraType.choices,
        default=CameraType.IP,
        verbose_name=_('Camera Type')
    )
    
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.INACTIVE,
        verbose_name=_('Status')
    )
    
    # Connection Details
    connection_protocol = models.CharField(
        max_length=50,
        choices=ConnectionProtocol.choices,
        default=ConnectionProtocol.RTSP,
        verbose_name=_('Connection Protocol')
    )
    
    stream_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name=_('Stream URL'),
        help_text=_('RTSP/HTTP stream URL (e.g., rtsp://username:password@ip:port/path)')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address'),
        help_text=_('Camera IP address if static')
    )
    
    port = models.IntegerField(
        default=554,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        verbose_name=_('Port'),
        help_text=_('Port number for camera connection')
    )
    
    username = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Username'),
        help_text=_('Authentication username')
    )
    
    password = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Password'),
        help_text=_('Authentication password (stored encrypted)')
    )
    
    # Technical Specifications
    resolution = models.CharField(
        max_length=20,
        default='1920x1080',
        verbose_name=_('Resolution'),
        help_text=_('Video resolution (e.g., 1920x1080, 1280x720)')
    )
    
    fps = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        verbose_name=_('Frames Per Second'),
        help_text=_('Frames per second for video capture')
    )
    
    has_night_vision = models.BooleanField(
        default=False,
        verbose_name=_('Night Vision')
    )
    
    has_audio = models.BooleanField(
        default=False,
        verbose_name=_('Audio Support')
    )
    
    field_of_view = models.IntegerField(
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(360)],
        verbose_name=_('Field of View'),
        help_text=_('Camera field of view in degrees')
    )
    
    # Operational Settings
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether camera is currently active in the system')
    )
    
    motion_detection_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Motion Detection Enabled')
    )
    
    recording_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Recording Enabled')
    )
    
    detection_zones = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Detection Zones'),
        help_text=_('JSON array of coordinates for motion detection zones')
    )
    
    # Maintenance Information
    last_maintenance = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Last Maintenance')
    )
    
    next_maintenance = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Next Maintenance')
    )
    
    warranty_expiry = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Warranty Expiry')
    )
    
    # Metadata
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Manufacturer')
    )
    
    model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Model')
    )
    
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Serial Number')
    )
    
    installation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Installation Date')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes or comments')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_ping = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Ping'),
        help_text=_('Last successful connection to camera')
    )
    
    class Meta:
        verbose_name = _('Camera')
        verbose_name_plural = _('Cameras')
        ordering = ['name', 'location']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['location', 'camera_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.camera_id}) - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        """Custom save method to handle camera_id generation."""
        if not self.camera_id:
            self.camera_id = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)
    
    def get_stream_url_with_auth(self):
        """Get stream URL with authentication if provided."""
        if not self.stream_url:
            return None
        
        if self.username and self.password:
            # Insert credentials into stream URL
            import re
            protocol = self.stream_url.split('://')[0]
            url_without_protocol = self.stream_url.split('://')[1]
            return f"{protocol}://{self.username}:{self.password}@{url_without_protocol}"
        
        return self.stream_url
    
    def get_status_color(self):
        """Get Bootstrap color for camera status."""
        status_colors = {
            'active': 'success',
            'inactive': 'secondary',
            'maintenance': 'warning',
            'offline': 'danger',
            'error': 'dark',
        }
        return status_colors.get(self.status, 'secondary')
    
    def is_online(self):
        """Check if camera is online (active and not offline/error)."""
        return self.status in [self.Status.ACTIVE, self.Status.MAINTENANCE] and self.is_active

class CameraGroup(models.Model):
    """
    Group cameras for easier management (e.g., Building A, Perimeter, etc.)
    """
    name = models.CharField(max_length=200, verbose_name=_('Group Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    cameras = models.ManyToManyField(
        Camera,
        related_name='groups',
        verbose_name=_('Cameras'),
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Camera Group')
        verbose_name_plural = _('Camera Groups')
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_active_cameras(self):
        """Get active cameras in this group."""
        return self.cameras.filter(is_active=True, status=Camera.Status.ACTIVE)
    
    def get_offline_cameras(self):
        """Get offline cameras in this group."""
        return self.cameras.filter(status__in=[Camera.Status.OFFLINE, Camera.Status.ERROR])

class CameraHealthLog(models.Model):
    """
    Log camera health and status over time.
    """
    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name='health_logs',
        verbose_name=_('Camera')
    )
    
    status = models.CharField(
        max_length=50,
        choices=Camera.Status.choices,
        verbose_name=_('Status')
    )
    
    uptime_percentage = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Uptime Percentage')
    )
    
    packet_loss = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Packet Loss (%)')
    )
    
    bandwidth_usage = models.FloatField(
        default=0.0,
        verbose_name=_('Bandwidth Usage (Mbps)')
    )
    
    response_time = models.FloatField(
        default=0.0,
        verbose_name=_('Response Time (ms)')
    )
    
    storage_usage = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Storage Usage (%)')
    )
    
    errors = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Errors'),
        help_text=_('List of errors encountered')
    )
    
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Recorded At')
    )
    
    class Meta:
        verbose_name = _('Camera Health Log')
        verbose_name_plural = _('Camera Health Logs')
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['camera', 'recorded_at']),
        ]
    
    def __str__(self):
        return f"{self.camera.name} - {self.status} at {self.recorded_at}"
    
    def is_healthy(self):
        """Check if camera health is acceptable."""
        return (
            self.uptime_percentage >= 95.0 and
            self.packet_loss <= 5.0 and
            self.response_time <= 1000.0  # 1 second
        )
        
        
# Add to cameras/models.py after CameraHealthLog

class VideoFile(models.Model):
    """
    Model for uploaded video files for processing and analysis.
    """
    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
    
    # Upload information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Video Title'),
        help_text=_('Descriptive name for the video')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('What this video contains or what to analyze')
    )
    
    video_file = models.FileField(
        upload_to='videos/uploads/%Y/%m/%d/',
        verbose_name=_('Video File'),
        help_text=_('Upload MP4, AVI, MOV, or MKV files (max 500MB)')
    )
    
    # Processing information
    processing_status = models.CharField(
        max_length=50,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        verbose_name=_('Processing Status')
    )
    
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='uploaded_videos',
        verbose_name=_('Uploaded By')
    )
    
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Uploaded At')
    )
    
    # Analysis results (after OpenCV processing)
    processing_started = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processing Started')
    )
    
    processing_completed = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processing Completed')
    )
    
    total_frames = models.IntegerField(
        default=0,
        verbose_name=_('Total Frames')
    )
    
    processed_frames = models.IntegerField(
        default=0,
        verbose_name=_('Processed Frames')
    )
    
    detection_count = models.IntegerField(
        default=0,
        verbose_name=_('Detections Found')
    )
    
    # Results storage
    results_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Analysis Results'),
        help_text=_('JSON containing detection data, timestamps, etc.')
    )
    
    output_video_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Output Video Path'),
        help_text=_('Path to processed video with annotations')
    )
    
    # Metadata
    duration = models.FloatField(
        default=0.0,
        verbose_name=_('Duration (seconds)')
    )
    
    resolution = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Resolution')
    )
    
    fps = models.FloatField(
        default=0.0,
        verbose_name=_('Frames Per Second')
    )
    
    file_size = models.BigIntegerField(
        default=0,
        verbose_name=_('File Size (bytes)')
    )
    
    class Meta:
        verbose_name = _('Video File')
        verbose_name_plural = _('Video Files')
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_processing_status_display()})"
    
    def get_file_size_mb(self):
        """Get file size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2)
    
    def get_progress_percentage(self):
        """Get processing progress percentage."""
        if self.total_frames == 0:
            return 0
        return round((self.processed_frames / self.total_frames) * 100, 1)
    
    def get_processing_time(self):
        """Get processing time in seconds."""
        if self.processing_started and self.processing_completed:
            return (self.processing_completed - self.processing_started).total_seconds()
        return None
    
    
@receiver(post_save, sender='cameras.Camera')
def create_alert_for_camera_status(sender, instance, **kwargs):
    """
    Signal handler to create alerts when camera status changes.
    """
    # Check if status changed
    if instance.pk:
        try:
            old_instance = Camera.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                # Import here to avoid circular imports
                from alerts.services import AlertService
                AlertService.create_camera_status_alert(
                    camera=instance,
                    status=instance.status,
                    reason=f"Status changed from {old_instance.status} to {instance.status}"
                )
        except Camera.DoesNotExist:
            pass  # New camera, not a status change