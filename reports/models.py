# smart_surveillance/reports/models.py
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid

class IncidentCategory(models.Model):
    """Predefined categories for incidents."""
    name = models.CharField(max_length=100, verbose_name=_('Category Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    icon = models.CharField(max_length=50, blank=True, verbose_name=_('Icon Class'))
    
    class Meta:
        verbose_name = _('Incident Category')
        verbose_name_plural = _('Incident Categories')
        ordering = ['name']
    
    def __str__(self):
        return self.name

class IncidentLocation(models.Model):
    """Predefined locations on campus."""
    name = models.CharField(max_length=100, verbose_name=_('Location Name'))
    building = models.CharField(max_length=100, blank=True, verbose_name=_('Building'))
    campus_zone = models.CharField(max_length=50, blank=True, verbose_name=_('Campus Zone'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    class Meta:
        verbose_name = _('Incident Location')
        verbose_name_plural = _('Incident Locations')
        ordering = ['building', 'name']
    
    def __str__(self):
        return f"{self.building} - {self.name}" if self.building else self.name

class IncidentReport(models.Model):
    """Main model for incident reports submitted by users."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending Review')
        PROCESSING = 'processing', _('Processing')
        RESOLVED = 'resolved', _('Resolved')
        CLOSED = 'closed', _('Closed')
    
    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        CRITICAL = 'critical', _('Critical')
    
    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name=_('Incident Title'))
    description = models.TextField(verbose_name=_('Detailed Description'))
    
    # Foreign keys
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_incidents',
        verbose_name=_('Reporter')
    )
    category = models.ForeignKey(
        IncidentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Category')
    )
    location = models.ForeignKey(
        IncidentLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Location')
    )
    
    # Status and tracking
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    priority = models.CharField(
        max_length=50,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name=_('Priority')
    )
    
    # Privacy options
    anonymous = models.BooleanField(
        default=False,
        verbose_name=_('Report Anonymously'),
        help_text=_('Hide your identity from other users')
    )
    
    # Timestamps
    incident_date = models.DateTimeField(
        verbose_name=_('Date/Time of Incident'),
        help_text=_('When did the incident occur?')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Incident Report')
        verbose_name_plural = _('Incident Reports')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reporter', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['priority', 'created_at']),
        ]
        permissions = [
            ("view_all_reports", "Can view all incident reports"),
            ("change_report_status", "Can change report status"),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('reports:detail', args=[str(self.id)])
    
    @property
    def image_count(self):
        return self.images.count()
    
    @property
    def display_reporter(self):
        """Display reporter name or 'Anonymous'."""
        if self.anonymous:
            return _("Anonymous")
        return self.reporter.get_full_name() or self.reporter.email

class IncidentImage(models.Model):
    """Images attached to incident reports."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        IncidentReport,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Incident Report')
    )
    image = models.ImageField(
        upload_to='incident_images/%Y/%m/%d/',
        verbose_name=_('Image')
    )
    
    # AI Analysis results
    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('AI Analysis Results'),
        help_text=_('Results from FastAPI image analysis')
    )
    faces_blurred = models.BooleanField(
        default=False,
        verbose_name=_('Faces Blurred')
    )
    analysis_requested = models.BooleanField(
        default=False,
        verbose_name=_('AI Analysis Requested')
    )
    analyzed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    uploaded_at = models.DateTimeField(auto_now_add=True)
    caption = models.CharField(max_length=255, blank=True, verbose_name=_('Caption'))
    
    class Meta:
        verbose_name = _('Incident Image')
        verbose_name_plural = _('Incident Images')
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Image for {self.incident.title}"
    
    @property
    def has_analysis(self):
        return bool(self.ai_analysis)

class IncidentUpdate(models.Model):
    """Updates/status changes for incident reports."""
    
    incident = models.ForeignKey(
        IncidentReport,
        on_delete=models.CASCADE,
        related_name='updates',
        verbose_name=_('Incident Report')
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Updated by')
    )
    
    # Update content
    status_change = models.CharField(
        max_length=50,
        choices=IncidentReport.Status.choices,
        blank=True,
        verbose_name=_('Status Change')
    )
    notes = models.TextField(verbose_name=_('Update Notes'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Incident Update')
        verbose_name_plural = _('Incident Updates')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Update for {self.incident.title} at {self.created_at}"