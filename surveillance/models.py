# smart_surveillance/surveillance/models.py
"""
Models for storing processing results from FastAPI server.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import json

class ImageProcessingResult(models.Model):
    """
    Stores results of image processing from FastAPI server.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='processed_images',
        null=True,
        blank=True
    )
    
    # File information
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)  # in bytes
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Processing information
    job_id = models.CharField(max_length=100, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Server information
    processing_server = models.CharField(max_length=200, default='fastapi')
    server_url = models.URLField(blank=True)
    
    # Results
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    detection_count = models.IntegerField(default=0)
    image_size = models.CharField(max_length=50, blank=True)  # "1920x1080"
    
    # Detection data (stored as JSON)
    detections = models.JSONField(default=list, blank=True)
    detection_summary = models.JSONField(default=dict, blank=True)
    
    # Processed image (if returned)
    processed_image_url = models.URLField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    
    # Metadata
    confidence_threshold = models.FloatField(default=0.5)
    detection_types = models.CharField(max_length=200, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        default='completed',
        choices=[
            ('submitted', 'Submitted'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ]
    )
    
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Image Processing Result'
        verbose_name_plural = 'Image Processing Results'
        indexes = [
            models.Index(fields=['user', 'submitted_at']),
            models.Index(fields=['job_id']),
            models.Index(fields=['status', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"Image: {self.original_filename} ({self.detection_count} detections)"
    
    @property
    def is_successful(self):
        return self.status == 'completed' and self.detection_count > 0
    
    @property
    def get_primary_detection_type(self):
        """Get the most common detection type."""
        if self.detection_summary:
            sorted_types = sorted(
                self.detection_summary.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_types[0][0] if sorted_types else 'none'
        return 'none'
    
    def get_detections_by_type(self, detection_type):
        """Get all detections of a specific type."""
        return [d for d in self.detections if d.get('label') == detection_type]

class VideoProcessingJob(models.Model):
    """
    Tracks video processing jobs submitted to FastAPI server.
    """
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        (0, 'Low'),
        (1, 'Normal'),
        (2, 'High'),
        (3, 'Urgent'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_jobs',
        null=True,
        blank=True
    )
    
    # Job identification
    job_id = models.CharField(max_length=100, unique=True, db_index=True)
    internal_id = models.CharField(max_length=50, blank=True)  # Our internal reference
    
    # File information
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)  # in bytes
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Processing parameters
    confidence_threshold = models.FloatField(default=0.5)
    frame_sample_rate = models.IntegerField(default=5)
    analyze_motion = models.BooleanField(default=True)
    summary_only = models.BooleanField(default=True)
    
    # Advanced features
    crowd_detection = models.BooleanField(default=False)
    min_people_count = models.IntegerField(default=3)
    vehicle_counting = models.BooleanField(default=False)
    counting_line_position = models.FloatField(default=0.5)  # 0-1
    
    # Server information
    processing_server = models.CharField(max_length=200, default='fastapi')
    server_url = models.URLField(blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    progress = models.FloatField(default=0.0)  # 0-100 percentage
    message = models.TextField(blank=True)
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=1)
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    
    # Results (stored when completed)
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    video_info = models.JSONField(null=True, blank=True)  # duration, resolution, etc.
    summary = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    
    # Links to incidents created from this job
    related_incidents = models.ManyToManyField(
        'incidents.Incident',
        related_name='video_processing_jobs',
        blank=True
    )
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Video Processing Job'
        verbose_name_plural = 'Video Processing Jobs'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['job_id']),
            models.Index(fields=['status', 'priority', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"Video Job: {self.original_filename} ({self.get_status_display()})"
    
    @property
    def is_active(self):
        return self.status in ['submitted', 'pending', 'processing']
    
    @property
    def is_completed(self):
        return self.status in ['completed', 'failed', 'cancelled']
    
    @property
    def duration_seconds(self):
        """Get duration in seconds from video info."""
        if self.video_info and 'duration' in self.video_info:
            return self.video_info['duration']
        return None
    
    @property
    def detection_counts(self):
        """Get detection counts from summary."""
        if self.summary and 'detection_counts' in self.summary:
            return self.summary['detection_counts']
        return {}
    
    def update_from_fastapi_status(self, status_data: dict):
        """
        Update job status from FastAPI status response.
        
        Args:
            status_data: Dictionary from FastAPI /jobs/{id}/status
        """
        self.status = status_data['status']
        self.progress = status_data.get('progress', 0.0)
        self.message = status_data.get('message', '')
        self.last_checked = timezone.now()
        
        # Update timestamps
        if status_data.get('started_at'):
            self.started_at = timezone.datetime.fromisoformat(
                status_data['started_at'].replace('Z', '+00:00')
            )
        
        if status_data.get('completed_at'):
            self.completed_at = timezone.datetime.fromisoformat(
                status_data['completed_at'].replace('Z', '+00:00')
            )
        
        # Store results if completed
        if status_data.get('result'):
            result = status_data['result']
            self.processing_time = result.get('processing_time')
            self.video_info = result.get('video_info')
            self.summary = result.get('summary')
        
        # Store error if failed
        if status_data.get('error'):
            self.error = status_data['error']
        
        self.save()
        
        # Create incidents if job completed successfully
        if self.status == 'completed' and self.summary:
            self.create_incidents_from_summary()
    
    def create_incidents_from_summary(self):
        """
        Create incidents based on video processing results.
        """
        from incidents.models import Incident
        from incidents.services import AlertService
        
        if not self.summary:
            return
        
        # Create incident for motion events
        motion_events = self.summary.get('motion_statistics', {}).get('total_events', 0)
        if motion_events > 0:
            incident = Incident.objects.create(
                incident_id=f"VID-{self.job_id[:8].upper()}",
                title=f"Video Analysis: {motion_events} motion events detected",
                description=f"Video analysis detected {motion_events} motion events in {self.original_filename}",
                incident_type='motion',
                severity='high' if motion_events > 10 else 'medium',
                status='detected',
                detected_at=self.completed_at or timezone.now(),
                assigned_to=self.user if self.user and self.user.can_acknowledge_incidents() else None,
                location_description=f"Video analysis: {self.original_filename}",
                confidence_score=0.8 if motion_events > 0 else 0.3,
                detection_metadata={
                    'video_job_id': self.job_id,
                    'motion_events': motion_events,
                    'video_duration': self.duration_seconds,
                    'detection_counts': self.detection_counts,
                }
            )
            self.related_incidents.add(incident)
            
            # Create alert for the incident
            if incident.camera:  # If camera is associated
                AlertService.create_incident_alert(incident, incident.camera)
        
        # Create incident for crowd detection
        crowd_stats = self.summary.get('crowd_statistics', {})
        if crowd_stats.get('active_crowds', 0) > 0:
            incident = Incident.objects.create(
                incident_id=f"CROWD-{self.job_id[:8].upper()}",
                title=f"Crowd detected: {crowd_stats.get('total_people_in_crowds')} people",
                description=f"Video analysis detected crowd activity in {self.original_filename}",
                incident_type='crowd',
                severity='high' if crowd_stats.get('total_people_in_crowds', 0) > 10 else 'medium',
                status='detected',
                detected_at=self.completed_at or timezone.now(),
                assigned_to=self.user if self.user and self.user.can_acknowledge_incidents() else None,
                location_description=f"Video analysis: {self.original_filename}",
                confidence_score=0.7,
                detection_metadata={
                    'video_job_id': self.job_id,
                    'crowd_statistics': crowd_stats,
                    'video_duration': self.duration_seconds,
                }
            )
            self.related_incidents.add(incident)