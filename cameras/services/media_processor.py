# smart_surveillance/cameras/services/media_processor.py
"""
Enhanced media processor with base64 support for FastAPI integration.
"""
import os
import json
import logging
import time
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image
import mimetypes
from django.utils import timezone

# Import our services
from .fastapi_client import FastAPIClient, fastapi_client
from .base64_processor import Base64Processor, base64_processor
from ..models import MediaUpload, MediaAnalysisResult, VideoFile
from surveillance.models import VideoProcessingJob, ImageProcessingResult

logger = logging.getLogger(__name__)

class MediaProcessor:
    """
    Enhanced media processor with base64 support for FastAPI integration.
    """
    
    def __init__(self):
        self.fastapi_client = fastapi_client
        self.base64_processor = base64_processor
    
    def process_media_upload(self, media_upload: MediaUpload, 
                           detection_types: List[str] = None,
                           request_base64: bool = True) -> Dict[str, Any]:
        """
        Main method to process a media upload through FastAPI with base64 support.
        
        Args:
            media_upload: MediaUpload instance
            detection_types: List of detection types
            request_base64: Whether to request base64 processed output
        
        Returns:
            Dict with processing results
        """
        result = {
            'success': False,
            'message': '',
            'job_id': None,
            'has_base64_data': False,
            'saved_files': [],
            'processing_time': None
        }
        
        try:
            # Check FastAPI server health
            health_status = self.fastapi_client.check_health()
            if not health_status.get('healthy'):
                result['message'] = f"FastAPI server is not healthy: {health_status.get('message', 'Unknown error')}"
                media_upload.mark_as_failed(result['message'])
                return result
            
            # Update status to processing
            media_upload.mark_as_processing()
            start_time = time.time()
            
            # Determine processing method based on media type
            if media_upload.is_image():
                process_result = self._process_image_with_base64(
                    media_upload, 
                    detection_types, 
                    request_base64
                )
            elif media_upload.is_video():
                process_result = self._process_video_with_base64(
                    media_upload, 
                    detection_types, 
                    request_base64
                )
            else:
                error_msg = f"Unsupported media type: {media_upload.media_type}"
                result['message'] = error_msg
                media_upload.mark_as_failed(error_msg)
                return result
            
            # Update result with processing results
            result.update(process_result)
            result['processing_time'] = time.time() - start_time
            
            # Update media upload status
            if result['success']:
                media_upload.mark_as_completed(process_result.get('response_data'))
                
                # Save base64 data if available
                if result.get('has_base64_data'):
                    self._save_base64_data_to_media(media_upload, process_result.get('response_data'))
            else:
                media_upload.mark_as_failed(result.get('message', 'Unknown error'))
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing media upload: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result['message'] = error_msg
            media_upload.mark_as_failed(error_msg)
            return result
    
    def _process_image_with_base64(self, media_upload: MediaUpload, 
                                 detection_types: List[str],
                                 request_base64: bool) -> Dict[str, Any]:
        """
        Process an image upload with base64 support.
        
        Args:
            media_upload: MediaUpload instance
            detection_types: List of detection types
            request_base64: Whether to request base64 output
        
        Returns:
            Dict with processing results
        """
        result = {
            'success': False,
            'message': '',
            'has_base64_data': False,
            'response_data': None,
        }
        
        try:
            logger.info(f"Processing image {media_upload.id}: {media_upload.original_file.name}")
            
            # Prepare detection types
            if not detection_types:
                detection_types = ['person', 'vehicle', 'face']
            
            # Send to FastAPI with base64 request
            fastapi_response = self.fastapi_client.process_image(
                image_file=media_upload.original_file,
                detection_types=detection_types,
                return_base64=request_base64,
                django_media_id=str(media_upload.id),
                django_user_id=str(media_upload.uploaded_by.id) if media_upload.uploaded_by else None
            )
            
            if not fastapi_response:
                result['message'] = "FastAPI returned no response"
                return result
            
            result['response_data'] = fastapi_response
            
            # Validate response
            validation = self.fastapi_client.validate_response_has_base64(fastapi_response)
            
            if not validation['is_valid']:
                result['message'] = "FastAPI response does not contain valid base64 data or summary"
                return result
            
            # Process base64 image if available
            if validation['has_processed_image']:
                base64_result = self.base64_processor.process_fastapi_image_response(
                    fastapi_response, 
                    media_upload
                )
                
                if base64_result['success']:
                    result['has_base64_data'] = True
                    result['message'] = base64_result['message']
                    result['saved_path'] = base64_result.get('saved_path')
                else:
                    result['message'] = base64_result['message']
                    return result
            
            # Create analysis results
            analysis_result = self._create_or_update_analysis_results(
                media_upload, 
                fastapi_response
            )
            
            # Also create ImageProcessingResult for backward compatibility
            self._create_image_processing_result(
                media_upload, 
                fastapi_response, 
                analysis_result
            )
            
            result['success'] = True
            if not result['message']:
                result['message'] = "Image processed successfully"
            
            return result
            
        except Exception as e:
            error_msg = f"Error in image processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result['message'] = error_msg
            return result
    
    def _process_video_with_base64(self, media_upload: MediaUpload, 
                                 detection_types: List[str],
                                 request_base64: bool) -> Dict[str, Any]:
        """
        Process a video upload with base64 key frames support.
        
        Args:
            media_upload: MediaUpload instance
            detection_types: List of detection types
            request_base64: Whether to request base64 key frames
        
        Returns:
            Dict with processing results
        """
        result = {
            'success': False,
            'message': '',
            'job_id': None,
            'has_base64_data': False,
            'response_data': None,
        }
        
        try:
            logger.info(f"Processing video {media_upload.id}: {media_upload.original_file.name}")
            
            # Prepare detection types
            if not detection_types:
                detection_types = ['person', 'vehicle', 'motion']
            
            # Send to FastAPI with key frames request
            fastapi_response = self.fastapi_client.process_video(
                video_file=media_upload.original_file,
                detection_types=detection_types,
                return_key_frames=request_base64,
                django_media_id=str(media_upload.id),
                django_user_id=str(media_upload.uploaded_by.id) if media_upload.uploaded_by else None
            )
            
            if not fastapi_response:
                result['message'] = "FastAPI returned no response"
                return result
            
            result['response_data'] = fastapi_response
            
            # Check if this is a synchronous or asynchronous response
            if 'job_id' in fastapi_response:
                # Asynchronous processing - store job ID and start monitoring
                result['job_id'] = fastapi_response['job_id']
                media_upload.job_id = fastapi_response['job_id']
                media_upload.save()
                
                # Start monitoring thread for async jobs
                self._start_async_job_monitoring(media_upload, fastapi_response['job_id'])
                
                result['success'] = True
                result['message'] = f"Video processing job submitted. Job ID: {fastapi_response['job_id']}"
                
            else:
                # Synchronous processing - process results immediately
                validation = self.fastapi_client.validate_response_has_base64(fastapi_response)
                
                if not validation['is_valid']:
                    result['message'] = "FastAPI response does not contain valid base64 data or summary"
                    return result
                
                # Process base64 key frames if available
                if validation['has_key_frames'] or validation['has_summary']:
                    base64_result = self.base64_processor.process_fastapi_video_response(
                        fastapi_response, 
                        media_upload
                    )
                    
                    if base64_result['success']:
                        result['has_base64_data'] = True
                        result['key_frames_saved'] = base64_result['key_frames_saved']
                        result['has_summary'] = base64_result['has_summary']
                    else:
                        result['message'] = base64_result['message']
                        return result
                
                # Create analysis results
                analysis_result = self._create_or_update_analysis_results(
                    media_upload, 
                    fastapi_response
                )
                
                # Also create VideoProcessingJob for backward compatibility
                video_job = self._create_video_processing_job(
                    media_upload, 
                    fastapi_response, 
                    analysis_result
                )
                
                # Link video job to media upload
                if video_job:
                    media_upload.video_processing_job = video_job
                    media_upload.save()
                
                result['success'] = True
                result['message'] = "Video processed successfully"
            
            return result
            
        except Exception as e:
            error_msg = f"Error in video processing: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result['message'] = error_msg
            return result
    
    def _create_or_update_analysis_results(self, media_upload: MediaUpload, 
                                         fastapi_response: Dict[str, Any]) -> MediaAnalysisResult:
        """
        Create or update analysis results from FastAPI response.
        """
        try:
            # Extract summary and detections
            summary = self.base64_processor.extract_summary_from_fastapi_response(fastapi_response)
            detections = fastapi_response.get('detections', [])
            
            # Calculate statistics
            total_detections = len(detections)
            person_count = sum(1 for d in detections 
                             if isinstance(d, dict) and 
                             d.get('label', '').lower() == 'person' or 
                             d.get('class', '').lower() == 'person')
            vehicle_count = sum(1 for d in detections 
                              if isinstance(d, dict) and 
                              d.get('label', '').lower() in ['car', 'truck', 'bus', 'motorcycle', 'vehicle'] or
                              d.get('class', '').lower() in ['car', 'truck', 'bus', 'motorcycle', 'vehicle'])
            
            # Extract base64 image if available
            base64_image = self.base64_processor.extract_image_from_fastapi_response(fastapi_response)
            
            # Get or create analysis results
            analysis_result, created = MediaAnalysisResult.objects.get_or_create(
                media_upload=media_upload,
                defaults={
                    'total_detections': total_detections,
                    'person_count': person_count,
                    'vehicle_count': vehicle_count,
                    'detections_json': detections,
                    'timeline_data': self._create_timeline_data(detections),
                    'heatmap_data': self._create_heatmap_data(detections),
                    'processed_image_base64': base64_image or '',
                }
            )
            
            if not created:
                # Update existing record
                analysis_result.total_detections = total_detections
                analysis_result.person_count = person_count
                analysis_result.vehicle_count = vehicle_count
                analysis_result.detections_json = detections
                analysis_result.timeline_data = self._create_timeline_data(detections)
                analysis_result.heatmap_data = self._create_heatmap_data(detections)
                if base64_image:
                    analysis_result.processed_image_base64 = base64_image
                analysis_result.save()
            
            # Save base64 image to file if not already done
            if base64_image and not analysis_result.annotated_media_path:
                analysis_result.save_base64_image_to_file()
            
            logger.info(f"Analysis results {'created' if created else 'updated'}: {analysis_result.id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error creating analysis results: {e}", exc_info=True)
            
            # Create minimal results to avoid errors
            try:
                analysis_result, _ = MediaAnalysisResult.objects.get_or_create(
                    media_upload=media_upload,
                    defaults={
                        'total_detections': 0,
                        'person_count': 0,
                        'vehicle_count': 0,
                        'detections_json': [],
                        'timeline_data': [],
                        'heatmap_data': {'points': [], 'max_intensity': 0},
                    }
                )
                return analysis_result
            except Exception as e2:
                logger.error(f"Failed to create minimal results: {e2}")
                raise
    
    def _create_image_processing_result(self, media_upload: MediaUpload, 
                                      fastapi_response: Dict[str, Any],
                                      analysis_result: MediaAnalysisResult) -> Optional[ImageProcessingResult]:
        """
        Create ImageProcessingResult for backward compatibility.
        """
        try:
            from surveillance.models import ImageProcessingResult
            
            # Extract relevant data
            detections = fastapi_response.get('detections', [])
            summary = self.base64_processor.extract_summary_from_fastapi_response(fastapi_response)
            
            # Create ImageProcessingResult
            image_result = ImageProcessingResult.objects.create(
                user=media_upload.uploaded_by,
                original_filename=os.path.basename(media_upload.original_file.name),
                file_size=media_upload.file_size,
                mime_type=media_upload.mime_type,
                job_id=media_upload.job_id or f"img_{media_upload.id}",
                processing_server='fastapi',
                server_url=self.fastapi_client.base_url,
                processing_time=media_upload.get_processing_time(),
                detection_count=analysis_result.total_detections,
                detections=detections,
                detection_summary=summary,
                status='completed',
                submitted_at=media_upload.processing_started or timezone.now(),
                completed_at=media_upload.processing_completed or timezone.now(),
            )
            
            return image_result
            
        except Exception as e:
            logger.error(f"Error creating ImageProcessingResult: {e}")
            return None
    
    def _create_video_processing_job(self, media_upload: MediaUpload, 
                                   fastapi_response: Dict[str, Any],
                                   analysis_result: MediaAnalysisResult) -> Optional[VideoProcessingJob]:
        """
        Create VideoProcessingJob for backward compatibility.
        """
        try:
            from surveillance.models import VideoProcessingJob
            
            # Extract summary
            summary = self.base64_processor.extract_summary_from_fastapi_response(fastapi_response)
            
            # Create VideoProcessingJob
            video_job = VideoProcessingJob.objects.create(
                user=media_upload.uploaded_by,
                job_id=media_upload.job_id or f"vid_{media_upload.id}",
                internal_id=f"MEDIA_{media_upload.id}",
                original_filename=os.path.basename(media_upload.original_file.name),
                file_size=media_upload.file_size,
                mime_type=media_upload.mime_type,
                processing_server='fastapi',
                server_url=self.fastapi_client.base_url,
                status='completed',
                progress=100.0,
                submitted_at=media_upload.processing_started or timezone.now(),
                completed_at=media_upload.processing_completed or timezone.now(),
                processing_time=media_upload.get_processing_time(),
                summary=summary,
                video_info={
                    'duration': media_upload.duration,
                    'resolution': media_upload.resolution,
                    'fps': media_upload.fps,
                }
            )
            
            return video_job
            
        except Exception as e:
            logger.error(f"Error creating VideoProcessingJob: {e}")
            return None
    
    def _create_timeline_data(self, detections: list) -> list:
        """Create timeline data for charts."""
        timeline = []
        for detection in detections:
            if isinstance(detection, dict):
                timeline.append({
                    'time': detection.get('timestamp', 0),
                    'type': detection.get('class', detection.get('label', 'unknown')),
                    'confidence': detection.get('confidence', 0)
                })
        return timeline
    
    def _create_heatmap_data(self, detections: list) -> Dict[str, Any]:
        """Create heatmap data from detections."""
        heatmap = {
            'points': [],
            'max_intensity': 0
        }
        
        for detection in detections:
            if not isinstance(detection, dict):
                continue
                
            bbox = detection.get('bbox')
            if bbox:
                if isinstance(bbox, dict):
                    # Dict format: {'x1': 120, 'y1': 85, 'x2': 310, 'y2': 480}
                    x = (bbox.get('x1', 0) + bbox.get('x2', 0)) / 2
                    y = (bbox.get('y1', 0) + bbox.get('y2', 0)) / 2
                elif isinstance(bbox, list) and len(bbox) >= 4:
                    # List format: [x1, y1, x2, y2] or [x, y, width, height]
                    x = (bbox[0] + bbox[2]) / 2 if len(bbox) == 4 else bbox[0]
                    y = (bbox[1] + bbox[3]) / 2 if len(bbox) == 4 else bbox[1]
                else:
                    continue  # Skip invalid bbox format
                
                heatmap['points'].append({'x': x, 'y': y, 'value': 1})
        
        heatmap['max_intensity'] = len(heatmap['points'])
        return heatmap
    
    def _save_base64_data_to_media(self, media_upload: MediaUpload, response_data: Dict[str, Any]):
        """
        Save base64 data from FastAPI response to media upload.
        """
        try:
            # For images
            if media_upload.is_image():
                base64_image = self.base64_processor.extract_image_from_fastapi_response(response_data)
                if base64_image:
                    media_upload.processed_file_base64 = base64_image
                    media_upload.save_processed_file_from_base64(base64_image)
            
            # For videos
            elif media_upload.is_video():
                key_frames = self.base64_processor.extract_key_frames_from_fastapi_response(response_data)
                if key_frames:
                    media_upload.key_frames_base64 = key_frames
                    media_upload.save_key_frames_from_base64(key_frames)
            
            media_upload.save()
            
        except Exception as e:
            logger.error(f"Error saving base64 data to media: {e}")
    
    def _start_async_job_monitoring(self, media_upload: MediaUpload, job_id: str):
        """
        Start monitoring an async video processing job.
        In production, use Celery or Django Background Tasks.
        """
        from threading import Thread
        
        def monitor_job():
            import time
            from django.utils import timezone
            
            max_checks = 120  # Check for up to 10 minutes (5-second intervals)
            check_interval = 5
            
            for i in range(max_checks):
                try:
                    # Check job status
                    status = self.fastapi_client.get_job_status(job_id)
                    
                    if not status:
                        time.sleep(check_interval)
                        continue
                    
                    # Update media upload status
                    if status.get('status') == 'completed':
                        # Get results
                        results = self.fastapi_client.get_job_results(job_id)
                        if results:
                            # Process results
                            base64_result = self.base64_processor.process_fastapi_video_response(
                                results, 
                                media_upload
                            )
                            
                            # Create analysis results
                            self._create_or_update_analysis_results(media_upload, results)
                            
                            # Create video processing job
                            self._create_video_processing_job(media_upload, results, None)
                            
                            # Mark as completed
                            media_upload.mark_as_completed(results)
                            
                            logger.info(f"Async job {job_id} completed successfully")
                            break
                    
                    elif status.get('status') == 'failed':
                        media_upload.mark_as_failed(status.get('message', 'Job failed'))
                        break
                    
                    # Update progress
                    progress = status.get('progress', 0)
                    media_upload.processing_status = MediaUpload.ProcessingStatus.PROCESSING
                    media_upload.save()
                    
                    logger.debug(f"Job {job_id} progress: {progress}%")
                    
                except Exception as e:
                    logger.error(f"Error monitoring job {job_id}: {e}")
                
                time.sleep(check_interval)
            
            # If we get here and job isn't completed, mark as failed
            if media_upload.processing_status != MediaUpload.ProcessingStatus.COMPLETED:
                media_upload.mark_as_failed("Job monitoring timeout")
        
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
                # For videos, use first key frame if available
                if media_upload.key_frames_base64 and len(media_upload.key_frames_base64) > 0:
                    # Decode first key frame
                    base64_img = media_upload.key_frames_base64[0]
                    content_file = self.base64_processor.decode_base64_to_file(base64_img)
                    
                    if content_file:
                        # Open and resize
                        with Image.open(content_file) as img:
                            img.thumbnail((300, 300))
                            thumb_io = BytesIO()
                            img.save(thumb_io, format='JPEG')
                            
                            media_upload.thumbnail.save(
                                f'thumb_{media_upload.id}.jpg',
                                ContentFile(thumb_io.getvalue()),
                                save=False
                            )
                            media_upload.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return False
    
    def check_processing_status(self, media_upload: MediaUpload) -> Dict[str, Any]:
        """
        Check current processing status of a media upload.
        
        Args:
            media_upload: MediaUpload instance
        
        Returns:
            Dict with status information
        """
        status = {
            'media_id': media_upload.id,
            'status': media_upload.processing_status,
            'progress': media_upload.get_progress_percentage(),
            'has_processed_file': media_upload.has_processed_file(),
            'has_base64_data': media_upload.has_base64_data(),
            'error_message': media_upload.error_message,
            'processing_time': media_upload.get_processing_time(),
            'uploaded_at': media_upload.uploaded_at,
        }
        
        # For async jobs, check FastAPI status
        if media_upload.job_id and media_upload.processing_status in [
            MediaUpload.ProcessingStatus.PROCESSING,
            MediaUpload.ProcessingStatus.PENDING
        ]:
            try:
                job_status = self.fastapi_client.get_job_status(media_upload.job_id)
                if job_status:
                    status['fastapi_status'] = job_status.get('status')
                    status['fastapi_progress'] = job_status.get('progress', 0)
                    status['fastapi_message'] = job_status.get('message', '')
            except Exception as e:
                logger.error(f"Error checking FastAPI job status: {e}")
        
        # Add analysis results if available
        try:
            if hasattr(media_upload, 'analysis_results'):
                status['analysis'] = {
                    'total_detections': media_upload.analysis_results.total_detections,
                    'person_count': media_upload.analysis_results.person_count,
                    'vehicle_count': media_upload.analysis_results.vehicle_count,
                }
        except Exception as e:
            logger.error(f"Error getting analysis results: {e}")
        
        return status

# Singleton instance for reuse
media_processor = MediaProcessor()