# smart_surveillance/surveillance/views.py
"""
Views for video processing and analysis.
"""
import os
import tempfile
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
import logging
from .processing.lightweight import SimpleVideoProcessor
from incidents.models import Incident
from cameras.models import Camera, VideoFile
from django.urls import reverse

logger = logging.getLogger(__name__)

"""
Views for video and image processing with FastAPI integration.
"""
import os
import tempfile
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db import transaction

from core.utils.fastapi_client import fastapi_client, FastAPIClientError
from surveillance.models import ImageProcessingResult, VideoProcessingJob
from surveillance.services.job_monitor import check_job_status
from incidents.models import Incident
from cameras.models import Camera, VideoFile

@login_required
def process_image_view(request):
    """Process uploaded image with FastAPI server."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to process images.'))
        return redirect('cameras:list')
    
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
        # Validate file size (max 10MB for free tier)
        if image_file.size > 10 * 1024 * 1024:
            messages.error(request, _('Image file too large. Maximum size is 10MB.'))
            return redirect('surveillance:process_image')
        
        try:
            # Get processing parameters from form
            confidence = float(request.POST.get('confidence', 0.5))
            detection_types = request.POST.get('detection_types', 'person,vehicle,face')
            return_image = request.POST.get('return_image', 'false') == 'true'
            advanced = request.POST.get('advanced', 'false') == 'true'
            
            # Process image with FastAPI
            result = fastapi_client.process_image(
                image_file,
                confidence=confidence,
                detection_types=detection_types,
                return_image=return_image,
                advanced=advanced
            )
            
            # Save result to database
            with transaction.atomic():
                processed = ImageProcessingResult.objects.create(
                    user=request.user,
                    original_filename=image_file.name,
                    file_size=image_file.size,
                    mime_type=image_file.content_type,
                    job_id=result.get('job_id', f"img_{timezone.now().timestamp()}"),
                    processing_server='fastapi',
                    server_url=result.get('server_url', ''),
                    processing_time=result.get('processing_time'),
                    detection_count=result.get('detection_count', 0),
                    image_size=result.get('image_size', ''),
                    detections=result.get('detections', []),
                    detection_summary=result.get('detection_summary', {}),
                    processed_image_url=result.get('processed_image_url', ''),
                    confidence_threshold=confidence,
                    detection_types=detection_types,
                    status='completed',
                    completed_at=timezone.now()
                )
            
            # Create incident if significant detections found
            significant_detections = [
                d for d in result.get('detections', []) 
                if d.get('confidence', 0) > 0.7
            ]
            
            if significant_detections:
                # Try to get camera from form or use default
                camera_id = request.POST.get('camera')
                camera = None
                if camera_id:
                    try:
                        camera = Camera.objects.get(id=camera_id, is_active=True)
                    except Camera.DoesNotExist:
                        pass
                
                # Create incident
                incident = Incident.objects.create(
                    title=f"Image Analysis: {len(significant_detections)} detections",
                    description=f"Image analysis detected {len(significant_detections)} objects in {image_file.name}",
                    incident_type='person' if any(d.get('label') == 'person' 
                                                for d in significant_detections) else 'other',
                    severity='high' if len(significant_detections) > 5 else 'medium',
                    status='detected',
                    camera=camera,
                    evidence_image=image_file,  # Store original image as evidence
                    detected_at=timezone.now(),
                    assigned_to=request.user if request.user.can_acknowledge_incidents() else None,
                    location_description=request.POST.get('location', 'Uploaded image analysis'),
                    confidence_score=max(d.get('confidence', 0) 
                                       for d in significant_detections),
                    detection_metadata={
                        'detections': significant_detections,
                        'processing_result_id': processed.id,
                        'total_detections': len(result.get('detections', [])),
                        'image_size': result.get('image_size')
                    }
                )
                
                messages.success(request, 
                    _(f'✅ Image processed successfully! Created incident {incident.incident_id} with {len(significant_detections)} significant detections.')
                )
                return redirect('incidents:detail', pk=incident.pk)
            else:
                messages.success(request, 
                    _(f'✅ Image processed successfully! Found {processed.detection_count} detections.')
                )
                return render(request, 'surveillance/image_results.html', {
                    'result': processed,
                    'detections': processed.detections,
                })
            
        except FastAPIClientError as e:
            messages.error(request, _(f'Processing server error: {str(e)}'))
            logger.error(f"FastAPI client error: {str(e)}")
        except Exception as e:
            messages.error(request, _(f'Error processing image: {str(e)}'))
            logger.error(f"Image processing error: {str(e)}")
    
    # GET request or form error
    cameras = Camera.objects.filter(is_active=True)[:10]
    return render(request, 'surveillance/process_image.html', {
        'cameras': cameras,
        'fastapi_available': _check_fastapi_available(),
    })

@login_required
def process_video_view(request, video_id=None):
    """Process uploaded video with FastAPI server."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to process videos.'))
        return redirect('cameras:list')
    
    if video_id:
        # Process existing video from database
        return _process_existing_video(request, video_id)
    
    if request.method == 'POST' and request.FILES.get('video'):
        return _submit_new_video_job(request)
    
    # GET request - show upload form
    cameras = Camera.objects.filter(is_active=True)[:10]
    return render(request, 'surveillance/process_video.html', {
        'cameras': cameras,
        'fastapi_available': _check_fastapi_available(),
    })

