# smart_surveillance/cameras/services/base64_processor.py
"""
Utility service for handling base64 encoding/decoding operations
for FastAPI integration.
"""
import base64
import imghdr
import logging
from io import BytesIO
from typing import Optional, Tuple, List, Dict, Any
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings

logger = logging.getLogger(__name__)

class Base64Processor:
    """
    Handles base64 encoding and decoding operations for media files.
    """
    
    @staticmethod
    def decode_base64_to_file(base64_string: str, file_name: str = None) -> Optional[ContentFile]:
        """
        Decode base64 string to Django ContentFile.
        
        Args:
            base64_string: Base64 encoded string (with or without data URI prefix)
            file_name: Optional file name for the ContentFile
        
        Returns:
            ContentFile object or None if decoding fails
        """
        try:
            # Clean base64 string (remove data URI prefix if present)
            if 'base64,' in base64_string:
                base64_string = base64_string.split('base64,')[1]
            
            # Decode base64
            file_data = base64.b64decode(base64_string)
            
            # Determine file name if not provided
            if not file_name:
                file_name = f"processed_{hash(base64_string[:100])}.jpg"
            
            return ContentFile(file_data, name=file_name)
            
        except Exception as e:
            logger.error(f"Error decoding base64 to file: {str(e)}")
            return None
    
    @staticmethod
    def encode_file_to_base64(file_path: str, include_data_uri: bool = False) -> Optional[str]:
        """
        Encode file to base64 string.
        
        Args:
            file_path: Path to the file
            include_data_uri: Whether to include data:image prefix
        
        Returns:
            Base64 encoded string or None if encoding fails
        """
        try:
            # Read file
            with default_storage.open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Encode to base64
            base64_string = base64.b64encode(file_data).decode('utf-8')
            
            # Add data URI prefix if requested
            if include_data_uri:
                # Try to determine MIME type
                mime_type = Base64Processor.detect_mime_type(file_data)
                if mime_type:
                    base64_string = f"data:{mime_type};base64,{base64_string}"
            
            return base64_string
            
        except Exception as e:
            logger.error(f"Error encoding file to base64: {str(e)}")
            return None
    
    @staticmethod
    def detect_mime_type(file_data: bytes) -> Optional[str]:
        """
        Detect MIME type from file data.
        
        Args:
            file_data: Raw file bytes
        
        Returns:
            MIME type string or None if detection fails
        """
        try:
            # Detect image type
            image_type = imghdr.what(None, file_data)
            if image_type:
                return f"image/{image_type}"
            
            # Add more MIME type detection logic here as needed
            # For now, return None for non-images
            return None
            
        except Exception as e:
            logger.error(f"Error detecting MIME type: {str(e)}")
            return None
    
    @staticmethod
    def is_valid_base64(base64_string: str) -> bool:
        """
        Check if string is valid base64.
        
        Args:
            base64_string: String to validate
        
        Returns:
            True if valid base64, False otherwise
        """
        try:
            # Clean data URI prefix if present
            if 'base64,' in base64_string:
                base64_string = base64_string.split('base64,')[1]
            
            # Try to decode
            base64.b64decode(base64_string)
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def save_base64_image(base64_string: str, upload_path: str, file_extension: str = '.jpg') -> Optional[str]:
        """
        Save base64 image to storage.
        
        Args:
            base64_string: Base64 encoded image
            upload_path: Path to save the image (relative to MEDIA_ROOT)
            file_extension: File extension (.jpg, .png, etc.)
        
        Returns:
            Saved file path or None if save fails
        """
        try:
            # Decode base64
            content_file = Base64Processor.decode_base64_to_file(base64_string)
            if not content_file:
                return None
            
            # Generate file name
            import uuid
            file_name = f"{upload_path}/{uuid.uuid4().hex}{file_extension}"
            
            # Save to storage
            saved_path = default_storage.save(file_name, content_file)
            
            logger.info(f"Saved base64 image to: {saved_path}")
            return saved_path
            
        except Exception as e:
            logger.error(f"Error saving base64 image: {str(e)}")
            return None
    
    @staticmethod
    def extract_image_from_fastapi_response(response_data: Dict[str, Any], 
                                           field_name: str = 'processed_image_base64') -> Optional[str]:
        """
        Extract base64 image from FastAPI response.
        
        Args:
            response_data: FastAPI response dictionary
            field_name: Field name containing base64 image
        
        Returns:
            Base64 string or None if not found
        """
        try:
            # Check if field exists in response
            if field_name in response_data and response_data[field_name]:
                return response_data[field_name]
            
            # Try alternative field names
            alt_fields = ['image_base64', 'result_image', 'annotated_image', 'output_image']
            for alt_field in alt_fields:
                if alt_field in response_data and response_data[alt_field]:
                    return response_data[alt_field]
            
            # Check in nested structures
            if 'result' in response_data and isinstance(response_data['result'], dict):
                result = response_data['result']
                for field in [field_name] + alt_fields:
                    if field in result and result[field]:
                        return result[field]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting image from FastAPI response: {str(e)}")
            return None
    
    @staticmethod
    def extract_key_frames_from_fastapi_response(response_data: Dict[str, Any]) -> List[str]:
        """
        Extract key frames from FastAPI video processing response.
        
        Args:
            response_data: FastAPI response dictionary
        
        Returns:
            List of base64 encoded key frames
        """
        try:
            key_frames = []
            
            # Check for key_frames_base64 field
            if 'key_frames_base64' in response_data and response_data['key_frames_base64']:
                if isinstance(response_data['key_frames_base64'], list):
                    key_frames = response_data['key_frames_base64']
            
            # Try alternative field names
            alt_fields = ['key_frames', 'important_frames', 'summary_frames']
            for alt_field in alt_fields:
                if alt_field in response_data and response_data[alt_field]:
                    if isinstance(response_data[alt_field], list):
                        # Check if list contains base64 strings or dicts
                        for item in response_data[alt_field]:
                            if isinstance(item, str) and Base64Processor.is_valid_base64(item):
                                key_frames.append(item)
                            elif isinstance(item, dict) and 'base64' in item:
                                key_frames.append(item['base64'])
            
            # Check in nested structures
            if 'result' in response_data and isinstance(response_data['result'], dict):
                result = response_data['result']
                if 'key_frames_base64' in result and result['key_frames_base64']:
                    if isinstance(result['key_frames_base64'], list):
                        key_frames.extend(result['key_frames_base64'])
            
            return key_frames
            
        except Exception as e:
            logger.error(f"Error extracting key frames from FastAPI response: {str(e)}")
            return []
    
    @staticmethod
    def extract_summary_from_fastapi_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract analysis summary from FastAPI response.
        
        Args:
            response_data: FastAPI response dictionary
        
        Returns:
            Summary dictionary
        """
        try:
            summary = {}
            
            # Check for summary field
            if 'summary' in response_data and response_data['summary']:
                summary = response_data['summary']
            
            # Try alternative field names
            alt_fields = ['analysis_summary', 'results_summary', 'detection_summary']
            for alt_field in alt_fields:
                if alt_field in response_data and response_data[alt_field]:
                    summary.update(response_data[alt_field])
            
            # Extract detection counts if available
            if 'detections' in response_data and response_data['detections']:
                detections = response_data['detections']
                if isinstance(detections, list):
                    # Count by type
                    type_counts = {}
                    for detection in detections:
                        if isinstance(detection, dict):
                            label = detection.get('label') or detection.get('class') or 'unknown'
                            type_counts[label] = type_counts.get(label, 0) + 1
                    
                    if 'detection_counts' not in summary:
                        summary['detection_counts'] = type_counts
                    summary['total_detections'] = len(detections)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error extracting summary from FastAPI response: {str(e)}")
            return {}
    
    @staticmethod
    def process_fastapi_image_response(response_data: Dict[str, Any], 
                                      media_upload) -> Dict[str, Any]:
        """
        Process FastAPI image response and save base64 image.
        
        Args:
            response_data: FastAPI response dictionary
            media_upload: MediaUpload instance
        
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'message': '',
            'saved_path': None,
            'has_base64': False
        }
        
        try:
            # Extract base64 image
            base64_image = Base64Processor.extract_image_from_fastapi_response(response_data)
            
            if not base64_image:
                result['message'] = 'No base64 image found in response'
                return result
            
            # Validate base64
            if not Base64Processor.is_valid_base64(base64_image):
                result['message'] = 'Invalid base64 data'
                return result
            
            result['has_base64'] = True
            
            # Save to media_upload
            if media_upload.save_processed_file_from_base64(base64_image):
                result['success'] = True
                result['message'] = 'Processed image saved successfully'
                result['saved_path'] = media_upload.processed_file.path
                
                # Update analysis results if they exist
                if hasattr(media_upload, 'analysis_results'):
                    try:
                        media_upload.analysis_results.processed_image_base64 = base64_image
                        media_upload.analysis_results.save()
                    except Exception as e:
                        logger.error(f"Error updating analysis results: {str(e)}")
            else:
                result['message'] = 'Failed to save processed file'
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing FastAPI image response: {str(e)}")
            result['message'] = f'Processing error: {str(e)}'
            return result
    
    @staticmethod
    def process_fastapi_video_response(response_data: Dict[str, Any], 
                                      media_upload) -> Dict[str, Any]:
        """
        Process FastAPI video response and save key frames.
        
        Args:
            response_data: FastAPI response dictionary
            media_upload: MediaUpload instance
        
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'message': '',
            'key_frames_saved': 0,
            'has_summary': False,
            'has_key_frames': False
        }
        
        try:
            # Extract and save key frames
            key_frames = Base64Processor.extract_key_frames_from_fastapi_response(response_data)
            
            if key_frames:
                result['has_key_frames'] = True
                saved_paths = media_upload.save_key_frames_from_base64(key_frames)
                result['key_frames_saved'] = len(saved_paths)
                result['message'] = f'Saved {len(saved_paths)} key frames'
            
            # Extract and save summary
            summary = Base64Processor.extract_summary_from_fastapi_response(response_data)
            
            if summary:
                result['has_summary'] = True
                media_upload.analysis_summary = summary
                media_upload.save()
                
                # Update message
                if result['message']:
                    result['message'] += f' and analysis summary'
                else:
                    result['message'] = 'Saved analysis summary'
            
            # Check if we have either key frames or summary
            if result['has_key_frames'] or result['has_summary']:
                result['success'] = True
            else:
                result['message'] = 'No key frames or summary found in response'
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing FastAPI video response: {str(e)}")
            result['message'] = f'Processing error: {str(e)}'
            return result
    
    @staticmethod
    def create_data_url(base64_string: str, mime_type: str = 'image/jpeg') -> str:
        """
        Create data URL from base64 string.
        
        Args:
            base64_string: Base64 encoded string
            mime_type: MIME type for the data URL
        
        Returns:
            Data URL string
        """
        # Clean base64 if it already has data URI
        if 'base64,' in base64_string:
            base64_string = base64_string.split('base64,')[1]
        
        return f"data:{mime_type};base64,{base64_string}"
    
    @staticmethod
    def get_base64_size(base64_string: str) -> int:
        """
        Calculate approximate size of base64 data in bytes.
        
        Args:
            base64_string: Base64 encoded string
        
        Returns:
            Approximate size in bytes
        """
        try:
            # Clean data URI
            if 'base64,' in base64_string:
                base64_string = base64_string.split('base64,')[1]
            
            # Base64 uses 4 characters for every 3 bytes
            # Remove padding characters for accurate calculation
            padding = base64_string.count('=')
            clean_string = base64_string.rstrip('=')
            size = (len(clean_string) * 3) // 4
            
            return size
            
        except Exception:
            return 0

# Singleton instance for reuse
base64_processor = Base64Processor()