"""
Models for storing processing results from FastAPI server with base64 support.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import json
import base64
from io import BytesIO
from django.core.files.base import ContentFile
import uuid
import logging

logger = logging.getLogger(__name__)

class ImageProcessingResult(models.Model):
    """
    Stores results of image processing from FastAPI server with base64 support.
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
    
    # Base64 processed image storage
    processed_image_base64 = models.TextField(
        blank=True,
        verbose_name='Processed Image Base64',
        help_text='Base64 encoded processed image with bounding boxes'
    )
    
    processed_image_file = models.ImageField(
        upload_to='processed_images/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name='Processed Image File',
        help_text='Saved processed image file (converted from base64)'
    )
    
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
    
    # Link to MediaUpload (if applicable)
    media_upload = models.ForeignKey(
        'cameras.MediaUpload',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='image_processing_results',
        verbose_name='Media Upload'
    )
    
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
    
    def has_base64_image(self):
        """Check if base64 processed image is available."""
        return bool(self.processed_image_base64)
    
    def has_processed_image_file(self):
        """Check if processed image file is available."""
        return bool(self.processed_image_file)
    
    def save_base64_to_file(self):
        """
        Save base64 image to processed_image_file field.
        
        Returns:
            bool: True if saved successfully
        """
        if not self.processed_image_base64:
            return False
        
        try:
            # Clean base64 string
            base64_str = self.processed_image_base64
            if 'base64,' in base64_str:
                base64_str = base64_str.split('base64,')[1]
            
            # Decode base64
            file_data = base64.b64decode(base64_str)
            
            # Create file name
            filename = f"processed_{self.job_id}_{uuid.uuid4().hex[:8]}.jpg"
            
            # Save to processed_image_file field
            self.processed_image_file.save(
                filename,
                ContentFile(file_data),
                save=False
            )
            
            # Clear base64 field to save database space
            self.processed_image_base64 = ''
            
            self.save()
            logger.info(f"Saved base64 image to file: {self.processed_image_file.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving base64 to file: {str(e)}")
            return False
    
    def get_image_data_url(self):
        """
        Get data URL for processed image.
        
        Returns:
            str: Data URL for embedding in HTML
        """
        if self.processed_image_base64:
            # Create data URL from base64
            if 'base64,' in self.processed_image_base64:
                return self.processed_image_base64
            else:
                return f"data:image/jpeg;base64,{self.processed_image_base64}"
        elif self.processed_image_file:
            # Return file URL
            return self.processed_image_file.url
        
        return None

