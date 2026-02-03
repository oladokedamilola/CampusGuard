# smart_surveillance/cameras/services/fastapi_client.py
"""
Enhanced FastAPI client for base64 integration with smart surveillance system.
"""
import requests
import json
import logging
import time
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)

class FastAPIClient:
    """
    Enhanced client for communicating with the FastAPI processing server.
    Supports base64 image/video processing.
    """
    
    def __init__(self):
        self.base_url = settings.FASTAPI_CONFIG['BASE_URL'].rstrip('/')
        self.api_key = settings.FASTAPI_CONFIG['API_KEY']
        self.timeout = settings.FASTAPI_CONFIG.get('TIMEOUT', 120)
        self.retry_attempts = settings.FASTAPI_CONFIG.get('RETRY_ATTEMPTS', 3)
        self.retry_delay = settings.FASTAPI_CONFIG.get('RETRY_DELAY', 2)
        
        # Endpoints from settings
        self.endpoints = settings.FASTAPI_CONFIG.get('ENDPOINTS', {
            'PROCESS_IMAGE': '/api/v1/process/image',
            'PROCESS_VIDEO': '/api/v1/process/video',
            'JOB_STATUS': '/api/v1/jobs/{job_id}/status',
            'HEALTH_CHECK': '/health',
        })
        
        # Headers
        self.headers = {
            'X-API-Key': self.api_key,
            'User-Agent': 'SmartSurveillance-Django/1.0',
            'Accept': 'application/json',
        }
    
    def _make_request_with_retry(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests
        
        Returns:
            requests.Response object
        
        Raises:
            Exception: If all retries fail
        """
        url = f"{self.base_url}{endpoint}"
        
        # Extract timeout from kwargs if provided, otherwise use default
        timeout = kwargs.pop('timeout', self.timeout)
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    timeout=timeout,
                    **kwargs
                )
                
                logger.debug(f"FastAPI Request: {method} {url} - Status: {response.status_code}")
                
                return response
                
            except Timeout as e:
                logger.warning(f"FastAPI timeout (attempt {attempt + 1}/{self.retry_attempts}): {str(e)}")
                if attempt == self.retry_attempts - 1:
                    raise FastAPIClientError(f"Request timed out after {self.retry_attempts} attempts")
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                
            except (ConnectionError, RequestException) as e:
                logger.error(f"FastAPI request error: {str(e)}")
                if attempt == self.retry_attempts - 1:
                    raise FastAPIClientError(f"Request failed after {self.retry_attempts} attempts: {str(e)}")
                time.sleep(self.retry_delay)
        
        # This should never be reached
        raise FastAPIClientError("Max retries exceeded")
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check if FastAPI server is healthy.
        
        Returns:
            Dict with health status
        """
        try:
            response = self._make_request_with_retry(
                method='GET',
                endpoint=self.endpoints['HEALTH_CHECK'],
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': True,
                    'status': 'online',
                    'response': data,
                    'server': self.base_url,
                }
            else:
                return {
                    'healthy': False,
                    'status': 'error',
                    'message': f"Health check failed: {response.status_code}",
                    'server': self.base_url,
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'healthy': False,
                'status': 'offline',
                'error': str(e),
                'server': self.base_url,
            }
    
    def process_image(self, image_file, detection_types: List[str] = None, 
                     return_base64: bool = True, django_media_id: str = None,
                     django_user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Process a single image through FastAPI with base64 support.
        
        Args:
            image_file: Django File object, path, or bytes
            detection_types: List of detection types ['person', 'vehicle', 'face']
            return_base64: Whether to request base64 processed image
            django_media_id: Optional Django media ID for tracking
            django_user_id: Optional Django user ID for tracking
        
        Returns:
            Dict with analysis results including 'processed_image_base64' or None if failed
        """
        try:
            # Read file content
            filename, file_content, mime_type = self._read_file_content(image_file)
            
            # Prepare files for upload
            files = {
                'file': (filename, file_content, mime_type)
            }
            
            # Prepare parameters
            data = {
                'return_base64': str(return_base64).lower(),
            }
            
            if detection_types:
                data['detection_types'] = ','.join(detection_types)
            
            if django_media_id:
                data['django_media_id'] = django_media_id
            
            if django_user_id:
                data['django_user_id'] = django_user_id
            
            # Send request
            logger.info(f"Sending image to FastAPI at {self.base_url}{self.endpoints['PROCESS_IMAGE']}")
            logger.info(f"Parameters: return_base64={return_base64}, detection_types={detection_types}")
            
            response = self._make_request_with_retry(
                method='POST',
                endpoint=self.endpoints['PROCESS_IMAGE'],
                files=files,
                data=data
            )
            
            logger.info(f"FastAPI response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Add metadata
                result['processed_by'] = 'fastapi'
                result['server_url'] = self.base_url
                result['request_type'] = 'image_processing'
                result['has_base64'] = 'processed_image_base64' in result
                
                # Log base64 availability
                if result['has_base64']:
                    logger.info(f"Response contains base64 processed image")
                else:
                    logger.warning(f"Response does not contain base64 processed image")
                
                return result
            else:
                logger.error(f"Image processing failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return None
    
    def process_video(self, video_file, detection_types: List[str] = None,
                     return_key_frames: bool = True, django_media_id: str = None,
                     django_user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Submit video for processing and get job ID with base64 key frames support.
        
        Args:
            video_file: Django File object, path, or bytes
            detection_types: List of detection types
            return_key_frames: Whether to request base64 key frames
            django_media_id: Optional Django media ID for tracking
            django_user_id: Optional Django user ID for tracking
        
        Returns:
            Dict with job_id and status, including 'key_frames_base64' if available
        """
        try:
            # Read file content
            filename, file_content, mime_type = self._read_file_content(video_file)
            
            # Prepare files for upload
            files = {
                'file': (filename, file_content, mime_type)
            }
            
            # Prepare parameters
            data = {
                'return_key_frames': str(return_key_frames).lower(),
            }
            
            if detection_types:
                data['detection_types'] = ','.join(detection_types)
            
            if django_media_id:
                data['django_media_id'] = django_media_id
            
            if django_user_id:
                data['django_user_id'] = django_user_id
            
            # Send request
            logger.info(f"Sending video to FastAPI at {self.base_url}{self.endpoints['PROCESS_VIDEO']}")
            logger.info(f"Parameters: return_key_frames={return_key_frames}, detection_types={detection_types}")
            
            response = self._make_request_with_retry(
                method='POST',
                endpoint=self.endpoints['PROCESS_VIDEO'],
                files=files,
                data=data,
                timeout=180  # Longer timeout for video upload
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Add metadata
                result['processed_by'] = 'fastapi'
                result['server_url'] = self.base_url
                result['request_type'] = 'video_processing'
                result['has_key_frames'] = 'key_frames_base64' in result
                
                # Log key frames availability
                if result['has_key_frames']:
                    key_frames = result.get('key_frames_base64', [])
                    logger.info(f"Response contains {len(key_frames)} base64 key frames")
                else:
                    logger.warning(f"Response does not contain base64 key frames")
                
                return result
            else:
                logger.error(f"Video job submission failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting video job: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a video processing job.
        
        Args:
            job_id: Job ID from process_video
        
        Returns:
            Dict with job status and progress
        """
        try:
            endpoint = self.endpoints['JOB_STATUS'].format(job_id=job_id)
            response = self._make_request_with_retry(
                method='GET',
                endpoint=endpoint,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Job status check failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking job status: {e}")
            return None
    
    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get results of a completed job.
        
        Args:
            job_id: Job ID from process_video
        
        Returns:
            Dict with full analysis results including base64 data
        """
        try:
            # First get status to check if job is completed
            status = self.get_job_status(job_id)
            if not status or status.get('status') != 'completed':
                logger.warning(f"Job {job_id} is not completed yet")
                return None
            
            # In the FastAPI design, results might be included in status response
            # or might need a separate endpoint. We'll check both.
            if 'result' in status and status['result']:
                result = status['result']
                
                # Add metadata
                result['job_id'] = job_id
                result['retrieved_at'] = time.time()
                result['has_base64_key_frames'] = 'key_frames_base64' in result
                
                return result
            else:
                # Try to get results from a different endpoint if available
                # This depends on your FastAPI implementation
                logger.warning(f"No results found in status response for job {job_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return None
    
    def get_available_models(self) -> Optional[List[str]]:
        """
        Get list of available detection models.
        """
        try:
            # This endpoint might be different in your FastAPI implementation
            response = self._make_request_with_retry(
                method='GET',
                endpoint='/api/v1/models',
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('models', [])
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return None
    
    def advanced_crowd_detection(self, image_file) -> Optional[Dict[str, Any]]:
        """
        Perform advanced crowd detection on image.
        """
        try:
            # Read file content
            filename, file_content, mime_type = self._read_file_content(image_file)
            
            files = {
                'file': (filename, file_content, mime_type)
            }
            
            response = self._make_request_with_retry(
                method='POST',
                endpoint='/api/v1/advanced/crowd-detection',
                files=files
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error in crowd detection: {e}")
            return None
    
    def _read_file_content(self, file_input):
        """
        Read file content from various input types.
        
        Args:
            file_input: Django File object, path, or bytes
        
        Returns:
            Tuple of (filename, file_content, mime_type)
        """
        try:
            # Determine MIME type and read content
            if hasattr(file_input, 'read'):
                # It's a Django File object
                file_input.seek(0)  # Rewind to beginning
                file_content = file_input.read()
                filename = file_input.name if hasattr(file_input, 'name') else 'upload.jpg'
                
                # Guess MIME type from filename
                if filename.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif filename.lower().endswith('.bmp'):
                    mime_type = 'image/bmp'
                elif filename.lower().endswith('.mp4'):
                    mime_type = 'video/mp4'
                elif filename.lower().endswith('.avi'):
                    mime_type = 'video/x-msvideo'
                elif filename.lower().endswith('.mov'):
                    mime_type = 'video/quicktime'
                else:
                    mime_type = 'application/octet-stream'
                    
            elif hasattr(file_input, 'temporary_file_path'):
                # It's a TemporaryUploadedFile
                with open(file_input.temporary_file_path(), 'rb') as f:
                    file_content = f.read()
                filename = file_input.name if hasattr(file_input, 'name') else 'upload.jpg'
                mime_type = file_input.content_type if hasattr(file_input, 'content_type') else 'application/octet-stream'
                
            elif isinstance(file_input, str):
                # It's a path
                with open(file_input, 'rb') as f:
                    file_content = f.read()
                filename = file_input.split('/')[-1]
                
                # Guess MIME type from extension
                if filename.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif filename.lower().endswith('.mp4'):
                    mime_type = 'video/mp4'
                else:
                    mime_type = 'application/octet-stream'
                    
            else:
                # Assume it's already bytes
                file_content = file_input
                filename = 'upload.jpg'
                mime_type = 'image/jpeg'
            
            return filename, file_content, mime_type
            
        except Exception as e:
            logger.error(f"Error reading file content: {e}")
            raise
    
    def validate_response_has_base64(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that FastAPI response contains expected base64 data.
        
        Args:
            response_data: FastAPI response dictionary
        
        Returns:
            Dict with validation results
        """
        validation = {
            'has_processed_image': False,
            'has_key_frames': False,
            'has_summary': False,
            'image_base64_size': 0,
            'key_frames_count': 0,
            'is_valid': False,
        }
        
        try:
            # Check for processed image
            if 'processed_image_base64' in response_data and response_data['processed_image_base64']:
                validation['has_processed_image'] = True
                validation['image_base64_size'] = len(response_data['processed_image_base64'])
            
            # Check for key frames
            if 'key_frames_base64' in response_data and response_data['key_frames_base64']:
                if isinstance(response_data['key_frames_base64'], list):
                    validation['has_key_frames'] = True
                    validation['key_frames_count'] = len(response_data['key_frames_base64'])
            
            # Check for summary
            if 'summary' in response_data and response_data['summary']:
                validation['has_summary'] = True
            
            # Determine if response is valid
            validation['is_valid'] = (
                validation['has_processed_image'] or 
                validation['has_key_frames'] or 
                validation['has_summary']
            )
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            validation['error'] = str(e)
            return validation

class FastAPIClientError(Exception):
    """Custom exception for FastAPI client errors."""
    pass

# Singleton instance for reuse
fastapi_client = FastAPIClient()