def _process_existing_video(request, video_id):
    """Process existing video from database."""
    video = get_object_or_404(VideoFile, pk=video_id, uploaded_by=request.user)
    
    # Check if already processed
    existing_jobs = VideoProcessingJob.objects.filter(
        original_filename=video.video_file.name
    ).exclude(status='failed').order_by('-submitted_at')
    
    if existing_jobs.exists():
        latest_job = existing_jobs.first()
        messages.info(request, 
            _(f'Video already processed (status: {latest_job.get_status_display()}).')
        )
        return redirect('surveillance:video_job_status', job_id=latest_job.job_id)
    
    try:
        # Submit video for processing
        result = _submit_video_for_processing(
            request,
            video.video_file,
            video.title,
            video.description
        )
        
        messages.success(request, 
            _(f'✅ Video submitted for processing! Job ID: {result["job_id"]}')
        )
        return redirect('surveillance:video_job_status', job_id=result['job_id'])
        
    except Exception as e:
        messages.error(request, _(f'Error submitting video: {str(e)}'))
        return redirect('cameras:video_detail', pk=video.pk)

def _submit_new_video_job(request):
    """Submit new video for processing."""
    video_file = request.FILES['video']
    
    # Validate file size
    if video_file.size > 50 * 1024 * 1024:  # 50MB max
        messages.error(request, _('Video file too large. Maximum size is 50MB.'))
        return redirect('surveillance:process_video')
    
    try:
        # Get processing parameters
        title = request.POST.get('title', f"Uploaded video {timezone.now().strftime('%Y%m%d_%H%M%S')}")
        description = request.POST.get('description', '')
        
        # Submit video for processing
        result = _submit_video_for_processing(
            request,
            video_file,
            title,
            description
        )
        
        messages.success(request, 
            _(f'✅ Video submitted for processing! Job ID: {result["job_id"]}. '
              f'You will be notified when processing is complete.')
        )
        return redirect('surveillance:video_job_status', job_id=result['job_id'])
        
    except FastAPIClientError as e:
        messages.error(request, _(f'Processing server error: {str(e)}'))
        logger.error(f"FastAPI client error: {str(e)}")
    except Exception as e:
        messages.error(request, _(f'Error submitting video: {str(e)}'))
        logger.error(f"Video submission error: {str(e)}")
    
    return redirect('surveillance:process_video')

def _submit_video_for_processing(request, video_file, title, description):
    """
    Submit video to FastAPI for processing.
    
    Returns:
        Dictionary with job information
    """
    # Get processing parameters from form
    confidence = float(request.POST.get('confidence', 0.5))
    frame_sample_rate = int(request.POST.get('frame_sample_rate', 5))
    analyze_motion = request.POST.get('analyze_motion', 'true') == 'true'
    summary_only = request.POST.get('summary_only', 'true') == 'true'
    advanced = request.POST.get('advanced', 'false') == 'true'
    priority = int(request.POST.get('priority', 1))
    
    # Advanced features
    crowd_detection = request.POST.get('crowd_detection', 'false') == 'true'
    min_people_count = int(request.POST.get('min_people_count', 3))
    vehicle_counting = request.POST.get('vehicle_counting', 'false') == 'true'
    counting_line_position = float(request.POST.get('counting_line_position', 0.5))
    
    # Submit to FastAPI
    result = fastapi_client.submit_video_job(
        video_file,
        confidence=confidence,
        frame_sample_rate=frame_sample_rate,
        analyze_motion=analyze_motion,
        summary_only=summary_only,
        advanced=advanced,
        priority=priority,
        crowd_detection=crowd_detection,
        min_people_count=min_people_count,
        vehicle_counting=vehicle_counting,
        counting_line_position=counting_line_position,
    )
    
    # Save job to database
    with transaction.atomic():
        job = VideoProcessingJob.objects.create(
            user=request.user,
            job_id=result['job_id'],
            internal_id=f"VID-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
            original_filename=video_file.name,
            file_size=video_file.size,
            mime_type=video_file.content_type,
            confidence_threshold=confidence,
            frame_sample_rate=frame_sample_rate,
            analyze_motion=analyze_motion,
            summary_only=summary_only,
            crowd_detection=crowd_detection,
            min_people_count=min_people_count,
            vehicle_counting=vehicle_counting,
            counting_line_position=counting_line_position,
            processing_server='fastapi',
            server_url=result.get('submitted_to', ''),
            status='submitted',
            priority=priority,
            submitted_at=timezone.now(),
            message=result.get('message', 'Job submitted')
        )
    
    return {
        'job_id': job.job_id,
        'job': job,
        'result': result
    }