class VideoProcessingJob(models.Model):
    """
    Tracks video processing jobs submitted to FastAPI server with base64 support.
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
    
    # Base64 key frames storage
    key_frames_base64 = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Key Frames Base64',
        help_text='List of base64 encoded key frames from video analysis'
    )
    
    key_frames_files = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Key Frames Files',
        help_text='List of saved key frame file paths'
    )
    
    # Link to MediaUpload (if applicable)
    media_upload = models.ForeignKey(
        'cameras.MediaUpload',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_processing_jobs',
        verbose_name='Media Upload'
    )
    
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
    
    @property
    def has_key_frames(self):
        """Check if key frames are available."""
        return bool(self.key_frames_base64) or bool(self.key_frames_files)
    
    @property
    def key_frames_count(self):
        """Get number of key frames."""
        if self.key_frames_base64 and isinstance(self.key_frames_base64, list):
            return len(self.key_frames_base64)
        elif self.key_frames_files and isinstance(self.key_frames_files, list):
            return len(self.key_frames_files)
        return 0
    
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
            
            # Store base64 key frames if available
            if 'key_frames_base64' in result:
                self.key_frames_base64 = result['key_frames_base64']
        
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
                from alerts.services import AlertService
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
    
    def save_key_frames_to_files(self):
        """
        Save base64 key frames to files and update key_frames_files.
        
        Returns:
            list: List of saved file paths
        """
        if not self.key_frames_base64 or not isinstance(self.key_frames_base64, list):
            return []
        
        saved_files = []
        
        try:
            for i, base64_img in enumerate(self.key_frames_base64):
                if not base64_img:
                    continue
                    
                # Clean base64 string
                if 'base64,' in base64_img:
                    base64_img = base64_img.split('base64,')[1]
                
                # Decode and save
                file_data = base64.b64decode(base64_img)
                filename = f"keyframe_{self.job_id}_{i}_{uuid.uuid4().hex[:8]}.jpg"
                
                # Save to storage
                from django.core.files.storage import default_storage
                file_path = default_storage.save(
                    f'processed/key_frames/{filename}',
                    ContentFile(file_data)
                )
                saved_files.append(file_path)
            
            # Update key_frames_files
            self.key_frames_files = saved_files
            self.save()
            
            logger.info(f"Saved {len(saved_files)} key frames to files for job {self.job_id}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving key frames to files: {str(e)}")
            return []
    
    def get_key_frame_data_urls(self, limit: int = None):
        """
        Get data URLs for key frames.
        
        Args:
            limit: Maximum number of key frames to return
        
        Returns:
            list: List of data URLs
        """
        data_urls = []
        
        # First try base64
        if self.key_frames_base64 and isinstance(self.key_frames_base64, list):
            frames = self.key_frames_base64[:limit] if limit else self.key_frames_base64
            for base64_img in frames:
                if base64_img:
                    if 'base64,' in base64_img:
                        data_urls.append(base64_img)
                    else:
                        data_urls.append(f"data:image/jpeg;base64,{base64_img}")
        
        # If no base64 or we need more, try files
        elif self.key_frames_files and isinstance(self.key_frames_files, list):
            # For files, we'd return URLs, not data URLs
            # This would require a different approach
            pass
        
        return data_urls
    
    def get_summary_statistics(self):
        """
        Get formatted summary statistics.
        
        Returns:
            dict: Formatted statistics
        """
        stats = {
            'detections': self.detection_counts,
            'duration': self.duration_seconds,
            'key_frames': self.key_frames_count,
            'processing_time': self.processing_time,
        }
        
        if self.summary:
            stats.update({
                'motion_events': self.summary.get('motion_statistics', {}).get('total_events', 0),
                'crowd_count': self.summary.get('crowd_statistics', {}).get('active_crowds', 0),
                'people_count': self.summary.get('crowd_statistics', {}).get('total_people_in_crowds', 0),
            })
        
        return stats

class ProcessingStatistics(models.Model):
    """
    Aggregated statistics for FastAPI processing.
    """
    date = models.DateField(unique=True, verbose_name='Date')
    
    # Counts
    total_requests = models.IntegerField(default=0, verbose_name='Total Requests')
    image_requests = models.IntegerField(default=0, verbose_name='Image Requests')
    video_requests = models.IntegerField(default=0, verbose_name='Video Requests')
    
    # Success rates
    successful_requests = models.IntegerField(default=0, verbose_name='Successful Requests')
    failed_requests = models.IntegerField(default=0, verbose_name='Failed Requests')
    
    # Processing times
    avg_image_processing_time = models.FloatField(default=0.0, verbose_name='Avg Image Processing Time (s)')
    avg_video_processing_time = models.FloatField(default=0.0, verbose_name='Avg Video Processing Time (s)')
    
    # Detection statistics
    total_detections = models.IntegerField(default=0, verbose_name='Total Detections')
    person_detections = models.IntegerField(default=0, verbose_name='Person Detections')
    vehicle_detections = models.IntegerField(default=0, verbose_name='Vehicle Detections')
    
    # Base64 statistics
    base64_images_processed = models.IntegerField(default=0, verbose_name='Base64 Images Processed')
    base64_key_frames_processed = models.IntegerField(default=0, verbose_name='Base64 Key Frames Processed')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Processing Statistics'
        verbose_name_plural = 'Processing Statistics'
        ordering = ['-date']
    
    def __str__(self):
        return f"Processing Stats for {self.date}"
    
    @property
    def success_rate(self):
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def avg_processing_time(self):
        """Calculate average processing time."""
        if self.total_requests == 0:
            return 0
        total_time = (self.avg_image_processing_time * self.image_requests + 
                     self.avg_video_processing_time * self.video_requests)
        return total_time / self.total_requests
    
    @classmethod
    def update_statistics(cls, date=None):
        """
        Update statistics for a given date.
        
        Args:
            date: Date to update statistics for (defaults to today)
        
        Returns:
            ProcessingStatistics instance
        """
        if date is None:
            date = timezone.now().date()
        
        # Get image processing results for the date
        image_results = ImageProcessingResult.objects.filter(
            submitted_at__date=date
        )
        
        # Get video processing jobs for the date
        video_jobs = VideoProcessingJob.objects.filter(
            submitted_at__date=date
        )
        
        # Calculate statistics
        stats, created = cls.objects.get_or_create(date=date)
        
        stats.total_requests = image_results.count() + video_jobs.count()
        stats.image_requests = image_results.count()
        stats.video_requests = video_jobs.count()
        
        stats.successful_requests = (
            image_results.filter(status='completed').count() +
            video_jobs.filter(status='completed').count()
        )
        stats.failed_requests = (
            image_results.filter(status='failed').count() +
            video_jobs.filter(status='failed').count()
        )
        
        # Calculate average processing times
        completed_images = image_results.filter(status='completed', processing_time__isnull=False)
        if completed_images.exists():
            stats.avg_image_processing_time = sum(
                img.processing_time for img in completed_images
            ) / completed_images.count()
        
        completed_videos = video_jobs.filter(status='completed', processing_time__isnull=False)
        if completed_videos.exists():
            stats.avg_video_processing_time = sum(
                vid.processing_time for vid in completed_videos
            ) / completed_videos.count()
        
        # Calculate detection statistics
        stats.total_detections = sum(img.detection_count for img in image_results)
        stats.person_detections = sum(
            len(img.get_detections_by_type('person')) for img in image_results
        )
        stats.vehicle_detections = sum(
            len(img.get_detections_by_type('vehicle')) for img in image_results
        )
        
        # Base64 statistics
        stats.base64_images_processed = image_results.filter(
            processed_image_base64__isnull=False
        ).exclude(processed_image_base64='').count()
        
        stats.base64_key_frames_processed = sum(
            job.key_frames_count for job in video_jobs
        )
        
        stats.save()
        return stats