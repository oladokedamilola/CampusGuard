# smart_surveillance/cameras/views.py
"""
Views for camera management and media processing with FastAPI integration.
"""
import os
import json
import threading
import logging
import mimetypes
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from .models import Camera, CameraGroup, CameraHealthLog, MediaUpload, MediaAnalysisResult, VideoFile
from .forms import CameraForm, CameraGroupForm, CameraFilterForm, VideoUploadForm, VideoProcessingForm, MediaUploadForm
from core.models import Location
from .services.media_processor import MediaProcessor, media_processor
from .services.fastapi_client import FastAPIClient, fastapi_client
from .services.base64_processor import base64_processor

logger = logging.getLogger(__name__)

# ============================================
# CAMERA VIEWS (Existing functionality)
# ============================================

class CameraListView(LoginRequiredMixin, ListView):
    """List all cameras with filtering."""
    model = Camera
    template_name = 'cameras/camera_list.html'
    context_object_name = 'cameras'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Camera.objects.select_related('location').order_by('name')
        
        # Apply filters from form
        form = CameraFilterForm(self.request.GET)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            camera_type = form.cleaned_data.get('camera_type')
            location = form.cleaned_data.get('location')
            is_active = form.cleaned_data.get('is_active')
            search = form.cleaned_data.get('search')
            
            if status:
                queryset = queryset.filter(status=status)
            
            if camera_type:
                queryset = queryset.filter(camera_type=camera_type)
            
            if location:
                queryset = queryset.filter(location=location)
            
            if is_active:
                is_active_bool = is_active == 'true'
                queryset = queryset.filter(is_active=is_active_bool)
            
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(camera_id__icontains=search) |
                    Q(ip_address__icontains=search) |
                    Q(serial_number__icontains=search) |
                    Q(location__name__icontains=search)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = CameraFilterForm(self.request.GET)
        
        # Stats for dashboard
        context['total_cameras'] = Camera.objects.count()
        context['active_cameras'] = Camera.objects.filter(
            is_active=True, status='active'
        ).count()
        context['offline_cameras'] = Camera.objects.filter(
            status__in=['offline', 'error']
        ).count()
        
        return context

@login_required
def camera_list_functional(request):
    """List all cameras (functional view)."""
    cameras = Camera.objects.filter(is_active=True).order_by('name')
    
    # Check FastAPI server health
    fastapi_health = fastapi_client.check_health()
    
    context = {
        'cameras': cameras,
        'fastapi_healthy': fastapi_health.get('healthy', False),
        'fastapi_status': fastapi_health.get('status', 'unknown'),
    }
    return render(request, 'cameras/camera_list.html', context)

class CameraDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View camera details."""
    model = Camera
    template_name = 'cameras/camera_detail.html'
    context_object_name = 'camera'
    
    def test_func(self):
        """Check if user can view cameras."""
        return self.request.user.can_manage_cameras()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent health logs
        context['health_logs'] = self.object.health_logs.all()[:10]
        
        return context

@login_required
def camera_detail_functional(request, camera_id):
    """View camera details (functional view)."""
    camera = get_object_or_404(Camera, camera_id=camera_id)
    
    # Get recent incidents for this camera
    recent_incidents = camera.incidents.all().order_by('-detected_at')[:5]
    
    # Get health logs
    health_logs = camera.health_logs.all().order_by('-recorded_at')[:10]
    
    context = {
        'camera': camera,
        'recent_incidents': recent_incidents,
        'health_logs': health_logs,
    }
    return render(request, 'cameras/camera_detail.html', context)

class CameraCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new camera."""
    model = Camera
    form_class = CameraForm
    template_name = 'cameras/camera_form.html'
    success_url = reverse_lazy('cameras:list')
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(
            self.request,
            _(f'Camera "{self.object.name}" created successfully!')
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Camera')
        return context

@login_required
def camera_create_functional(request):
    """Create a new camera (functional view)."""
    if request.method == 'POST':
        form = CameraForm(request.POST)
        if form.is_valid():
            camera = form.save(commit=False)
            camera.save()
            messages.success(request, f'Camera "{camera.name}" created successfully!')
            return redirect('cameras:camera_detail_functional', camera_id=camera.camera_id)
    else:
        form = CameraForm()
    
    context = {'form': form}
    return render(request, 'cameras/camera_form.html', context)

class CameraUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an existing camera."""
    model = Camera
    form_class = CameraForm
    template_name = 'cameras/camera_form.html'
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def get_success_url(self):
        return reverse_lazy('cameras:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(
            self.request,
            _(f'Camera "{self.object.name}" updated successfully!')
        )
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Camera')
        return context

@login_required
def camera_update_functional(request, camera_id):
    """Update camera details (functional view)."""
    camera = get_object_or_404(Camera, camera_id=camera_id)
    
    if request.method == 'POST':
        form = CameraForm(request.POST, instance=camera)
        if form.is_valid():
            camera = form.save()
            messages.success(request, f'Camera "{camera.name}" updated successfully!')
            return redirect('cameras:camera_detail_functional', camera_id=camera.camera_id)
    else:
        form = CameraForm(instance=camera)
    
    context = {'form': form, 'camera': camera}
    return render(request, 'cameras/camera_form.html', context)

class CameraDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a camera."""
    model = Camera
    template_name = 'cameras/camera_confirm_delete.html'
    success_url = reverse_lazy('cameras:list')
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def form_valid(self, form):
        """Handle successful deletion."""
        camera_name = self.object.name
        response = super().form_valid(form)
        messages.success(
            self.request,
            _(f'Camera "{camera_name}" deleted successfully!')
        )
        return response

@login_required
@require_POST
def camera_delete_functional(request, camera_id):
    """Delete a camera (functional view)."""
    camera = get_object_or_404(Camera, camera_id=camera_id)
    camera_name = camera.name
    camera.delete()
    messages.success(request, f'Camera "{camera_name}" deleted successfully!')
    return redirect('cameras:camera_list_functional')

@login_required
def camera_dashboard(request):
    """Camera dashboard with statistics and overview."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to view this page.'))
        return redirect('dashboard:index')
    
    # Get statistics
    total_cameras = Camera.objects.count()
    active_cameras = Camera.objects.filter(is_active=True, status='active').count()
    offline_cameras = Camera.objects.filter(status__in=['offline', 'error']).count()
    
    # Get cameras by type
    cameras_by_type = Camera.objects.values('camera_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Get cameras by status
    cameras_by_status = Camera.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Get recent health logs
    recent_logs = CameraHealthLog.objects.select_related('camera').order_by('-recorded_at')[:10]
    
    # Get cameras needing maintenance
    maintenance_cameras = Camera.objects.filter(
        status='maintenance'
    ).select_related('location')[:5]
    
    context = {
        'total_cameras': total_cameras,
        'active_cameras': active_cameras,
        'offline_cameras': offline_cameras,
        'uptime_percentage': (active_cameras / total_cameras * 100) if total_cameras > 0 else 0,
        'cameras_by_type': cameras_by_type,
        'cameras_by_status': cameras_by_status,
        'recent_logs': recent_logs,
        'maintenance_cameras': maintenance_cameras,
    }
    
    return render(request, 'cameras/dashboard.html', context)

@login_required
def toggle_camera_status(request, pk):
    """Toggle camera active/inactive status."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to perform this action.'))
        return redirect('cameras:list')
    
    camera = get_object_or_404(Camera, pk=pk)
    
    if camera.is_active:
        camera.is_active = False
        camera.status = Camera.Status.INACTIVE
        message = _('Camera deactivated.')
    else:
        camera.is_active = True
        camera.status = Camera.Status.ACTIVE
        message = _('Camera activated.')
    
    camera.save()
    messages.success(request, message)
    
    return redirect('cameras:detail', pk=camera.pk)

@login_required
@require_http_methods(['POST'])
def bulk_toggle_cameras(request):
    """Bulk toggle camera active/inactive status."""
    if not request.user.can_manage_cameras():
        return JsonResponse({
            'success': False,
            'message': _('You do not have permission to perform this action.')
        }, status=403)
    
    try:
        data = json.loads(request.body)
        camera_ids = data.get('camera_ids', [])
        action = data.get('action', 'activate')  # 'activate' or 'deactivate'
        
        if not camera_ids:
            return JsonResponse({
                'success': False,
                'message': _('No cameras selected.')
            }, status=400)
        
        # Get cameras
        cameras = Camera.objects.filter(id__in=camera_ids)
        
        # Update status based on action
        if action == 'activate':
            cameras.update(
                is_active=True,
                status=Camera.Status.ACTIVE
            )
            message = f'{cameras.count()} cameras activated.'
        else:  # deactivate
            cameras.update(
                is_active=False,
                status=Camera.Status.INACTIVE
            )
            message = f'{cameras.count()} cameras deactivated.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'updated_count': cameras.count()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': _('Invalid JSON data.')
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def camera_health_check(request, pk):
    """Perform health check on a camera."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to perform this action.'))
        return redirect('cameras:list')
    
    camera = get_object_or_404(Camera, pk=pk)
    
    # This would normally ping the camera and check connectivity
    # For now, we'll simulate it
    import random
    from django.utils import timezone
    
    # Simulate health check
    is_online = random.choice([True, True, True, False])  # 75% chance online
    
    if is_online:
        camera.status = Camera.Status.ACTIVE
        camera.last_ping = timezone.now()
        
        # Create health log
        CameraHealthLog.objects.create(
            camera=camera,
            status=Camera.Status.ACTIVE,
            uptime_percentage=random.uniform(95.0, 100.0),
            packet_loss=random.uniform(0.0, 5.0),
            bandwidth_usage=random.uniform(1.0, 10.0),
            response_time=random.uniform(10.0, 200.0),
            storage_usage=random.uniform(10.0, 80.0),
        )
        
        message = _('Camera is online and responding.')
    else:
        camera.status = Camera.Status.OFFLINE
        
        # Create health log
        CameraHealthLog.objects.create(
            camera=camera,
            status=Camera.Status.OFFLINE,
            uptime_percentage=0.0,
            packet_loss=100.0,
            bandwidth_usage=0.0,
            response_time=9999.0,
            storage_usage=0.0,
            errors=['Connection timeout', 'No response from camera']
        )
        
        message = _('Camera is offline or not responding.')
    
    camera.save()
    messages.info(request, message)
    
    return redirect('cameras:detail', pk=camera.pk)

@login_required
def export_cameras(request):
    """Export cameras data in various formats."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to export data.'))
        return redirect('cameras:list')
    
    format_type = request.GET.get('format', 'csv')
    queryset = Camera.objects.select_related('location').all()
    
    # Apply filters if any (same as list view)
    form = CameraFilterForm(request.GET)
    if form.is_valid():
        status = form.cleaned_data.get('status')
        camera_type = form.cleaned_data.get('camera_type')
        location = form.cleaned_data.get('location')
        is_active = form.cleaned_data.get('is_active')
        search = form.cleaned_data.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if camera_type:
            queryset = queryset.filter(camera_type=camera_type)
        if location:
            queryset = queryset.filter(location=location)
        if is_active:
            is_active_bool = is_active == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(camera_id__icontains=search) |
                Q(ip_address__icontains=search) |
                Q(serial_number__icontains=search) |
                Q(location__name__icontains=search)
            )
    
    # Prepare data
    data = []
    for camera in queryset:
        data.append({
            'ID': camera.camera_id,
            'Name': camera.name,
            'Location': camera.location.name if camera.location else '',
            'Type': camera.get_camera_type_display(),
            'Status': camera.get_status_display(),
            'IP Address': camera.ip_address or '',
            'Port': camera.port,
            'Protocol': camera.get_connection_protocol_display(),
            'Resolution': camera.resolution,
            'FPS': camera.fps,
            'Active': 'Yes' if camera.is_active else 'No',
            'Motion Detection': 'Yes' if camera.motion_detection_enabled else 'No',
            'Recording': 'Yes' if camera.recording_enabled else 'No',
            'Manufacturer': camera.manufacturer or '',
            'Model': camera.model or '',
            'Serial Number': camera.serial_number or '',
            'Installation Date': camera.installation_date or '',
            'Last Maintenance': camera.last_maintenance or '',
            'Created At': camera.created_at,
            'Updated At': camera.updated_at,
        })
    
    if format_type == 'csv':
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cameras_export.csv"'
        
        if data:
            writer = csv.DictWriter(response, fieldnames=data[0].keys())
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        
        return response
    
    elif format_type == 'json':
        import json
        from django.http import JsonResponse
        
        return JsonResponse(data, safe=False)
    
    else:
        messages.error(request, _('Unsupported export format.'))
        return redirect('cameras:list')
    