@login_required
def video_job_status_view(request, job_id):
    """View status of a video processing job."""
    job = get_object_or_404(VideoProcessingJob, job_id=job_id)
    
    # Check if user has permission to view this job
    if job.user != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to view this job.'))
        return redirect('surveillance:process_video')
    
    # Check job status with FastAPI if it's still active
    if job.is_active:
        try:
            status_data = fastapi_client.get_job_status(job_id)
            if status_data.get('status') != 'error':
                job.update_from_fastapi_status(status_data)
        except Exception as e:
            logger.warning(f"Could not update job status from FastAPI: {str(e)}")
    
    # Get related incidents
    related_incidents = job.related_incidents.all().order_by('-detected_at')
    
    return render(request, 'surveillance/video_job_status.html', {
        'job': job,
        'related_incidents': related_incidents,
        'is_active': job.is_active,
        'refresh_interval': 10 if job.is_active else 0,  # Auto-refresh if active
    })

@login_required
def video_job_status_json(request, job_id):
    """Get JSON status of a video processing job (for AJAX)."""
    job = get_object_or_404(VideoProcessingJob, job_id=job_id)
    
    # Check if user has permission
    if job.user != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check job status with FastAPI if it's still active
    if job.is_active:
        try:
            status_data = fastapi_client.get_job_status(job_id)
            if status_data.get('status') != 'error':
                job.update_from_fastapi_status(status_data)
        except Exception as e:
            logger.warning(f"Could not update job status from FastAPI: {str(e)}")
    
    return JsonResponse({
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'submitted_at': job.submitted_at.isoformat() if job.submitted_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'is_active': job.is_active,
        'error': job.error,
        'summary': job.summary,
    })

@login_required
def cancel_video_job(request, job_id):
    """Cancel a video processing job."""
    job = get_object_or_404(VideoProcessingJob, job_id=job_id)
    
    # Check if user has permission
    if job.user != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to cancel this job.'))
        return redirect('surveillance:video_job_status', job_id=job_id)
    
    # Check if job can be cancelled
    if not job.is_active:
        messages.warning(request, _(f'Job cannot be cancelled (status: {job.get_status_display()}).'))
        return redirect('surveillance:video_job_status', job_id=job_id)
    
    try:
        # Try to cancel on FastAPI server
        cancelled = fastapi_client.cancel_job(job_id)
        
        if cancelled:
            job.status = 'cancelled'
            job.message = 'Job cancelled by user'
            job.save()
            messages.success(request, _('✅ Job cancelled successfully.'))
        else:
            messages.warning(request, _('Could not cancel job on processing server.'))
            
    except Exception as e:
        messages.error(request, _(f'Error cancelling job: {str(e)}'))
    
    return redirect('surveillance:video_job_status', job_id=job_id)

@login_required
def demo_camera_view(request):
    """Demo camera view (simulated for free tier)."""
    context = {
        'cameras': Camera.objects.filter(is_active=True)[:4],
        'fastapi_available': _check_fastapi_available(),
        'fastapi_url': settings.FASTAPI_BASE_URL,
    }
    return render(request, 'surveillance/demo_camera.html', context)

@login_required
def analyze_camera_feed(request, camera_id):
    """Analyze a snapshot from camera feed."""
    camera = get_object_or_404(Camera, pk=camera_id)
    
    if not camera.is_active:
        messages.error(request, _(f'Camera {camera.name} is not active.'))
        return redirect('surveillance:demo_camera')
    
    # This is a placeholder - in a real implementation, 
    # we would capture a frame from the camera stream
    # For now, we'll redirect to image upload with camera pre-selected
    
    messages.info(request, 
        _('To analyze camera feed, please upload a screenshot from the camera. '
          'Real-time analysis requires camera integration setup.')
    )
    return redirect(f"{reverse('surveillance:process_image')}?camera={camera_id}")

