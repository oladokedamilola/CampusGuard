# cameras/tasks.py
import os
from django.utils import timezone
from celery import shared_task
from .models import VideoFile

@shared_task
def process_video_task(video_id, processing_config):
    """
    Background task to process video with OpenCV.
    This will be fully implemented in Phase 4.
    """
    try:
        video = VideoFile.objects.get(pk=video_id)
        video.processing_status = VideoFile.ProcessingStatus.PROCESSING
        video.processing_started = timezone.now()
        video.save()
        
        # TODO: In Phase 4, implement:
        # 1. OpenCV video capture
        # 2. Motion/object detection
        # 3. Save results to video.results_json
        # 4. Generate output video with annotations
        
        # Simulate processing for now
        import time
        import random
        
        video.total_frames = 1000  # Simulated
        for i in range(1, 101):  # 10% increments
            time.sleep(0.5)  # Simulate processing time
            video.processed_frames = i * 10
            video.detection_count = random.randint(0, i * 2)
            video.save()
        
        # Mark as completed
        video.processing_status = VideoFile.ProcessingStatus.COMPLETED
        video.processing_completed = timezone.now()
        video.detection_count = random.randint(50, 200)
        video.results_json = {
            'detections': [
                {
                    'type': 'person',
                    'count': random.randint(10, 50),
                    'timestamps': [random.uniform(0, 300) for _ in range(10)]
                },
                {
                    'type': 'vehicle',
                    'count': random.randint(5, 20),
                    'timestamps': [random.uniform(0, 300) for _ in range(5)]
                }
            ],
            'motion_zones': [
                {'x1': 100, 'y1': 100, 'x2': 300, 'y2': 300, 'activity': 'high'},
                {'x1': 400, 'y1': 200, 'x2': 600, 'y2': 400, 'activity': 'medium'},
            ],
            'processing_time': random.uniform(30, 120),
        }
        video.save()
        
        return f"Video {video_id} processed successfully"
    
    except VideoFile.DoesNotExist:
        return f"Video {video_id} not found"
    except Exception as e:
        # Update status to failed
        VideoFile.objects.filter(pk=video_id).update(
            processing_status=VideoFile.ProcessingStatus.FAILED
        )
        return f"Error processing video {video_id}: {str(e)}"