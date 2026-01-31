"""
Lightweight computer vision for PythonAnywhere free tier.
"""
import cv2
import numpy as np
import os
import time
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
import io
import logging

logger = logging.getLogger(__name__)

class LightweightDetector:
    """Lightweight detection suitable for PythonAnywhere free tier."""
    
    def __init__(self):
        self.models_loaded = False
        self.face_cascade = None
        self.hog = None
        
    def load_models(self):
        """Load lightweight models."""
        try:
            # Haar Cascade for face detection (built into OpenCV)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(cascade_path):
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
                logger.info("Loaded Haar Cascade face detector")
            
            # HOG (Histogram of Oriented Gradients) for person detection
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            logger.info("Loaded HOG person detector")
            
            self.models_loaded = True
            return True
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            return False
    
    def detect_motion(self, frame1, frame2, threshold=30):
        """
        Simple frame differencing motion detection.
        
        Args:
            frame1: Previous frame
            frame2: Current frame
            threshold: Motion threshold
        
        Returns:
            motion_detected: Boolean
            motion_mask: Motion regions
        """
        if frame1 is None or frame2 is None:
            return False, None
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        gray1 = cv2.GaussianBlur(gray1, (21, 21), 0)
        gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
        
        # Compute absolute difference
        frame_diff = cv2.absdiff(gray1, gray2)
        
        # Apply threshold
        _, thresh = cv2.threshold(frame_diff, threshold, 255, cv2.THRESH_BINARY)
        
        # Dilate to fill gaps
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check if any contour is large enough
        motion_detected = False
        motion_regions = []
        
        for contour in contours:
            if cv2.contourArea(contour) < 500:  # Minimum area
                continue
            
            motion_detected = True
            x, y, w, h = cv2.boundingRect(contour)
            motion_regions.append((x, y, w, h))
        
        return motion_detected, motion_regions
    
    def detect_faces(self, frame, scale_factor=1.1, min_neighbors=5):
        """Detect faces using Haar Cascade."""
        if not self.models_loaded or self.face_cascade is None:
            return []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=scale_factor,
            minNeighbors=min_neighbors,
            minSize=(30, 30)
        )
        
        detections = []
        for (x, y, w, h) in faces:
            detections.append({
                'bbox': [x, y, x+w, y+h],
                'label': 'person',
                'confidence': 0.8,  # Estimated
                'type': 'face'
            })
        
        return detections
    
    def detect_people(self, frame):
        """Detect people using HOG."""
        if not self.models_loaded or self.hog is None:
            return []
        
        # Resize for faster processing if image is large
        if frame.shape[1] > 800:
            scale = 800 / frame.shape[1]
            new_width = 800
            new_height = int(frame.shape[0] * scale)
            frame_resized = cv2.resize(frame, (new_width, new_height))
        else:
            frame_resized = frame
            scale = 1.0
        
        # Detect people
        (rects, weights) = self.hog.detectMultiScale(
            frame_resized,
            winStride=(4, 4),
            padding=(8, 8),
            scale=1.05
        )
        
        detections = []
        for i, (x, y, w, h) in enumerate(rects):
            # Scale back if resized
            if scale != 1.0:
                x, y, w, h = int(x/scale), int(y/scale), int(w/scale), int(h/scale)
            
            confidence = float(weights[i]) if i < len(weights) else 0.5
            detections.append({
                'bbox': [x, y, x+w, y+h],
                'label': 'person',
                'confidence': min(confidence, 0.95),
                'type': 'person'
            })
        
        return detections
    
    def detect_objects_simple(self, frame, min_size=50):
        """
        Simple object detection using contour analysis.
        Good for abandoned objects, vehicles (blobs).
        """
        # Convert to grayscale and blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # Edge detection
        edges = cv2.Canny(blurred, 30, 150)
        
        # Dilate to close gaps
        edges = cv2.dilate(edges, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_size * min_size:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            # Classify by aspect ratio and size
            aspect_ratio = w / h if h > 0 else 0
            
            if 0.8 < aspect_ratio < 1.2 and area > 10000:
                label = "vehicle"
            elif area > 5000:
                label = "object"
            else:
                label = "small_object"
            
            detections.append({
                'bbox': [x, y, x+w, y+h],
                'label': label,
                'confidence': 0.6,
                'type': 'object',
                'area': area
            })
        
        return detections

class SimpleVideoProcessor:
    """
    Simplified video processor for PythonAnywhere.
    Processes short videos (< 30 seconds) or images.
    """
    
    def __init__(self, max_duration=30, max_frames=900):  # 30 seconds at 30fps
        self.max_duration = max_duration
        self.max_frames = max_frames
        self.detector = LightweightDetector()
        self.detector.load_models()
        
    def process_image(self, image_path):
        """
        Process a single image.
        
        Returns:
            {
                'detections': [...],
                'processed_image': Django File,
                'analysis_time': seconds
            }
        """
        start_time = time.time()
        
        # Read image
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")
        
        # Run all detectors
        all_detections = []
        
        # Detect faces
        faces = self.detector.detect_faces(frame)
        all_detections.extend(faces)
        
        # Detect people
        people = self.detector.detect_people(frame)
        all_detections.extend(people)
        
        # Detect objects
        objects = self.detector.detect_objects_simple(frame)
        all_detections.extend(objects)
        
        # Draw detections
        result_frame = frame.copy()
        for det in all_detections:
            x1, y1, x2, y2 = det['bbox']
            label = det['label']
            confidence = det.get('confidence', 0)
            
            # Choose color based on label
            if label == 'person' or det.get('type') == 'face':
                color = (0, 255, 0)  # Green for people
            elif label == 'vehicle':
                color = (255, 0, 0)  # Blue for vehicles
            else:
                color = (0, 165, 255)  # Orange for objects
            
            # Draw rectangle
            cv2.rectangle(result_frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label_text = f"{label} {confidence:.0%}"
            cv2.putText(result_frame, label_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Convert to Django File
        success, buffer = cv2.imencode('.jpg', result_frame)
        if not success:
            raise ValueError("Could not encode image")
        
        image_data = io.BytesIO(buffer)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"processed_{timestamp}.jpg"
        django_file = ContentFile(image_data.getvalue(), name=filename)
        
        analysis_time = time.time() - start_time
        
        return {
            'detections': all_detections,
            'processed_image': django_file,
            'analysis_time': analysis_time,
            'detection_count': len(all_detections),
            'image_size': f"{frame.shape[1]}x{frame.shape[0]}"
        }
    
    def process_video(self, video_path, sample_every=10):
        """
        Process a video file (limited duration).
        
        Args:
            video_path: Path to video file
            sample_every: Process every Nth frame (for speed)
        
        Returns:
            {
                'detections_by_frame': {frame_num: [...]},
                'summary': {...},
                'sample_frames': [...],
                'analysis_time': seconds
            }
        """
        start_time = time.time()
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Get video info
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Limit frames for free tier
        if total_frames > self.max_frames:
            total_frames = self.max_frames
        
        detections_by_frame = {}
        sample_frames = []
        frame_count = 0
        
        prev_frame = None
        motion_events = []
        
        while frame_count < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process every Nth frame
            if frame_count % sample_every == 0:
                # Detect motion if we have previous frame
                if prev_frame is not None:
                    motion_detected, motion_regions = self.detector.detect_motion(
                        prev_frame, frame
                    )
                    
                    if motion_detected:
                        motion_events.append({
                            'frame': frame_count,
                            'regions': motion_regions,
                            'timestamp': frame_count / fps if fps > 0 else 0
                        })
                
                # Run object detection
                detections = []
                
                # Detect people
                people = self.detector.detect_people(frame)
                detections.extend(people)
                
                # Detect faces
                faces = self.detector.detect_faces(frame)
                detections.extend(faces)
                
                if detections:
                    detections_by_frame[frame_count] = detections
                    
                    # Save sample frame with detections
                    if len(sample_frames) < 5:  # Keep only 5 sample frames
                        sample_frame = frame.copy()
                        for det in detections:
                            x1, y1, x2, y2 = det['bbox']
                            cv2.rectangle(sample_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # Save as Django File
                        success, buffer = cv2.imencode('.jpg', sample_frame)
                        if success:
                            image_data = io.BytesIO(buffer)
                            filename = f"frame_{frame_count:06d}.jpg"
                            django_file = ContentFile(image_data.getvalue(), name=filename)
                            sample_frames.append({
                                'frame': frame_count,
                                'image': django_file,
                                'detections': detections,
                                'timestamp': frame_count / fps if fps > 0 else 0
                            })
            
            prev_frame = frame.copy()
            frame_count += 1
            
            # Check timeout (max 30 seconds processing)
            if time.time() - start_time > 30:
                logger.warning(f"Video processing timeout at frame {frame_count}")
                break
        
        cap.release()
        
        # Generate summary
        total_detections = sum(len(dets) for dets in detections_by_frame.values())
        
        summary = {
            'total_frames': frame_count,
            'processed_frames': len(detections_by_frame),
            'total_detections': total_detections,
            'motion_events': len(motion_events),
            'fps': fps,
            'duration': frame_count / fps if fps > 0 else 0,
            'processing_time': time.time() - start_time
        }
        
        return {
            'detections_by_frame': detections_by_frame,
            'motion_events': motion_events,
            'sample_frames': sample_frames,
            'summary': summary,
            'analysis_time': time.time() - start_time
        }