@login_required
def api_process_frame(request):
    """API endpoint to process a single frame (AJAX)."""
    if not request.user.can_manage_cameras():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST' and request.FILES.get('frame'):
        frame_file = request.FILES['frame']
        
        try:
            # Process with FastAPI
            result = fastapi_client.process_image(
                frame_file,
                confidence=0.5,
                return_image=False
            )
            
            # Return JSON response
            return JsonResponse({
                'success': True,
                'detections': result.get('detections', []),
                'detection_count': result.get('detection_count', 0),
                'processing_time': result.get('processing_time', 0),
                'image_size': result.get('image_size', ''),
            })
            
        except FastAPIClientError as e:
            return JsonResponse({'error': str(e)}, status=500)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'No frame provided'}, status=400)

@login_required
def fastapi_health_check(request):
    """Check FastAPI server health."""
    try:
        health = fastapi_client.check_server_health()
        models = fastapi_client.get_available_models()
        
        return JsonResponse({
            'fastapi_health': health,
            'available_models': models,
            'config': {
                'base_url': fastapi_client.base_url,
                'timeout': fastapi_client.config['REQUEST_TIMEOUT'],
            }
        })
    except Exception as e:
        return JsonResponse({
            'fastapi_health': {
                'healthy': False,
                'status': 'error',
                'error': str(e)
            },
            'available_models': [],
        })

def _check_fastapi_available():
    """Check if FastAPI server is available."""
    try:
        health = fastapi_client.check_server_health()
        return health.get('healthy', False)
    except:
        return False








# Old views for processing images and videos
@login_required
def process_image_view(request):
    """Process uploaded image."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to process images.'))
        return redirect('cameras:list')
    
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
        # Validate file size (max 10MB for free tier)
        if image_file.size > 10 * 1024 * 1024:
            messages.error(request, _('Image file too large. Maximum size is 10MB.'))
            return redirect('surveillance:process_image')
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            for chunk in image_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        try:
            # Process image
            processor = SimpleVideoProcessor()
            result = processor.process_image(tmp_path)
            
            # Create incident for significant detections
            if result['detections']:
                # Find most relevant detection
                significant_detections = [d for d in result['detections'] 
                                         if d.get('confidence', 0) > 0.7]
                
                if significant_detections:
                    # Create incident
                    incident = Incident.objects.create(
                        title=f"Image Analysis: {len(significant_detections)} detections",
                        description=f"Image analysis detected {len(significant_detections)} objects.",
                        incident_type='person' if any(d.get('label') == 'person' 
                                                    for d in significant_detections) else 'other',
                        severity='medium' if len(significant_detections) > 0 else 'low',
                        status='detected',
                        evidence_image=result['processed_image'],
                        detected_at=timezone.now(),
                        assigned_to=request.user if request.user.can_acknowledge_incidents() else None,
                        location_description="Uploaded image analysis",
                        confidence_score=max(d.get('confidence', 0) 
                                           for d in significant_detections),
                        detection_metadata={
                            'detections': significant_detections,
                            'analysis_time': result['analysis_time'],
                            'total_detections': len(result['detections'])
                        }
                    )
                    
                    messages.success(request, 
                        _(f'Image processed! Created incident {incident.incident_id} with {len(significant_detections)} detections.')
                    )
                    return redirect('incidents:detail', pk=incident.pk)
            
            # No significant detections, just show results
            context = {
                'result': result,
                'image_url': default_storage.url(result['processed_image'].name),
                'detections': result['detections'],
            }
            
            return render(request, 'surveillance/image_results.html', context)
            
        except Exception as e:
            messages.error(request, _(f'Error processing image: {str(e)}'))
            logger.error(f"Image processing error: {str(e)}")
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    return render(request, 'surveillance/process_image.html')

@login_required
def process_video_view(request, video_id=None):
    """Process uploaded video or camera stream."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to process videos.'))
        return redirect('cameras:list')
    
    if video_id:
        # Process existing video from database
        video = get_object_or_404(VideoFile, pk=video_id, uploaded_by=request.user)
        
        # Check if already processed
        if video.processing_status != 'pending':
            messages.info(request, _(f'Video already processed (status: {video.get_processing_status_display()}).'))
            return redirect('cameras:video_detail', pk=video.pk)
        
        # Update status
        video.processing_status = 'processing'
        video.processing_started = timezone.now()
        video.save()
        
        try:
            # Process video
            processor = SimpleVideoProcessor()
            result = processor.process_video(video.video_file.path, sample_every=15)
            
            # Update video record
            video.processing_status = 'completed'
            video.processing_completed = timezone.now()
            video.total_frames = result['summary']['total_frames']
            video.processed_frames = result['summary']['processed_frames']
            video.detection_count = result['summary']['total_detections']
            video.results_json = {
                'summary': result['summary'],
                'detections_by_frame': {
                    str(k): v for k, v in result['detections_by_frame'].items()
                },
                'motion_events': result['motion_events'],
                'sample_frames_count': len(result['sample_frames'])
            }
            
            # Save sample frames
            for i, sample in enumerate(result['sample_frames']):
                frame_field = f'sample_frame_{i+1}'
                if hasattr(video, frame_field):
                    getattr(video, frame_field).save(
                        sample['image'].name,
                        sample['image'],
                        save=False
                    )
            
            video.save()
            
            # Create incidents for significant events
            incidents_created = 0
            motion_event_count = len(result['motion_events'])
            
            if motion_event_count > 0:
                # Create incident for motion detection
                incident = Incident.objects.create(
                    title=f"Video Analysis: {motion_event_count} motion events",
                    description=f"Video analysis detected {motion_event_count} motion events with {result['summary']['total_detections']} total detections.",
                    incident_type='motion',
                    severity='high' if motion_event_count > 10 else 'medium',
                    status='detected',
                    video_file=video,
                    detected_at=timezone.now(),
                    assigned_to=request.user if request.user.can_acknowledge_incidents() else None,
                    location_description=f"Uploaded video: {video.title}",
                    confidence_score=0.8 if motion_event_count > 0 else 0.3,
                    detection_metadata={
                        'motion_events': motion_event_count,
                        'total_detections': result['summary']['total_detections'],
                        'analysis_time': result['analysis_time'],
                        'video_duration': result['summary']['duration']
                    }
                )
                incidents_created += 1
            
            messages.success(request, 
                _(f'Video processed successfully! Found {result["summary"]["total_detections"]} detections, '
                  f'{motion_event_count} motion events. Created {incidents_created} incidents.')
            )
            
            return redirect('cameras:video_detail', pk=video.pk)
            
        except Exception as e:
            video.processing_status = 'failed'
            video.save()
            messages.error(request, _(f'Error processing video: {str(e)}'))
            logger.error(f"Video processing error: {str(e)}")
            return redirect('cameras:video_detail', pk=video.pk)
    
    return render(request, 'surveillance/process_video.html')