@login_required
def configure_camera(request, camera_id=None):
    """
    Configure a camera for live analysis/streaming.
    If camera_id is provided, configure that specific camera.
    If not, show a list of cameras to choose from.
    """
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to configure cameras.'))
        return redirect('cameras:list')
    
    if camera_id:
        # Configure specific camera
        camera = get_object_or_404(Camera, id=camera_id)
        
        if request.method == 'POST':
            # Process configuration
            detection_types = request.POST.getlist('detection_types', ['person', 'vehicle'])
            analysis_mode = request.POST.get('analysis_mode', 'realtime')
            save_output = request.POST.get('save_output', 'false') == 'true'
            alert_on_detection = request.POST.get('alert_on_detection', 'false') == 'true'
            
            # Store configuration (you might want to save this to a model)
            config_data = {
                'detection_types': detection_types,
                'analysis_mode': analysis_mode,
                'save_output': save_output,
                'alert_on_detection': alert_on_detection,
                'configured_by': request.user.id,
                'configured_at': timezone.now().isoformat()
            }
            
            # Here you would typically:
            # 1. Save configuration to database
            # 2. Start a background task for live analysis
            # 3. Connect to the camera stream
            
            messages.success(request, f'Camera "{camera.name}" configured for live analysis!')
            return redirect('cameras:live_stream', camera_id=camera.id)
        
        # GET request - show configuration form
        context = {
            'camera': camera,
            'title': f'Configure {camera.name}',
        }
        return render(request, 'cameras/configure_camera.html', context)
    
    else:
        # Show list of cameras to configure
        cameras = Camera.objects.filter(
            is_active=True,
            status=Camera.Status.ACTIVE
        ).select_related('location')
        
        context = {
            'cameras': cameras,
            'title': 'Select Camera to Configure',
        }
        return render(request, 'cameras/select_camera.html', context)

@login_required
def live_stream(request, camera_id):
    """
    Live stream and analysis view for a configured camera.
    """
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to view live streams.'))
        return redirect('cameras:list')
    
    camera = get_object_or_404(Camera, id=camera_id)
    
    context = {
        'camera': camera,
        'title': f'Live: {camera.name}',
        'stream_url': camera.get_stream_url_with_auth() or '',
        'ws_url': f'ws://{request.get_host()}/ws/camera/{camera.id}/',  # Example WebSocket URL
    }
    
    return render(request, 'cameras/live_stream.html', context)

# ============================================================================
# MEDIA UPLOAD AND PROCESSING VIEWS (Updated with new functionality)
# ============================================================================

@login_required
def media_selection(request):
    """Page for selecting upload or live camera."""
    return render(request, 'cameras/media_selection.html')

