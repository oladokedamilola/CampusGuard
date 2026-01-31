# smart_surveillance/cameras/services/media_processor.py
import os
import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image
import mimetypes
from django.utils import timezone
from .fastapi_client import FastAPIClient
from ..models import MediaUpload, MediaAnalysisResult

logger = logging.getLogger(__name__)

class MediaProcessor:
    """
    Handles media processing workflow from upload to analysis results.
    """
    
    def __init__(self):
        self.fastapi_client = FastAPIClient()
    
    def process_media_upload(self, media_upload: MediaUpload, detection_types: list = None) -> bool:
        """
        Main method to process a media upload through FastAPI.
        
        Args:
            media_upload: MediaUpload instance
            detection_types: List of detection types
            
        Returns:
            bool: True if processing started successfully
        """
        try:
            # Update status
            media_upload.processing_status = MediaUpload.ProcessingStatus.PROCESSING
            media_upload.processing_started = timezone.now()
            media_upload.save()
            
            # Determine endpoint based on media type
            if media_upload.is_image():
                return self._process_image(media_upload, detection_types)
            elif media_upload.is_video():
                return self._process_video(media_upload, detection_types)
            else:
                logger.error(f"Unknown media type: {media_upload.media_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing media upload {media_upload.id}: {e}")
            media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
            media_upload.save()
            return False
    
    def _process_image(self, media_upload: MediaUpload, detection_types: list) -> bool:
        """
        Process an image upload.
        """
        try:
            # Open the image file
            logger.info(f"Processing image {media_upload.id}: {media_upload.original_file.name}")
            
            # Check file size
            media_upload.original_file.seek(0, os.SEEK_END)
            file_size = media_upload.original_file.tell()
            media_upload.original_file.seek(0)
            logger.info(f"Image file size: {file_size} bytes")
            
            # Read the file
            file_content = media_upload.original_file.read()
            logger.info(f"Read {len(file_content)} bytes from file")
            
            # Check first few bytes to verify it's an image
            if len(file_content) > 0:
                first_bytes = file_content[:8].hex()
                logger.info(f"First 8 bytes (hex): {first_bytes}")
            
            # Reset file pointer
            media_upload.original_file.seek(0)
            
            # Send to FastAPI
            logger.info(f"Sending to FastAPI with detection_types: {detection_types}")
            response = self.fastapi_client.process_image(
                media_upload.original_file,
                detection_types or ['person', 'vehicle']
            )
            
            if response:
                # Save response
                media_upload.response_data = response
                media_upload.fastapi_endpoint = '/api/v1/process/image'
                
                # Create analysis results
                self._create_analysis_results(media_upload, response)
                
                # Update status
                media_upload.processing_status = MediaUpload.ProcessingStatus.COMPLETED
                media_upload.processing_completed = timezone.now()
                media_upload.save()
                
                logger.info(f"Image processing completed for {media_upload.id}")
                return True
            else:
                logger.error(f"FastAPI returned no response for image {media_upload.id}")
                media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
                media_upload.save()
                return False
                
        except Exception as e:
            logger.error(f"Error in image processing: {e}", exc_info=True)
            media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
            media_upload.save()
            return False
    
    def _process_video(self, media_upload: MediaUpload, detection_types: list) -> bool:
        """
        Process a video upload (asynchronous job).
        """
        try:
            # Open the video file
            with media_upload.original_file.open('rb') as f:
                video_data = f.read()
            
            # Submit job to FastAPI
            response = self.fastapi_client.process_video(
                video_data,
                detection_types or ['person', 'vehicle', 'motion']
            )
            
            if response and 'job_id' in response:
                # Save job information
                media_upload.job_id = response['job_id']
                media_upload.response_data = response
                media_upload.fastapi_endpoint = '/api/v1/jobs/process/video'
                media_upload.save()
                
                # Start background task to monitor job
                self._start_job_monitoring(media_upload)
                
                logger.info(f"Video job submitted for {media_upload.id}, job_id: {response['job_id']}")
                return True
            else:
                media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
                media_upload.save()
                return False
                
        except Exception as e:
            logger.error(f"Error submitting video job: {e}")
            media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
            media_upload.save()
            return False
    
    def _create_analysis_results(self, media_upload: MediaUpload, fastapi_response: Dict) -> MediaAnalysisResult:
        """
        Create analysis results from FastAPI response.
        """
        try:
            # Parse response and extract statistics
            detections = fastapi_response.get('detections', [])
            
            # Count by type
            person_count = sum(1 for d in detections if d.get('class') == 'person')
            vehicle_count = sum(1 for d in detections if d.get('class') in ['car', 'truck', 'bus', 'motorcycle'])
            
            # Create result object
            result = MediaAnalysisResult.objects.create(
                media_upload=media_upload,
                total_detections=len(detections),
                person_count=person_count,
                vehicle_count=vehicle_count,
                suspicious_activity_count=0,  # Could be calculated from behavior analysis
                detections_json=detections,
                timeline_data=self._create_timeline_data(detections),
                heatmap_data=self._create_heatmap_data(detections)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating analysis results: {e}")
            return None
    
    def _create_timeline_data(self, detections: list) -> list:
        """Create timeline data for charts."""
        timeline = []
        for detection in detections:
            timeline.append({
                'time': detection.get('timestamp', 0),
                'type': detection.get('class', 'unknown'),
                'confidence': detection.get('confidence', 0)
            })
        return timeline
    
    def _create_heatmap_data(self, detections: list) -> Dict:
        """Create heatmap data from detections."""
        heatmap = {
            'points': [],
            'max_intensity': 0
        }
        
        for detection in detections:
            bbox = detection.get('bbox', {})
            if bbox:
                x = (bbox.get('x1', 0) + bbox.get('x2', 0)) / 2
                y = (bbox.get('y1', 0) + bbox.get('y2', 0)) / 2
                heatmap['points'].append({'x': x, 'y': y, 'value': 1})
        
        heatmap['max_intensity'] = len(heatmap['points'])
        return heatmap
    
    def _start_job_monitoring(self, media_upload: MediaUpload):
        """
        Start monitoring a video processing job.
        This could be implemented with Celery or Django Background Tasks.
        """
        # For now, we'll implement a simple version
        # In production, use Celery or similar
        
        from threading import Thread
        
        def monitor_job():
            import time
            from django.utils import timezone
            
            max_checks = 60  # Check for up to 5 minutes
            check_interval = 5  # Check every 5 seconds
            
            for i in range(max_checks):
                try:
                    # Check job status
                    status = self.fastapi_client.get_job_status(media_upload.job_id)
                    
                    if status and status.get('status') == 'completed':
                        # Get results
                        results = self.fastapi_client.get_job_results(media_upload.job_id)
                        if results:
                            # Update media upload with results
                            media_upload.response_data = results
                            media_upload.processing_status = MediaUpload.ProcessingStatus.COMPLETED
                            media_upload.processing_completed = timezone.now()
                            media_upload.save()
                            
                            # Create analysis results
                            self._create_analysis_results(media_upload, results)
                            break
                    
                    elif status and status.get('status') == 'failed':
                        media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
                        media_upload.save()
                        break
                    
                    # Update progress if available
                    if status and 'progress' in status:
                        # You could store progress somewhere
                        pass
                    
                except Exception as e:
                    logger.error(f"Error monitoring job {media_upload.job_id}: {e}")
                
                time.sleep(check_interval)
            
            # If we get here and job isn't completed, mark as failed
            if media_upload.processing_status != MediaUpload.ProcessingStatus.COMPLETED:
                media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
                media_upload.save()
        
        # Start monitoring thread
        thread = Thread(target=monitor_job, daemon=True)
        thread.start()
    
    def generate_thumbnail(self, media_upload: MediaUpload) -> bool:
        """
        Generate thumbnail for media upload.
        """
        try:
            if media_upload.is_image():
                # For images, create resized thumbnail
                with Image.open(media_upload.original_file) as img:
                    img.thumbnail((300, 300))
                    
                    # Save thumbnail
                    thumb_io = BytesIO()
                    img.save(thumb_io, format='JPEG')
                    
                    media_upload.thumbnail.save(
                        f'thumb_{media_upload.id}.jpg',
                        ContentFile(thumb_io.getvalue()),
                        save=False
                    )
                    media_upload.save()
                    
            elif media_upload.is_video():
                # For videos, you could extract first frame
                # This requires moviepy or similar
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return False