@login_required
def demo_camera_view(request):
    """Demo camera view (simulated for free tier)."""
    context = {
        'cameras': Camera.objects.filter(is_active=True)[:4],  # Limit for demo
    }
    return render(request, 'surveillance/demo_camera.html', context)

@login_required
def analyze_camera_feed(request, camera_id):
    """Analyze a snapshot from camera feed (simulated for free tier)."""
    camera = get_object_or_404(Camera, pk=camera_id)
    
    if not camera.is_active:
        messages.error(request, _(f'Camera {camera.name} is not active.'))
        return redirect('surveillance:demo_camera')
    
    # Simulate capturing a frame (in real implementation, would connect to RTSP)
    # For free tier demo, we'll use a placeholder
    
    context = {
        'camera': camera,
        'simulated': True,
        'message': _('Camera analysis simulated for demo. On production with proper hosting, this would connect to actual camera feed.')
    }
    
    return render(request, 'surveillance/camera_analysis.html', context)

@login_required
def api_process_frame(request):
    """API endpoint to process a single frame (AJAX)."""
    if not request.user.can_manage_cameras():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST' and request.FILES.get('frame'):
        frame_file = request.FILES['frame']
        
        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            for chunk in frame_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        try:
            processor = SimpleVideoProcessor()
            result = processor.process_image(tmp_path)
            
            # Return JSON response
            detections = []
            for det in result['detections']:
                detections.append({
                    'bbox': det['bbox'],
                    'label': det['label'],
                    'confidence': det.get('confidence', 0),
                    'type': det.get('type', 'unknown')
                })
            
            return JsonResponse({
                'success': True,
                'detections': detections,
                'detection_count': len(detections),
                'analysis_time': result['analysis_time']
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    return JsonResponse({'error': 'No frame provided'}, status=400)



@login_required
def analysis_result_detail(request, result_id):
    """View detailed analysis result."""
    result = get_object_or_404(ImageProcessingResult, id=result_id)
    
    # Check permission
    if result.user != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to view this result.'))
        return redirect('surveillance:processing_results')
    
    return render(request, 'surveillance/analysis_result_detail.html', {
        'result': result,
        'detections': result.detections,
    })