@login_required
def media_upload_list(request):
    """List all media uploads."""
    media_uploads = MediaUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    # Pagination
    paginator = Paginator(media_uploads, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Check FastAPI server health
    fastapi_health = fastapi_client.check_health()
    
    context = {
        'page_obj': page_obj,
        'fastapi_healthy': fastapi_health.get('healthy', False),
        'fastapi_status': fastapi_health.get('status', 'unknown'),
        'media_types': MediaUpload.MediaType.choices,
        'processing_statuses': MediaUpload.ProcessingStatus.choices,
    }
    return render(request, 'cameras/media_upload_list.html', context)



@login_required
def media_gallery(request):
    """Show gallery of all media uploads by user."""
    media_uploads = MediaUpload.objects.filter(
        uploaded_by=request.user
    ).order_by('-uploaded_at')
    
    return render(request, 'cameras/media_gallery.html', {
        'media_uploads': media_uploads
    })

@login_required
def upload_media(request):
    """
    Handle media upload (both images and videos) for FastAPI processing.
    Legacy version - kept for backward compatibility.
    """
    if request.method == 'POST':
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Handle file upload
        if 'media_file' not in request.FILES:
            if is_ajax:
                return JsonResponse({'error': 'No file selected'}, status=400)
            messages.error(request, 'No file selected')
            return redirect('cameras:upload_media')
        
        media_file = request.FILES['media_file']
        media_type = request.POST.get('media_type', 'image')
        title = request.POST.get('title', f'Uploaded {media_type}')
        description = request.POST.get('description', '')
        detection_types = request.POST.getlist('detection_types', ['person', 'vehicle'])
        
        # Determine MIME type
        mime_type = media_file.content_type
        if not mime_type:
            mime_type = mimetypes.guess_type(media_file.name)[0]
        
        # Validate file size
        max_size = 500 * 1024 * 1024  # 500MB
        if media_file.size > max_size:
            if is_ajax:
                return JsonResponse({'error': 'File size exceeds maximum limit (500MB)'}, status=400)
            messages.error(request, 'File size exceeds maximum limit (500MB)')
            return redirect('cameras:upload_media')
        
        # Validate file type
        if media_type == 'image':
            valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
            ext = os.path.splitext(media_file.name)[1].lower()
            if ext not in valid_extensions:
                if is_ajax:
                    return JsonResponse({'error': f'Invalid image format. Supported formats: {", ".join(valid_extensions)}'}, status=400)
                messages.error(request, f'Invalid image format. Supported formats: {", ".join(valid_extensions)}')
                return redirect('cameras:upload_media')
        elif media_type == 'video':
            valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
            ext = os.path.splitext(media_file.name)[1].lower()
            if ext not in valid_extensions:
                if is_ajax:
                    return JsonResponse({'error': f'Invalid video format. Supported formats: {", ".join(valid_extensions)}'}, status=400)
                messages.error(request, f'Invalid video format. Supported formats: {", ".join(valid_extensions)}')
                return redirect('cameras:upload_media')
        
        try:
            # Create MediaUpload instance
            media_upload = MediaUpload.objects.create(
                title=title,
                description=description,
                media_type=media_type,
                original_file=media_file,
                uploaded_by=request.user,
                mime_type=mime_type,
                file_size=media_file.size,
                processing_status=MediaUpload.ProcessingStatus.PENDING,
                request_data={
                    'detection_types': detection_types,
                    'original_filename': media_file.name,
                    'upload_timestamp': timezone.now().isoformat()
                }
            )
            
            # Try to generate thumbnail
            processor = MediaProcessor()
            processor.generate_thumbnail(media_upload)
            
            # Start processing ASYNCHRONOUSLY (don't wait for completion)
            from threading import Thread
            def start_processing():
                try:
                    success = processor.process_media_upload(media_upload, detection_types)
                    logger.info(f"Processing {'started successfully' if success else 'failed'} for media {media_upload.id}")
                except Exception as e:
                    logger.error(f"Error in processing thread: {str(e)}")
                    media_upload.processing_status = MediaUpload.ProcessingStatus.FAILED
                    media_upload.error_message = f"Processing error: {str(e)}"
                    media_upload.save()
            
            # Start processing in background thread
            processing_thread = Thread(target=start_processing, daemon=True)
            processing_thread.start()
            
            # Return immediately with upload info
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'{media_type.capitalize()} uploaded successfully! Processing has started.',
                    'upload_id': media_upload.id,
                    'redirect_url': f'/cameras/media/{media_upload.id}/status/',
                    'processing_started': True
                })
            
            # For non-AJAX, redirect to status page
            messages.success(request, f'{media_type.capitalize()} uploaded successfully! Processing has started.')
            return redirect('cameras:media_upload_status', media_id=media_upload.id)
                
        except Exception as e:
            logger.error(f"Error in upload_media: {str(e)}")
            if is_ajax:
                return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
            messages.error(request, f'Error uploading file: {str(e)}')
            return redirect('cameras:upload_media')
    
    # GET request - show upload form
    return render(request, 'cameras/upload_media.html', {
        'max_file_size': 500  # MB
    })
    
    
