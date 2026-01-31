from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
import mimetypes
import os
import json
import threading
from django.core.files.storage import default_storage
import logging
from .models import Camera, CameraGroup, CameraHealthLog, MediaUpload, MediaAnalysisResult, VideoFile
from .forms import CameraForm, CameraGroupForm, CameraFilterForm, VideoUploadForm, VideoProcessingForm
from core.models import Location
from .services.media_processor import MediaProcessor

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
        messages.info(request, _('Please select a media upload to view results.'))
        return redirect('cameras:media_gallery')
    

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

# ============================================
# LEGACY VIDEO PROCESSING (Old system - keep for backward compatibility)
# ============================================

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

# ============================================
# NEW MEDIA UPLOAD SYSTEM (with FastAPI integration)
# ============================================
@login_required
def media_selection(request):
    """
    Page for selecting upload or live camera.
    """
    return render(request, 'cameras/media_selection.html')

@login_required
def upload_media(request):
    """
    Handle media upload (both images and videos) for FastAPI processing.
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
            
            # Start processing
            success = processor.process_media_upload(media_upload, detection_types)
            
            if success:
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': f'{media_type.capitalize()} uploaded successfully and processing started!',
                        'upload_id': media_upload.id
                    })
                messages.success(request, f'{media_type.capitalize()} uploaded successfully and processing started!')
                return redirect('cameras:media_processing_status', upload_id=media_upload.id)
            else:
                if is_ajax:
                    return JsonResponse({'error': 'Failed to start processing. Please try again.'}, status=500)
                messages.error(request, 'Failed to start processing. Please try again.')
                return redirect('cameras:upload_media')
                
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
def media_analysis_results(request, upload_id):
    """
    Show analysis results for completed media upload.
    """
    media_upload = get_object_or_404(MediaUpload, id=upload_id, uploaded_by=request.user)
    
    # Check if processing is complete
    if media_upload.processing_status != MediaUpload.ProcessingStatus.COMPLETED:
        messages.warning(request, 'Analysis is still in progress. Please wait.')
        return redirect('cameras:media_processing_status', upload_id=upload_id)
    
    # Get analysis results
    try:
        analysis_results = media_upload.analysis_results
    except MediaAnalysisResult.DoesNotExist:
        # Try to create from response data
        processor = MediaProcessor()
        processor._create_analysis_results(media_upload, media_upload.response_data)
        analysis_results = media_upload.analysis_results
    
    return render(request, 'cameras/media_analysis_results.html', {
        'media_upload': media_upload,
        'analysis_results': analysis_results
    })

@login_required
@require_http_methods(['GET'])
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
def media_gallery(request):
    """
    Show gallery of all media uploads by user.
    """
    media_uploads = MediaUpload.objects.filter(
        uploaded_by=request.user
    ).order_by('-uploaded_at')
    
    return render(request, 'cameras/media_gallery.html', {
        'media_uploads': media_uploads
    })

@login_required
def delete_media_upload(request, upload_id):
    """
    Delete a media upload and associated files.
    """
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
    
from django.conf import settings    
    
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