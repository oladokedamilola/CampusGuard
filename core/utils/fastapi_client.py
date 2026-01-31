"""
FastAPI client for communicating with the processing server.
"""
import requests
import time
import logging
from typing import Dict, List, Optional, Any
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)

class FastAPIClientError(Exception):
    """Custom exception for FastAPI client errors."""
    pass

class FastAPIClient:
    """
    Client for communicating with FastAPI processing server.
    """
    
    def __init__(self):
        # Get config from settings
        self.config = {
            'DEV': settings.FASTAPI_CONFIG['DEV'],
            'PROD': settings.FASTAPI_CONFIG['PROD']
        }
        
        # Use appropriate config based on environment
        if settings.DEBUG:
            self.config = self.config['DEV']
        else:
            self.config = self.config['PROD']
        
        self.base_url = self.config['BASE_URL']
        self.api_key = self.config['API_KEY']
        self.headers = {
            'X-API-Key': self.api_key,
            'User-Agent': 'SmartSurveillance-Django/1.0'
        }
        
        logger.info(f"FastAPI Client initialized with base URL: {self.base_url}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic.
        """
        url = f"{self.base_url}{endpoint}"
        max_retries = self.config['MAX_RETRIES']
        
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    **kwargs
                )
                
                # Log request (excluding sensitive data)
                logger.debug(f"FastAPI Request: {method} {url} - Status: {response.status_code}")
                
                return response
                
            except Timeout as e:
                logger.warning(f"FastAPI timeout (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise FastAPIClientError(f"Request timed out after {max_retries} attempts")
                time.sleep(self.config['RETRY_DELAY'] * (2 ** attempt))  # Exponential backoff
                
            except RequestException as e:
                logger.error(f"FastAPI request error: {str(e)}")
                if attempt == max_retries - 1:
                    raise FastAPIClientError(f"Request failed after {max_retries} attempts: {str(e)}")
                time.sleep(self.config['RETRY_DELAY'])
        
        # This should never be reached
        raise FastAPIClientError("Max retries exceeded")
    
    def process_image(self, image_file: UploadedFile, **kwargs) -> Dict[str, Any]:
        """
        Process a single image synchronously.
        
        Args:
            image_file: Django UploadedFile object
            **kwargs: Additional processing parameters
        
        Returns:
            Dictionary with processing results
        """
        try:
            # Prepare file for upload
            files = {
                'file': (image_file.name, image_file.read(), image_file.content_type)
            }
            
            # Default parameters
            params = {
                'confidence_threshold': str(kwargs.get('confidence', 0.5)),
                'return_image': str(kwargs.get('return_image', False)).lower(),
                'detection_types': kwargs.get('detection_types', 'person,vehicle,face'),
                'enable_advanced_features': str(kwargs.get('advanced', False)).lower(),
            }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in ['confidence', 'return_image', 'detection_types', 'advanced']:
                    params[key] = str(value)
            
            # Make request
            response = self._make_request(
                method='POST',
                endpoint='/api/v1/process/image',
                files=files,
                data=params,
                timeout=self.config['REQUEST_TIMEOUT']
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Add server info to result
                result['processed_by'] = 'fastapi'
                result['server_url'] = self.base_url
                
                return result
            else:
                error_msg = f"Image processing failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise FastAPIClientError(error_msg)
                
        except Exception as e:
            logger.error(f"Error in process_image: {str(e)}")
            raise
    
    def submit_video_job(self, video_file: UploadedFile, **kwargs) -> Dict[str, Any]:
        """
        Submit video for asynchronous processing.
        
        Args:
            video_file: Django UploadedFile object
            **kwargs: Additional processing parameters
        
        Returns:
            Dictionary with job submission details
        """
        try:
            # Prepare file for upload
            files = {
                'file': (video_file.name, video_file.read(), video_file.content_type)
            }
            
            # Default parameters for video processing
            params = {
                'confidence_threshold': str(kwargs.get('confidence', 0.5)),
                'frame_sample_rate': str(kwargs.get('frame_sample_rate', 5)),
                'analyze_motion': str(kwargs.get('analyze_motion', True)).lower(),
                'return_summary_only': str(kwargs.get('summary_only', True)).lower(),
                'enable_advanced_features': str(kwargs.get('advanced', False)).lower(),
                'priority': str(kwargs.get('priority', 1)),  # 0=low, 1=normal, 2=high, 3=urgent
            }
            
            # Add specific advanced features if requested
            if kwargs.get('crowd_detection'):
                params['crowd_detection'] = 'true'
                params['min_people_count'] = str(kwargs.get('min_people_count', 3))
            
            if kwargs.get('vehicle_counting'):
                params['vehicle_counting'] = 'true'
                params['counting_line_position'] = str(kwargs.get('counting_line_position', 0.5))
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params:
                    params[key] = str(value)
            
            # Make request
            response = self._make_request(
                method='POST',
                endpoint='/api/v1/jobs/process/video',
                files=files,
                data=params,
                timeout=self.config['VIDEO_UPLOAD_TIMEOUT']
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Add server info to result
                result['submitted_to'] = self.base_url
                
                return result
            else:
                error_msg = f"Video job submission failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise FastAPIClientError(error_msg)
                
        except Exception as e:
            logger.error(f"Error in submit_video_job: {str(e)}")
            raise
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check status of a processing job.
        
        Args:
            job_id: Job ID returned by submit_video_job
        
        Returns:
            Dictionary with job status
        """
        try:
            response = self._make_request(
                method='GET',
                endpoint=f'/api/v1/jobs/{job_id}/status',
                timeout=self.config['JOB_STATUS_TIMEOUT']
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {
                    'status': 'error',
                    'message': f'Job {job_id} not found on processing server'
                }
            else:
                error_msg = f"Job status check failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'status': 'error',
                    'message': error_msg
                }
                
        except Exception as e:
            logger.error(f"Error in get_job_status: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def check_server_health(self) -> Dict[str, Any]:
        """
        Check if FastAPI server is healthy.
        
        Returns:
            Dictionary with health status
        """
        try:
            response = self._make_request(
                method='GET',
                endpoint='/health',
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'status': 'online',
                    'response': response.json()
                }
            else:
                return {
                    'healthy': False,
                    'status': 'error',
                    'response': response.text
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'healthy': False,
                'status': 'offline',
                'error': str(e)
            }
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available detection models on the server.
        
        Returns:
            List of model information dictionaries
        """
        try:
            response = self._make_request(
                method='GET',
                endpoint='/api/v1/models',
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get models: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting models: {str(e)}")
            return []
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a processing job.
        
        Args:
            job_id: Job ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        try:
            response = self._make_request(
                method='POST',
                endpoint=f'/api/v1/jobs/{job_id}/cancel',
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {str(e)}")
            return False

# Singleton instance for reuse
fastapi_client = FastAPIClient()