@login_required
def media_upload_create(request):
    """Upload and process media through FastAPI (new version)."""
    if request.method == 'POST':
        form = MediaUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Check FastAPI server health
            health_status = fastapi_client.check_health()
            if not health_status.get('healthy'):
                messages.error(request, 
                    f"FastAPI server is not available. Status: {health_status.get('status', 'unknown')}")
                return render(request, 'cameras/media_upload_form.html', {'form': form})
            
            # Save media upload
            media_upload = form.save(commit=False)
            media_upload.uploaded_by = request.user
            
            # Extract file metadata
            file = request.FILES['original_file']
            media_upload.file_size = file.size
            media_upload.mime_type = file.content_type
            
            # Determine media type from file extension
            filename = file.name.lower()
            if any(filename.endswith(ext) for ext in settings.ALLOWED_IMAGE_EXTENSIONS):
                media_upload.media_type = MediaUpload.MediaType.IMAGE
            elif any(filename.endswith(ext) for ext in settings.ALLOWED_VIDEO_EXTENSIONS):
                media_upload.media_type = MediaUpload.MediaType.VIDEO
            else:
                messages.error(request, 'Unsupported file format')
                return render(request, 'cameras/media_upload_form.html', {'form': form})
            
            media_upload.save()
            
            # Get detection types from form
            detection_types = form.cleaned_data.get('detection_types', [])
            if not detection_types:
                detection_types = ['person', 'vehicle']
            
            # Start processing
            try:
                processing_result = media_processor.process_media_upload(
                    media_upload=media_upload,
                    detection_types=detection_types,
                    request_base64=True  # Always request base64 from FastAPI
                )
                
                if processing_result['success']:
                    messages.success(request, 
                        f"Media uploaded and sent for processing! {processing_result['message']}")
                    
                    # Generate thumbnail
                    media_processor.generate_thumbnail(media_upload)
                    
                    return redirect('cameras:media_upload_detail_functional', media_id=media_upload.id)
                else:
                    messages.error(request, 
                        f"Upload successful but processing failed: {processing_result['message']}")
                    return redirect('cameras:media_upload_list')
                    
            except Exception as e:
                logger.error(f"Error processing media upload: {e}", exc_info=True)
                messages.error(request, f"Error processing media: {str(e)}")
                return redirect('cameras:media_upload_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MediaUploadForm()
    
    # Check FastAPI server health
    fastapi_health = fastapi_client.check_health()
    
    context = {
        'form': form,
        'fastapi_healthy': fastapi_health.get('healthy', False),
        'fastapi_status': fastapi_health.get('status', 'unknown'),
        'max_upload_size_mb': settings.MAX_UPLOAD_SIZE // (1024 * 1024),
    }
    return render(request, 'cameras/media_upload_form.html', context)

@login_required
def media_processing_status(request, upload_id):
    """
    Show processing status for a media upload.
    """
    media_upload = get_object_or_404(MediaUpload, id=upload_id, uploaded_by=request.user)
    
    return render(request, 'cameras/media_processing_status.html', {
        'media_upload': media_upload,
        'progress_percentage': media_upload.get_progress_percentage()
    })

@login_required
def media_upload_detail_functional(request, media_id):
    """
    Redirect to media_analysis_results view.
    This maintains backward compatibility.
    """
    return redirect('cameras:media_analysis_results', upload_id=media_id)



@login_required
def media_analysis_results(request, upload_id):
    """
    Show enhanced AI analysis results for completed media upload with campus-specific intelligence.
    This is the MAIN view for displaying intelligent security analysis.
    """
    logger.info(f"=== CAMPUSGUARD AI ANALYSIS RESULTS START ===")
    logger.info(f"User: {request.user.username}, Media ID: {upload_id}")
    
    media_upload = get_object_or_404(MediaUpload, id=upload_id, uploaded_by=request.user)
    
    # Debug: Print basic info
    logger.info(f"Media Type: {'Image' if media_upload.is_image() else 'Video'}")
    logger.info(f"Processing Status: {media_upload.processing_status}")
    logger.info(f"Has Base64 Data: {media_upload.has_base64_data()}")
    logger.info(f"Has Processed File: {media_upload.has_processed_file()}")
    
    # Check if processing is complete
    if media_upload.processing_status != MediaUpload.ProcessingStatus.COMPLETED:
        messages.warning(request, 'AI analysis is still in progress. Please wait.')
        return redirect('cameras:media_upload_status', media_id=upload_id)
    
    # Get analysis results - FIXED: Use the correct exception handling
    try:
        analysis_results = media_upload.analysis_results
        logger.info(f"Found existing analysis results")
    except MediaUpload.analysis_results.RelatedObjectDoesNotExist:
        logger.info(f"No existing analysis results, creating new")
        # Try to create from response data
        processor = MediaProcessor()
        
        # Check if response_data exists and is valid
        if media_upload.response_data:
            # FIXED: Changed _create_analysis_results to _create_or_update_analysis_results
            analysis_results = processor._create_or_update_analysis_results(media_upload, media_upload.response_data)
            logger.info(f"Created analysis results from response_data")
        else:
            # Create empty results to avoid errors
            analysis_results = MediaAnalysisResult.objects.create(
                media_upload=media_upload,
                total_detections=0,
                person_count=0,
                vehicle_count=0,
                suspicious_activity_count=0,
                detections_json=[],
                timeline_data=[],
                heatmap_data={'points': [], 'max_intensity': 0}
            )
            messages.info(request, 'No AI analysis results available yet.')
            logger.info(f"Created empty analysis results (no response_data)")
    
    # STRICT DEBUG: Check response data
    logger.info(f"=== RESPONSE DATA ANALYSIS ===")
    logger.info(f"Response data exists: {media_upload.response_data is not None}")
    
    if media_upload.response_data:
        logger.info(f"Response data type: {type(media_upload.response_data)}")
        if isinstance(media_upload.response_data, dict):
            logger.info(f"Response data keys: {list(media_upload.response_data.keys())}")
            
            # Check for base64 data
            has_base64_image = 'processed_image_base64' in media_upload.response_data
            has_key_frames = 'key_frames_base64' in media_upload.response_data
            logger.info(f"Has base64 image: {has_base64_image}")
            logger.info(f"Has key frames: {has_key_frames}")
            
            if has_base64_image:
                base64_str = media_upload.response_data['processed_image_base64']
                logger.info(f"Base64 image length: {len(str(base64_str)) if base64_str else 0}")
            
            if has_key_frames:
                key_frames = media_upload.response_data['key_frames_base64']
                if isinstance(key_frames, list):
                    logger.info(f"Number of key frames: {len(key_frames)}")
                else:
                    logger.info(f"Key frames type: {type(key_frames)}")
        else:
            logger.warning(f"response_data is not a dict, it's: {type(media_upload.response_data)}")
    else:
        logger.warning("No response_data available")
    
    # Process base64 data for template
    processed_image_data = None
    key_frames_data = []
    
    # For images: Get base64 image or processed file
    if media_upload.is_image():
        if media_upload.has_processed_file():
            # Use saved processed file
            processed_image_data = {
                'type': 'file',
                'url': media_upload.processed_file.url,
                'has_data': True
            }
            logger.info(f"Using saved processed file: {media_upload.processed_file.url}")
        elif media_upload.processed_file_base64:
            # Use base64 data from model
            processed_image_data = {
                'type': 'base64',
                'data': media_upload.processed_file_base64,
                'has_data': True
            }
            logger.info(f"Using base64 data from model (length: {len(media_upload.processed_file_base64)})")
        elif hasattr(analysis_results, 'processed_image_base64') and analysis_results.processed_image_base64:
            # Use base64 data from analysis results
            processed_image_data = {
                'type': 'base64',
                'data': analysis_results.processed_image_base64,
                'has_data': True
            }
            logger.info(f"Using base64 data from analysis results")
        elif media_upload.response_data and 'processed_image_base64' in media_upload.response_data:
            # Use base64 data from response
            processed_image_data = {
                'type': 'base64',
                'data': media_upload.response_data['processed_image_base64'],
                'has_data': True
            }
            logger.info(f"Using base64 data from response_data")
        else:
            logger.warning("No processed image data available")
            processed_image_data = {'type': 'none', 'has_data': False}
    
    # For videos: Get key frames
    elif media_upload.is_video():
        if media_upload.key_frames_base64:
            # Use key frames from model
            key_frames_data = media_upload.key_frames_base64
            logger.info(f"Using {len(key_frames_data)} key frames from model")
        elif media_upload.response_data and 'key_frames_base64' in media_upload.response_data:
            # Use key frames from response
            key_frames_data = media_upload.response_data['key_frames_base64']
            if isinstance(key_frames_data, list):
                logger.info(f"Using {len(key_frames_data)} key frames from response_data")
            else:
                logger.warning(f"Key frames data is not a list: {type(key_frames_data)}")
                key_frames_data = []
        else:
            logger.warning("No key frames data available")
    
    # Extract analysis summary
    analysis_summary = {}
    if media_upload.analysis_summary:
        analysis_summary = media_upload.analysis_summary
    elif media_upload.response_data and 'summary' in media_upload.response_data:
        analysis_summary = media_upload.response_data['summary']
    
    # Get processing time
    processing_time = None
    if media_upload.get_processing_time():
        processing_time = media_upload.get_processing_time()
    elif media_upload.response_data and 'processing_time' in media_upload.response_data:
        processing_time = media_upload.response_data['processing_time']
    
    # ===== ENHANCED CAMPUS-SPECIFIC ANALYSIS =====
    
    # Process enhanced detections with campus context
    enhanced_detections = []
    detections_data = []
    
    # Try multiple sources for detections data
    if hasattr(analysis_results, 'detections_json') and analysis_results.detections_json:
        # Use detections from analysis results
        detections_data = analysis_results.detections_json
        logger.info(f"Using {len(detections_data)} detections from analysis_results.detections_json")
    elif media_upload.response_data and 'detections' in media_upload.response_data:
        # Use detections from response data
        detections_data = media_upload.response_data['detections']
        logger.info(f"Using {len(detections_data)} detections from response_data['detections']")
    elif analysis_results and hasattr(analysis_results, 'detections_json'):
        # Fallback to empty if available
        detections_data = analysis_results.detections_json or []
        logger.info(f"Using detections_json from analysis_results (might be empty)")
    
    # Process enhanced detections
    if detections_data:
        logger.info(f"Processing {len(detections_data)} detections for campus context")
        
        for idx, detection in enumerate(detections_data[:20]):  # Limit for display
            try:
                enhanced = process_detection_for_context(detection, media_upload, idx)
                enhanced_detections.append(enhanced)
            except Exception as e:
                logger.error(f"Error processing detection {idx}: {e}")
                # Create a basic enhanced detection with minimal info
                enhanced_detections.append({
                    'index': idx,
                    'label': detection.get('label', 'unknown') if isinstance(detection, dict) else 'unknown',
                    'confidence': detection.get('confidence', 0) if isinstance(detection, dict) else 0,
                    'campus_context': ['Processing error occurred'],
                    'risk_assessment': {'level': 'Unknown', 'color': 'secondary', 'action': 'Review needed'},
                    'needs_review': True
                })
    
    # Calculate threat level
    threat_info = calculate_threat_level(media_upload.response_data)
    logger.info(f"Threat level calculated: {threat_info['label']}")
    
    # Generate AI recommendations
    recommendations = generate_recommendations(media_upload.response_data)
    logger.info(f"Generated {len(recommendations)} AI recommendations")
    
    # Calculate average confidence - FIXED: Handle different data structures
    average_confidence = 0
    if detections_data and len(detections_data) > 0:
        confidences = []
        for detection in detections_data:
            if isinstance(detection, dict):
                confidence = detection.get('confidence')
                if confidence is not None:
                    try:
                        confidences.append(float(confidence))
                    except (ValueError, TypeError):
                        pass
        
        if confidences:
            average_confidence = (sum(confidences) / len(confidences)) * 100
    
    # Calculate detection statistics - FIXED: Use analysis_results directly
    person_count = analysis_results.person_count if hasattr(analysis_results, 'person_count') else 0
    vehicle_count = analysis_results.vehicle_count if hasattr(analysis_results, 'vehicle_count') else 0
    total_detections = analysis_results.total_detections if hasattr(analysis_results, 'total_detections') else 0
    
    # Calculate detection density (simplified)
    detection_density = "Low"
    if total_detections > 20:
        detection_density = "High"
    elif total_detections > 10:
        detection_density = "Medium"
    
    # Get peak activity time (for videos)
    peak_activity_time = "N/A"
    if media_upload.is_video() and media_upload.analysis_summary:
        peak_activity_time = media_upload.analysis_summary.get('peak_time', 'N/A')
    
    # Check if suspicious timing (simplified)
    is_suspicious_timing = False
    uploaded_hour = media_upload.uploaded_at.hour if media_upload.uploaded_at else 12
    if uploaded_hour < 6 or uploaded_hour > 22:
        is_suspicious_timing = True
    
    # Log the final data for debugging
    logger.info(f"=== ENHANCED ANALYSIS DATA ===")
    logger.info(f"Enhanced detections: {len(enhanced_detections)}")
    logger.info(f"Threat level: {threat_info['label']}")
    logger.info(f"Average confidence: {average_confidence:.1f}%")
    logger.info(f"Detection density: {detection_density}")
    logger.info(f"Processing time: {processing_time}")
    logger.info(f"=== ANALYSIS COMPLETE ===")
    
    # Prepare comprehensive context for template
    context = {
        'media_upload': media_upload,
        'analysis': analysis_results,
        'analysis_results': analysis_results,  # Alias for compatibility
        'processed_image_data': processed_image_data,
        'key_frames_data': key_frames_data,
        'analysis_summary': analysis_summary,
        'processing_time': processing_time,
        'has_analysis': True,
        
        # Enhanced campus intelligence
        'enhanced_detections': enhanced_detections,
        'threat_level_color': threat_info['color'],
        'threat_level_icon': threat_info['icon'],
        'threat_level_label': threat_info['label'],
        'threat_level_description': threat_info['description'],
        'recommendations': recommendations,
        'average_confidence': average_confidence,
        'detection_density': detection_density,
        'peak_activity_time': peak_activity_time,
        'is_suspicious_timing': is_suspicious_timing,
        
        # Campus zone statistics
        'academic_persons': person_count,
        'residential_persons': int(person_count * 0.3) if person_count > 0 else 0,
        'academic_vehicles': int(vehicle_count * 0.7) if vehicle_count > 0 else 0,
        'residential_vehicles': int(vehicle_count * 0.3) if vehicle_count > 0 else 0,
        'academic_alerts': analysis_results.suspicious_activity_count if hasattr(analysis_results, 'suspicious_activity_count') else 0,
        'residential_alerts': 0,  # Could be calculated based on detection zones
        
        # Detection metrics
        'person_confidence': average_confidence,
        'cluster_count': len(set([d.get('label', '') for d in detections_data if isinstance(d, dict)])) if detections_data else 0,
        
        # FastAPI info
        'debug': False  # Set to True for debugging
    }
    
    # Add FastAPI info if available
    if media_upload.fastapi_endpoint:
        context['fastapi_endpoint'] = media_upload.fastapi_endpoint
        context['fastapi_job_id'] = media_upload.job_id
    
    # Add detection legend colors
    context['detection_colors'] = {
        'person': '#00FF00',  # Green
        'car': '#0000FF',     # Blue
        'truck': '#FF0000',   # Red
        'bus': '#FFFF00',     # Yellow
        'motorcycle': '#00FFFF', # Cyan
        'vehicle': '#800080'  # Purple
    }
    
    return render(request, 'cameras/media_analysis_results.html', context)


# ===== HELPER FUNCTIONS FOR CAMPUS-SPECIFIC ANALYSIS =====

def process_detection_for_context(detection, media_upload, index):
    """
    Enhance detection with campus-specific context and intelligence.
    """
    # Create a copy to avoid modifying original
    if isinstance(detection, dict):
        enhanced = detection.copy()
    else:
        enhanced = {'raw': detection}
    
    # Extract detection type
    detection_type = enhanced.get('label') or enhanced.get('class') or 'unknown'
    confidence = enhanced.get('confidence', 0)
    
    # Add campus-specific intelligence
    enhanced['campus_context'] = get_campus_context(detection_type, confidence, media_upload)
    enhanced['risk_assessment'] = get_risk_assessment(detection_type, confidence)
    enhanced['recommendations'] = get_detection_recommendations(detection_type, confidence)
    
    # Add display properties
    enhanced['icon'] = get_detection_icon(detection_type)
    enhanced['color'] = get_detection_color(detection_type)
    enhanced['risk_color'] = get_risk_color(confidence)
    enhanced['risk_icon'] = get_risk_icon(confidence)
    enhanced['risk_level'] = get_risk_level_label(confidence)
    
    # Add zone assessment (simplified - could be based on bounding box)
    enhanced['zone'] = assign_campus_zone(enhanced)
    enhanced['zone_color'] = get_zone_color(enhanced['zone'])
    enhanced['zone_icon'] = get_zone_icon(enhanced['zone'])
    enhanced['zone_assessment'] = get_zone_assessment(enhanced['zone'], detection_type)
    
    # Add context tags
    enhanced['context_tags'] = get_context_tags(detection_type, confidence, media_upload)
    enhanced['time_context'] = get_time_context(media_upload)
    
    # Add needs review flag
    enhanced['needs_review'] = confidence < 0.6
    
    # Add index for reference
    enhanced['index'] = index
    
    return enhanced


def get_campus_context(detection_type, confidence, media_upload):
    """
    Get campus-specific context for a detection.
    """
    context = []
    uploaded_hour = media_upload.uploaded_at.hour if media_upload.uploaded_at else 12
    
    if detection_type == 'person':
        context.append('Potential campus member (student/staff)')
        if confidence > 0.8:
            context.append('High confidence identification')
        elif confidence > 0.6:
            context.append('Moderate confidence - likely campus member')
        else:
            context.append('Low confidence - verification recommended')
        
        # Time-based context
        if uploaded_hour < 6 or uploaded_hour > 22:
            context.append('Detected during non-standard campus hours')
        
    elif detection_type in ['car', 'truck', 'bus', 'motorcycle']:
        context.append('Campus vehicle detected')
        if detection_type == 'bus':
            context.append('Potential campus shuttle or transport vehicle')
        elif detection_type == 'truck':
            context.append('Delivery or maintenance vehicle')
        
        if confidence < 0.7:
            context.append('Vehicle identification uncertain')
    
    else:
        context.append(f'{detection_type.title()} detected in campus environment')
        if confidence < 0.5:
            context.append('Low confidence - may require manual review')
    
    return context


def get_risk_assessment(detection_type, confidence):
    """
    Assess risk level for campus security.
    """
    if detection_type == 'person':
        if confidence < 0.5:
            return {'level': 'High', 'color': 'danger', 'action': 'Immediate review required'}
        elif confidence < 0.7:
            return {'level': 'Medium', 'color': 'warning', 'action': 'Verification recommended'}
        else:
            return {'level': 'Low', 'color': 'success', 'action': 'Standard campus activity'}
    
    elif detection_type in ['car', 'truck', 'bus']:
        if confidence < 0.6:
            return {'level': 'Medium', 'color': 'warning', 'action': 'Verify authorization'}
        else:
            return {'level': 'Low', 'color': 'success', 'action': 'Standard vehicle activity'}
    
    else:
        return {'level': 'Unknown', 'color': 'secondary', 'action': 'Monitor if unusual'}


def get_detection_recommendations(detection_type, confidence):
    """
    Generate specific recommendations for each detection.
    """
    recommendations = []
    
    if confidence < 0.6:
        recommendations.append({
            'icon': 'eye',
            'color': 'warning',
            'text': 'Low confidence detection - manual review recommended'
        })
    
    if detection_type == 'person' and confidence > 0.8:
        recommendations.append({
            'icon': 'check-circle',
            'color': 'success',
            'text': 'High confidence person detection - no action required'
        })
    
    if detection_type in ['truck', 'bus']:
        recommendations.append({
            'icon': 'clipboard-check',
            'color': 'info',
            'text': 'Check delivery schedules or transport authorization'
        })
    
    if detection_type == 'person' and confidence < 0.7:
        recommendations.append({
            'icon': 'id-card',
            'color': 'warning',
            'text': 'Consider identification verification if in restricted area'
        })
    
    return recommendations


def get_detection_icon(detection_type):
    """
    Get FontAwesome icon for detection type.
    """
    icons = {
        'person': 'user',
        'car': 'car',
        'truck': 'truck',
        'bus': 'bus',
        'motorcycle': 'motorcycle',
        'bicycle': 'bicycle',
        'vehicle': 'car',
    }
    return icons.get(detection_type.lower(), 'cube')


def get_detection_color(detection_type):
    """
    Get Bootstrap color for detection type.
    """
    colors = {
        'person': 'primary',
        'car': 'warning',
        'truck': 'warning',
        'bus': 'warning',
        'motorcycle': 'warning',
        'bicycle': 'info',
        'vehicle': 'warning',
    }
    return colors.get(detection_type.lower(), 'secondary')


def get_risk_color(confidence):
    """
    Get color based on confidence level.
    """
    if confidence > 0.8:
        return 'success'
    elif confidence > 0.6:
        return 'warning'
    else:
        return 'danger'


def get_risk_icon(confidence):
    """
    Get icon based on confidence level.
    """
    if confidence > 0.8:
        return 'shield-alt'
    elif confidence > 0.6:
        return 'exclamation-circle'
    else:
        return 'exclamation-triangle'


def get_risk_level_label(confidence):
    """
    Get risk level label based on confidence.
    """
    if confidence > 0.8:
        return 'Low Risk'
    elif confidence > 0.6:
        return 'Medium Risk'
    else:
        return 'High Risk'


def assign_campus_zone(detection):
    """
    Assign campus zone based on detection properties.
    Simplified - in real implementation, use bounding box coordinates.
    """
    # This is a simplified version
    # In production, you would use bounding box coordinates to determine zone
    zones = ['Academic', 'Residential', 'Administrative', 'Recreational', 'Parking']
    
    # Simple assignment based on detection type
    detection_type = detection.get('label') or detection.get('class') or 'unknown'
    
    if detection_type == 'person':
        return 'Academic'  # Default for persons
    elif detection_type in ['car', 'truck', 'bus', 'motorcycle']:
        return 'Parking'
    else:
        return 'Academic'


def get_zone_color(zone):
    """
    Get color for campus zone.
    """
    colors = {
        'Academic': 'primary',
        'Residential': 'warning',
        'Administrative': 'info',
        'Recreational': 'success',
        'Parking': 'secondary',
    }
    return colors.get(zone, 'secondary')


def get_zone_icon(zone):
    """
    Get icon for campus zone.
    """
    icons = {
        'Academic': 'graduation-cap',
        'Residential': 'home',
        'Administrative': 'building',
        'Recreational': 'futbol',
        'Parking': 'parking',
    }
    return icons.get(zone, 'map-marker')


def get_zone_assessment(zone, detection_type):
    """
    Get assessment for detection in specific zone.
    """
    assessments = {
        'Academic': {
            'person': 'Standard academic area activity',
            'vehicle': 'Check parking authorization',
            'default': 'Activity in academic zone'
        },
        'Residential': {
            'person': 'Residential area activity',
            'vehicle': 'Resident or visitor vehicle',
            'default': 'Activity in residential zone'
        },
        'Parking': {
            'person': 'Person in parking area',
            'vehicle': 'Parked vehicle',
            'default': 'Parking area activity'
        }
    }
    
    zone_assessments = assessments.get(zone, assessments['Academic'])
    return zone_assessments.get(detection_type, zone_assessments['default'])


def get_context_tags(detection_type, confidence, media_upload):
    """
    Generate context tags for the detection.
    """
    tags = []
    uploaded_hour = media_upload.uploaded_at.hour if media_upload.uploaded_at else 12
    
    # Time-based tags
    if uploaded_hour < 6:
        tags.append('Early Morning')
    elif uploaded_hour < 12:
        tags.append('Morning')
    elif uploaded_hour < 18:
        tags.append('Afternoon')
    else:
        tags.append('Evening')
    
    if uploaded_hour < 6 or uploaded_hour > 22:
        tags.append('Non-Standard Hours')
    
    # Confidence tags
    if confidence > 0.8:
        tags.append('High Confidence')
    elif confidence > 0.6:
        tags.append('Medium Confidence')
    else:
        tags.append('Low Confidence')
    
    # Detection type tags
    if detection_type == 'person':
        tags.append('Campus Member')
    elif detection_type in ['car', 'truck', 'bus']:
        tags.append('Campus Vehicle')
    
    return tags


def get_time_context(media_upload):
    """
    Get time context for the analysis.
    """
    if not media_upload.uploaded_at:
        return "Time unknown"
    
    hour = media_upload.uploaded_at.hour
    weekday = media_upload.uploaded_at.weekday()  # 0 = Monday
    
    time_context = ""
    
    if weekday < 5:  # Monday to Friday
        time_context += "Weekday "
    else:
        time_context += "Weekend "
    
    if hour < 6:
        time_context += "· Early Morning (12AM-6AM)"
    elif hour < 12:
        time_context += "· Morning (6AM-12PM)"
    elif hour < 18:
        time_context += "· Afternoon (12PM-6PM)"
    else:
        time_context += "· Evening (6PM-12AM)"
    
    return time_context


def calculate_threat_level(response_data):
    """
    Calculate overall threat level based on analysis results.
    """
    if not response_data or 'detections' not in response_data:
        return {
            'level': 'normal',
            'color': 'success',
            'icon': 'shield-alt',
            'label': 'Normal Campus Activity',
            'description': 'Standard activity detected. No immediate threats identified.'
        }
    
    detections = response_data.get('detections', [])
    
    if not detections:
        return {
            'level': 'normal',
            'color': 'success',
            'icon': 'shield-alt',
            'label': 'No Activity Detected',
            'description': 'No persons or vehicles detected in the analyzed media.'
        }
    
    # Analyze detections
    total_detections = len(detections)
    low_confidence_count = len([d for d in detections if d.get('confidence', 0) < 0.5])
    person_count = len([d for d in detections if d.get('label') == 'person'])
    
    # Calculate threat score
    threat_score = 0
    
    # Low confidence detections increase threat
    threat_score += low_confidence_count * 2
    
    # Many persons might indicate crowd (could be normal or concerning)
    if person_count > 15:
        threat_score += 3
    elif person_count > 5:
        threat_score += 1
    
    # Determine threat level
    if threat_score > 10:
        return {
            'level': 'high',
            'color': 'danger',
            'icon': 'exclamation-triangle',
            'label': 'Elevated Security Alert',
            'description': f'Multiple concerning factors detected ({low_confidence_count} low-confidence detections). Review recommended.'
        }
    elif threat_score > 5:
        return {
            'level': 'medium',
            'color': 'warning',
            'icon': 'exclamation-circle',
            'label': 'Moderate Alert',
            'description': f'Some detections require attention ({low_confidence_count} low-confidence). Monitor activity.'
        }
    elif total_detections == 0:
        return {
            'level': 'normal',
            'color': 'info',
            'icon': 'info-circle',
            'label': 'No Activity',
            'description': 'No detections made. Camera may be offline or area clear.'
        }
    else:
        return {
            'level': 'normal',
            'color': 'success',
            'icon': 'shield-alt',
            'label': 'Normal Campus Activity',
            'description': f'Standard activity detected ({total_detections} objects). No immediate threats.'
        }


def generate_recommendations(response_data):
    """
    Generate AI-powered recommendations based on analysis.
    """
    recommendations = []
    
    if not response_data:
        # Default recommendation when no data
        recommendations.append({
            'icon': 'info-circle',
            'color': 'info',
            'title': 'Analysis Complete',
            'description': 'Media has been processed by CampusGuard AI.'
        })
        return recommendations
    
    detections = response_data.get('detections', [])
    
    if not detections:
        recommendations.append({
            'icon': 'check-circle',
            'color': 'success',
            'title': 'No Threats Detected',
            'description': 'Area appears clear of security concerns.'
        })
        return recommendations
    
    # Count statistics
    person_count = len([d for d in detections if d.get('label') == 'person'])
    vehicle_count = len([d for d in detections if d.get('label') in ['car', 'truck', 'bus', 'motorcycle']])
    low_confidence_count = len([d for d in detections if d.get('confidence', 0) < 0.6])
    
    # Generate recommendations based on analysis
    
    if low_confidence_count > 0:
        recommendations.append({
            'icon': 'eye',
            'color': 'warning',
            'title': 'Review Low Confidence Detections',
            'description': f'{low_confidence_count} detections have confidence below 60%. Manual verification recommended.'
        })
    
    if person_count > 10:
        recommendations.append({
            'icon': 'users',
            'color': 'info',
            'title': 'High Person Density',
            'description': f'{person_count} persons detected. Consider crowd monitoring if in confined space.'
        })
    
    if vehicle_count > 3:
        recommendations.append({
            'icon': 'car',
            'color': 'info',
            'title': 'Vehicle Activity',
            'description': f'{vehicle_count} vehicles detected. Verify parking authorization if in restricted zones.'
        })
    
    if person_count == 0 and vehicle_count == 0:
        recommendations.append({
            'icon': 'check-circle',
            'color': 'success',
            'title': 'Area Clear',
            'description': 'No persons or vehicles detected. Normal security status.'
        })
    
    # Always add general recommendation
    recommendations.append({
        'icon': 'clipboard-check',
        'color': 'primary',
        'title': 'Document Analysis',
        'description': 'Save this analysis report for security records and audit purposes.'
    })
    
    # Add export recommendation
    recommendations.append({
        'icon': 'download',
        'color': 'secondary',
        'title': 'Export Results',
        'description': 'Download the complete analysis for sharing with security team.'
    })
    
    return recommendations


@login_required
def media_upload_detail_functional(request, media_id):
    """
    Redirect to media_analysis_results view.
    This maintains backward compatibility.
    """
    return redirect('cameras:media_analysis_results', upload_id=media_id)
@login_required
@require_GET
def get_processing_status(request, upload_id):
    """
    AJAX endpoint to get processing status.
    """
    media_upload = get_object_or_404(MediaUpload, id=upload_id, uploaded_by=request.user)
    
    return JsonResponse({
        'status': media_upload.processing_status,
        'progress': media_upload.get_progress_percentage(),
        'job_id': media_upload.job_id,
        'has_results': hasattr(media_upload, 'analysis_results'),
        'can_view_results': media_upload.processing_status == MediaUpload.ProcessingStatus.COMPLETED
    })

@login_required
@require_GET
def media_upload_status(request, media_id):
    """Get processing status of a media upload (AJAX endpoint)."""
    media_upload = get_object_or_404(MediaUpload, id=media_id, uploaded_by=request.user)
    
    status_info = media_processor.check_processing_status(media_upload)
    
    return JsonResponse({
        'success': True,
        'status': status_info,
    })

@login_required
@require_POST
def media_upload_retry(request, media_id):
    """Retry processing a failed media upload."""
    media_upload = get_object_or_404(MediaUpload, id=media_id, uploaded_by=request.user)
    
    # Check if media can be retried
    if media_upload.processing_status not in [MediaUpload.ProcessingStatus.FAILED, 
                                             MediaUpload.ProcessingStatus.RETRYING]:
        messages.error(request, 'Media cannot be retried in its current state.')
        return redirect('cameras:media_upload_detail_functional', media_id=media_id)
    
    # Reset for retry
    media_upload.retry_processing()
    
    # Get detection types from previous request or use defaults
    detection_types = media_upload.request_data.get('detection_types', ['person', 'vehicle'])
    
    # Retry processing
    try:
        processing_result = media_processor.process_media_upload(
            media_upload=media_upload,
            detection_types=detection_types,
            request_base64=True
        )
        
        if processing_result['success']:
            messages.success(request, 'Media processing retry started successfully!')
        else:
            messages.error(request, f"Retry failed: {processing_result['message']}")
            
    except Exception as e:
        logger.error(f"Error retrying media processing: {e}", exc_info=True)
        messages.error(request, f"Error retrying processing: {str(e)}")
    
    return redirect('cameras:media_upload_detail_functional', media_id=media_id)

@login_required
def delete_media_upload(request, upload_id):
    """Delete a media upload and associated files."""
    media_upload = get_object_or_404(MediaUpload, id=upload_id, uploaded_by=request.user)
    
    if request.method == 'POST':
        title = media_upload.title
        media_upload.delete()
        messages.success(request, f'Media "{title}" deleted successfully.')
        return redirect('cameras:media_gallery')
    
    return render(request, 'cameras/media_confirm_delete.html', {
        'media_upload': media_upload
    })

@login_required
@require_POST
def media_upload_delete(request, media_id):
    """Delete a media upload (functional view)."""
    media_upload = get_object_or_404(MediaUpload, id=media_id, uploaded_by=request.user)
    
    # Delete associated files
    if media_upload.original_file:
        media_upload.original_file.delete(save=False)
    if media_upload.processed_file:
        media_upload.processed_file.delete(save=False)
    if media_upload.thumbnail:
        media_upload.thumbnail.delete(save=False)
    
    title = media_upload.title
    media_upload.delete()
    
    messages.success(request, f'Media "{title}" deleted successfully!')
    return redirect('cameras:media_upload_list')

# ============================================================================
# FASTAPI INTEGRATION VIEWS
# ============================================================================

@login_required
def fastapi_status(request):
    """Check FastAPI server status."""
    health_status = fastapi_client.check_health()
    
    # Get available models
    models = fastapi_client.get_available_models() or []
    
    context = {
        'health_status': health_status,
        'models': models,
        'base_url': fastapi_client.base_url,
    }
    
    return render(request, 'cameras/fastapi_status.html', context)

@login_required
@require_GET
def fastapi_status_json(request):
    """Get FastAPI server status as JSON (AJAX endpoint)."""
    health_status = fastapi_client.check_health()
    
    return JsonResponse({
        'success': True,
        'data': health_status,
    })

@login_required
def fastapi_health_check(request):
    """
    Check FastAPI server health.
    """
    processor = MediaProcessor()
    is_healthy = processor.fastapi_client.check_health()
    
    return JsonResponse({
        'healthy': is_healthy,
        'server_url': processor.fastapi_client.base_url
    })

@login_required
def process_demo_image(request):
    """Demo page for image processing."""
    if request.method == 'POST' and request.FILES.get('image_file'):
        # Check FastAPI server health
        health_status = fastapi_client.check_health()
        if not health_status.get('healthy'):
            messages.error(request, f"FastAPI server is not available: {health_status.get('status', 'unknown')}")
            return render(request, 'cameras/process_demo.html')
        
        # Process image
        image_file = request.FILES['image_file']
        detection_types = request.POST.getlist('detection_types', ['person', 'vehicle'])
        
        try:
            response = fastapi_client.process_image(
                image_file=image_file,
                detection_types=detection_types,
                return_base64=True,
                django_user_id=str(request.user.id)
            )
            
            if response:
                # Extract base64 image
                base64_image = base64_processor.extract_image_from_fastapi_response(response)
                
                context = {
                    'success': True,
                    'response': response,
                    'has_base64_image': bool(base64_image),
                    'base64_image': base64_image,
                    'detection_count': len(response.get('detections', [])),
                    'detections': response.get('detections', []),
                }
                
                # Create data URL for display
                if base64_image:
                    context['data_url'] = base64_processor.create_data_url(base64_image, 'image/jpeg')
                
                return render(request, 'cameras/process_demo.html', context)
            else:
                messages.error(request, 'Failed to process image. Please try again.')
                
        except Exception as e:
            logger.error(f"Error in demo image processing: {e}", exc_info=True)
            messages.error(request, f"Error processing image: {str(e)}")
    
    return render(request, 'cameras/process_demo.html')

# ============================================================================
# PROCESSED IMAGE PROXY
# ============================================================================

from django.conf import settings
from datetime import datetime

@login_required
def processed_image_proxy(request, filename):
    """
    Proxy processed images from FastAPI static endpoint.
    No authentication needed for static files!
    """
    try:
        from django.conf import settings
        
        # Use the static endpoint (no authentication needed)
        fastapi_base_url = getattr(settings, 'FASTAPI_BASE_URL', 'http://localhost:8001')
        fastapi_url = f"{fastapi_base_url}/static/processed/images/{filename}"
        
        logger.info(f"Fetching from FastAPI static endpoint: {fastapi_url}")
        
        import requests
        # NO API KEY NEEDED for static files!
        response = requests.get(fastapi_url, timeout=10)
        
        if response.status_code == 200:
            # Return the image
            django_response = HttpResponse(
                response.content,
                content_type=response.headers.get('Content-Type', 'image/jpeg')
            )
            
            # Cache for 1 hour (optional)
            django_response['Cache-Control'] = 'public, max-age=3600'
            
            return django_response
        else:
            logger.error(f"FastAPI static endpoint error {response.status_code}: {fastapi_url}")
            
            # Try the old API endpoint as fallback (for backward compatibility)
            old_url = f"{fastapi_base_url}/api/v1/files/processed/images/{filename}"
            api_key = getattr(settings, 'FASTAPI_API_KEY', '')
            headers = {'X-API-Key': api_key} if api_key else {}
            
            fallback_response = requests.get(old_url, headers=headers, timeout=10)
            if fallback_response.status_code == 200:
                logger.info(f"Used fallback API endpoint for: {filename}")
                return HttpResponse(
                    fallback_response.content,
                    content_type=fallback_response.headers.get('Content-Type', 'image/jpeg')
                )
            
            return HttpResponse(
                f"Error {response.status_code} from FastAPI static endpoint",
                status=response.status_code
            )
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in image proxy: {e}")
        return HttpResponse(f"Error fetching image: {str(e)}", status=500)
    except Exception as e:
        logger.error(f"Unexpected error in image proxy: {e}")
        return HttpResponse(f"Internal server error: {str(e)}", status=500)

# ============================================================================
# CAMERA GROUP VIEWS
# ============================================================================

# Camera Group Views
class CameraGroupListView(LoginRequiredMixin, ListView):
    """List all camera groups."""
    model = CameraGroup
    template_name = 'cameras/group_list.html'
    context_object_name = 'groups'
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()

class CameraGroupCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new camera group."""
    model = CameraGroup
    form_class = CameraGroupForm
    template_name = 'cameras/group_form.html'
    success_url = reverse_lazy('cameras:group_list')
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Camera group created successfully!'))
        return response

class CameraGroupUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update a camera group."""
    model = CameraGroup
    form_class = CameraGroupForm
    template_name = 'cameras/group_form.html'
    success_url = reverse_lazy('cameras:group_list')
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Camera group updated successfully!'))
        return response

class CameraGroupDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a camera group."""
    model = CameraGroup
    template_name = 'cameras/group_confirm_delete.html'
    success_url = reverse_lazy('cameras:group_list')
    
    def test_func(self):
        """Check if user can manage cameras."""
        return self.request.user.can_manage_cameras()
    
    def form_valid(self, form):
        group_name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, _(f'Camera group "{group_name}" deleted!'))
        return response

# ============================================================================
# LEGACY VIDEO PROCESSING (Old system - keep for backward compatibility)
# ============================================================================

@login_required
def video_upload_view(request):
    """Legacy video upload view (for backward compatibility)."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to upload videos.'))
        return redirect('cameras:list')
    
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save(commit=False)
            video.uploaded_by = request.user
            video.file_size = video.video_file.size
            video.save()
            
            messages.success(request, _('Video uploaded successfully! Please use the new media upload system for processing.'))
            return redirect('cameras:video_detail', pk=video.pk)
    else:
        form = VideoUploadForm()
    
    context = {
        'form': form,
        'title': _('Upload Video (Legacy System)'),
    }
    return render(request, 'cameras/video_upload.html', context)

@login_required
def video_list_view(request):
    """Legacy video list view."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to view videos.'))
        return redirect('cameras:list')
    
    videos = VideoFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    context = {
        'videos': videos,
        'title': _('Legacy Video Uploads'),
    }
    return render(request, 'cameras/video_list.html', context)

@login_required
def video_upload_list_functional(request):
    """List all video uploads (legacy)."""
    video_files = VideoFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    context = {
        'video_files': video_files,
    }
    return render(request, 'cameras/video_upload_list.html', context)

@login_required
def video_upload_create_functional(request):
    """Upload a video file (legacy)."""
    if request.method == 'POST':
        form = VideoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video_file = form.save(commit=False)
            video_file.uploaded_by = request.user
            video_file.save()
            messages.success(request, 'Video uploaded successfully!')
            return redirect('cameras:video_upload_list_functional')
    else:
        form = VideoUploadForm()
    
    context = {'form': form}
    return render(request, 'cameras/video_upload_form.html', context)

@login_required
def video_detail_view(request, pk):
    """Legacy video detail view."""
    video = get_object_or_404(VideoFile, pk=pk)
    
    # Check permission
    if video.uploaded_by != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to view this video.'))
        return redirect('cameras:video_list')
    
    context = {
        'video': video,
        'results': video.results_json if video.results_json else {},
    }
    return render(request, 'cameras/video_detail.html', context)

@login_required
def video_processing_status(request, pk):
    """Legacy video processing status (AJAX endpoint)."""
    video = get_object_or_404(VideoFile, pk=pk)
    
    if video.uploaded_by != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    return JsonResponse({
        'status': video.processing_status,
        'progress': video.get_progress_percentage(),
        'processed_frames': video.processed_frames,
        'total_frames': video.total_frames,
        'detection_count': video.detection_count,
        'is_completed': video.processing_status == VideoFile.ProcessingStatus.COMPLETED,
    })

# ============================================================================
# API ENDPOINTS FOR JAVASCRIPT/AJAX
# ============================================================================

@login_required
@require_GET
def api_media_status(request, media_id):
    """API endpoint for media processing status."""
    try:
        media_upload = MediaUpload.objects.get(id=media_id, uploaded_by=request.user)
        
        status_info = media_processor.check_processing_status(media_upload)
        
        # Add analysis data if available
        if hasattr(media_upload, 'analysis_results'):
            status_info['analysis'] = {
                'total_detections': media_upload.analysis_results.total_detections,
                'person_count': media_upload.analysis_results.person_count,
                'vehicle_count': media_upload.analysis_results.vehicle_count,
            }
        
        return JsonResponse({
            'success': True,
            'data': status_info,
        })
        
    except MediaUpload.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Media not found',
        }, status=404)
    except Exception as e:
        logger.error(f"Error in API media status: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@login_required
@csrf_exempt
@require_POST
def api_process_media(request):
    """API endpoint for processing media via AJAX."""
    try:
        if not request.FILES.get('file'):
            return JsonResponse({
                'success': False,
                'error': 'No file provided',
            }, status=400)
        
        # Check FastAPI server health
        health_status = fastapi_client.check_health()
        if not health_status.get('healthy'):
            return JsonResponse({
                'success': False,
                'error': f"FastAPI server unavailable: {health_status.get('status', 'unknown')}",
            }, status=503)
        
        # Create media upload
        file = request.FILES['file']
        title = request.POST.get('title', file.name)
        description = request.POST.get('description', '')
        detection_types = request.POST.getlist('detection_types', ['person', 'vehicle'])
        
        # Determine media type
        filename = file.name.lower()
        if any(filename.endswith(ext) for ext in settings.ALLOWED_IMAGE_EXTENSIONS):
            media_type = MediaUpload.MediaType.IMAGE
        elif any(filename.endswith(ext) for ext in settings.ALLOWED_VIDEO_EXTENSIONS):
            media_type = MediaUpload.MediaType.VIDEO
        else:
            return JsonResponse({
                'success': False,
                'error': 'Unsupported file format',
            }, status=400)
        
        # Create media upload
        media_upload = MediaUpload.objects.create(
            title=title,
            description=description,
            media_type=media_type,
            original_file=file,
            uploaded_by=request.user,
            file_size=file.size,
            mime_type=file.content_type,
        )
        
        # Start processing
        processing_result = media_processor.process_media_upload(
            media_upload=media_upload,
            detection_types=detection_types,
            request_base64=True
        )
        
        # Generate thumbnail
        media_processor.generate_thumbnail(media_upload)
        
        return JsonResponse({
            'success': processing_result['success'],
            'media_id': media_upload.id,
            'message': processing_result.get('message', ''),
            'job_id': processing_result.get('job_id'),
            'redirect_url': f'/cameras/media/{media_upload.id}/',
        })
        
    except Exception as e:
        logger.error(f"Error in API process media: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@login_required
@require_GET
def api_get_key_frame(request, media_id, frame_index):
    """API endpoint to get a specific key frame as data URL."""
    try:
        media_upload = MediaUpload.objects.get(id=media_id, uploaded_by=request.user)
        
        if not media_upload.is_video():
            return JsonResponse({
                'success': False,
                'error': 'Not a video',
            }, status=400)
        
        if not media_upload.key_frames_base64:
            return JsonResponse({
                'success': False,
                'error': 'No key frames available',
            }, status=404)
        
        frame_index = int(frame_index)
        if frame_index < 0 or frame_index >= len(media_upload.key_frames_base64):
            return JsonResponse({
                'success': False,
                'error': 'Frame index out of range',
            }, status=400)
        
        base64_img = media_upload.key_frames_base64[frame_index]
        data_url = base64_processor.create_data_url(base64_img, 'image/jpeg')
        
        return JsonResponse({
            'success': True,
            'frame_index': frame_index,
            'total_frames': len(media_upload.key_frames_base64),
            'data_url': data_url,
        })
        
    except MediaUpload.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Media not found',
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting key frame: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

@login_required
@require_GET
def api_get_processed_image(request, media_id):
    """API endpoint to get processed image as data URL."""
    try:
        media_upload = MediaUpload.objects.get(id=media_id, uploaded_by=request.user)
        
        if not media_upload.is_image():
            return JsonResponse({
                'success': False,
                'error': 'Not an image',
            }, status=400)
        
        # Try to get from analysis results first
        if hasattr(media_upload, 'analysis_results') and media_upload.analysis_results.has_base64_image():
            base64_img = media_upload.analysis_results.processed_image_base64
        elif media_upload.processed_file_base64:
            base64_img = media_upload.processed_file_base64
        else:
            return JsonResponse({
                'success': False,
                'error': 'No processed image available',
            }, status=404)
        
        data_url = base64_processor.create_data_url(base64_img, 'image/jpeg')
        
        return JsonResponse({
            'success': True,
            'media_id': media_id,
            'data_url': data_url,
        })
        
    except MediaUpload.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Media not found',
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting processed image: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)

# ============================================================================
# UTILITY VIEWS
# ============================================================================

@login_required
def processing_dashboard(request):
    """Dashboard showing all processing jobs."""
    # Get media uploads in progress
    processing_media = MediaUpload.objects.filter(
        uploaded_by=request.user,
        processing_status__in=[
            MediaUpload.ProcessingStatus.PROCESSING,
            MediaUpload.ProcessingStatus.PENDING,
            MediaUpload.ProcessingStatus.RETRYING,
        ]
    ).order_by('-uploaded_at')
    
    # Get recently completed
    completed_media = MediaUpload.objects.filter(
        uploaded_by=request.user,
        processing_status=MediaUpload.ProcessingStatus.COMPLETED
    ).order_by('-processing_completed')[:10]
    
    # Get failed
    failed_media = MediaUpload.objects.filter(
        uploaded_by=request.user,
        processing_status=MediaUpload.ProcessingStatus.FAILED
    ).order_by('-uploaded_at')[:10]
    
    # FastAPI status
    fastapi_health = fastapi_client.check_health()
    
    context = {
        'processing_media': processing_media,
        'completed_media': completed_media,
        'failed_media': failed_media,
        'fastapi_healthy': fastapi_health.get('healthy', False),
        'fastapi_status': fastapi_health.get('status', 'unknown'),
    }
    
    return render(request, 'cameras/processing_dashboard.html', context)

def health_check(request):
    """Health check endpoint for monitoring."""
    # Check database
    try:
        from django.db import connection
        connection.ensure_connection()
        db_healthy = True
    except Exception:
        db_healthy = False
    
    # Check FastAPI
    fastapi_health = fastapi_client.check_health()
    
    # Check media storage
    try:
        from django.core.files.storage import default_storage
        test_file = 'health_check.txt'
        default_storage.save(test_file, ContentFile(b'test'))
        default_storage.delete(test_file)
        storage_healthy = True
    except Exception:
        storage_healthy = False
    
    overall_healthy = db_healthy and fastapi_health.get('healthy', False) and storage_healthy
    
    return JsonResponse({
        'healthy': overall_healthy,
        'timestamp': timezone.now().isoformat(),
        'services': {
            'database': db_healthy,
            'fastapi': fastapi_health.get('healthy', False),
            'storage': storage_healthy,
        },
        'fastapi_details': fastapi_health,
    })

# ============================================================================
# MISC VIEWS
# ============================================================================

@login_required
def test_fastapi_connection(request):
    """Test FastAPI connection and API key."""
    from .services.fastapi_client import FastAPIClient
    
    client = FastAPIClient()
    
    # Test connection
    is_healthy = client.check_health()
    
    return JsonResponse({
        'fastapi_url': client.base_url,
        'api_key_first_10': client.api_key[:10] + '...' if client.api_key else 'None',
        'api_key_length': len(client.api_key) if client.api_key else 0,
        'is_healthy': is_healthy,
        'settings_fastapi_key': settings.FASTAPI_API_KEY,
        'settings_fastapi_url': settings.FASTAPI_BASE_URL,
    })

# Add this missing function for the legacy redirect URL
@login_required
def analysis_results_redirect(request, upload_id=None):
    """
    Redirect for backward compatibility from 'analysis_results' to 'media_analysis_results'.
    """
    if upload_id:
        # Redirect to specific media analysis result
        return redirect('cameras:media_analysis_results', upload_id=upload_id)
    else:
        # No specific ID - redirect to media gallery
        messages.info(request, 'Please select a media upload to view results.')
        return redirect('cameras:media_gallery')