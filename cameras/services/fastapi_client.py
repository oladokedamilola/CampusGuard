# smart_surveillance/cameras/services/fastapi_client.py
import requests
import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO

logger = logging.getLogger(__name__)

class FastAPIClient:
    """
    Client for communicating with the FastAPI processing server.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'FASTAPI_BASE_URL', 'http://localhost:8001')
        self.api_key = getattr(settings, 'FASTAPI_API_KEY', 'a3f8e97b12c450d6f34a8921b567d0e9f12a34b5678c9d0e1f23a45b67c89d012')
        self.timeout = 30  # seconds
    
    def check_health(self) -> bool:
        """
        Check if FastAPI server is healthy.
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                headers={'X-API-Key': self.api_key},
                timeout=10
            )
            return response.status_code == 200 and response.json().get('healthy', False)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def process_image(self, image_file, detection_types: list = None) -> Optional[Dict]:
        """
        Process a single image through FastAPI.
        
        Args:
            image_file: Django File object or path to image
            detection_types: List of detection types ['person', 'vehicle', 'face']
        
        Returns:
            Dict with analysis results or None if failed
        """
        try:
            # Determine correct MIME type based on file extension
            if hasattr(image_file, 'name'):
                filename = image_file.name
                # Guess MIME type from filename
                if filename.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif filename.lower().endswith('.bmp'):
                    mime_type = 'image/bmp'
                else:
                    mime_type = 'image/jpeg'  # default
            else:
                filename = 'upload.jpg'
                mime_type = 'image/jpeg'
            
            # Read file content as binary
            if hasattr(image_file, 'read'):
                # It's a Django File object
                image_file.seek(0)  # Rewind to beginning
                file_content = image_file.read()
            elif hasattr(image_file, 'temporary_file_path'):
                # It's a TemporaryUploadedFile
                with open(image_file.temporary_file_path(), 'rb') as f:
                    file_content = f.read()
            elif isinstance(image_file, str):
                # It's a path
                with open(image_file, 'rb') as f:
                    file_content = f.read()
            else:
                # Assume it's already bytes
                file_content = image_file
            
            # Prepare files for upload - FIX: Use 'file' not 'image'
            files = {
                'file': (filename, file_content, mime_type)  # Changed from 'image' to 'file'
            }
            
            # Prepare parameters
            data = {}
            if detection_types:
                data['detection_types'] = ','.join(detection_types)
            
            # Send request with proper headers
            logger.info(f"Sending image to FastAPI at {self.base_url}/api/v1/process/image")
            logger.info(f"Using API key (first 10 chars): {self.api_key[:10]}...")
            logger.info(f"Sending file with key: 'file' (filename: {filename})")
            
            response = requests.post(
                f"{self.base_url}/api/v1/process/image",
                files=files,
                data=data,
                headers={'X-API-Key': self.api_key},
                timeout=self.timeout
            )
            
            logger.info(f"FastAPI response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Image processing failed: {response.status_code} - {response.text[:200]}")
                # Try to get more detailed error info
                try:
                    error_data = response.json()
                    logger.error(f"FastAPI error details: {error_data}")
                except:
                    pass
                return None
                
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return None
    
    def process_video(self, video_file, detection_types: list = None) -> Optional[Dict]:
        """
        Submit video for processing and get job ID.
        
        Args:
            video_file: Django File object or path to video
            detection_types: List of detection types
            
        Returns:
            Dict with job_id and status or None if failed
        """
        try:
            # Read file content properly
            if hasattr(video_file, 'read'):
                # It's a Django File object
                video_file.seek(0)  # Rewind to beginning
                file_content = video_file.read()
                filename = video_file.name if hasattr(video_file, 'name') else 'upload.mp4'
            elif hasattr(video_file, 'temporary_file_path'):
                # It's a TemporaryUploadedFile
                with open(video_file.temporary_file_path(), 'rb') as f:
                    file_content = f.read()
                filename = video_file.name if hasattr(video_file, 'name') else 'upload.mp4'
            elif isinstance(video_file, str):
                # It's a path
                with open(video_file, 'rb') as f:
                    file_content = f.read()
                filename = video_file.split('/')[-1] if isinstance(video_file, str) else 'upload.mp4'
            else:
                # Assume it's already bytes
                file_content = video_file
                filename = 'upload.mp4'
            
            # Prepare files for upload - FIX: Check what parameter FastAPI expects for video
            files = {
                'file': (filename, file_content, 'video/mp4')  # Changed from 'video' to 'file'
            }
            
            # Prepare parameters
            data = {}
            if detection_types:
                data['detection_types'] = ','.join(detection_types)
            
            # Send request
            logger.info(f"Sending video to FastAPI at {self.base_url}/api/v1/jobs/process/video")
            response = requests.post(
                f"{self.base_url}/api/v1/jobs/process/video",
                files=files,
                data=data,
                headers={'X-API-Key': self.api_key},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Video job submission failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting video job: {e}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Get status of a video processing job.
        
        Args:
            job_id: Job ID from process_video
            
        Returns:
            Dict with job status and progress
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/jobs/{job_id}/status",
                headers={'X-API-Key': self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Job status check failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error checking job status: {e}")
            return None
    
    def get_job_results(self, job_id: str) -> Optional[Dict]:
        """
        Get results of a completed job.
        
        Args:
            job_id: Job ID from process_video
            
        Returns:
            Dict with full analysis results
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/jobs/{job_id}/results",
                headers={'X-API-Key': self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Getting job results failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return None
    
    def get_available_models(self) -> Optional[list]:
        """
        Get list of available detection models.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/models",
                headers={'X-API-Key': self.api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('models', [])
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return None
    
    def advanced_crowd_detection(self, image_file) -> Optional[Dict]:
        """
        Perform advanced crowd detection on image.
        """
        try:
            # Read file content
            if hasattr(image_file, 'read'):
                image_file.seek(0)
                file_content = image_file.read()
                filename = image_file.name if hasattr(image_file, 'name') else 'image.jpg'
            else:
                with open(image_file, 'rb') as f:
                    file_content = f.read()
                filename = image_file.split('/')[-1] if isinstance(image_file, str) else 'image.jpg'
            
            files = {
                'image': (filename, file_content, 'image/jpeg')
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/advanced/crowd-detection",
                files=files,
                headers={'X-API-Key': self.api_key},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error in crowd detection: {e}")
            return None