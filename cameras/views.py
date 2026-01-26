from datetime import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy

from .models import Camera, CameraGroup, CameraHealthLog
from .forms import CameraForm, CameraGroupForm, CameraFilterForm
from core.models import Location

import os
import threading
from django.core.files.storage import default_storage
from django.http import JsonResponse
from .models import VideoFile
from .forms import VideoUploadForm, VideoProcessingForm


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
        
        # Get incidents for this camera (when incidents app is created)
        # context['recent_incidents'] = self.object.incidents.all()[:5]
        
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
    
    
@login_required
def video_upload_view(request):
    """Upload video file for processing."""
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
            
            messages.success(request, _('Video uploaded successfully! Processing will start soon.'))
            return redirect('cameras:video_detail', pk=video.pk)
    else:
        form = VideoUploadForm()
    
    context = {
        'form': form,
        'title': _('Upload Video for Analysis'),
    }
    return render(request, 'cameras/video_upload.html', context)

@login_required
def video_list_view(request):
    """List all uploaded videos."""
    if not request.user.can_manage_cameras():
        messages.error(request, _('You do not have permission to view videos.'))
        return redirect('cameras:list')
    
    videos = VideoFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    context = {
        'videos': videos,
        'title': _('My Uploaded Videos'),
    }
    return render(request, 'cameras/video_list.html', context)

@login_required
def video_detail_view(request, pk):
    """View video details and processing results."""
    video = get_object_or_404(VideoFile, pk=pk)
    
    # Check permission
    if video.uploaded_by != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to view this video.'))
        return redirect('cameras:video_list')
    
    if request.method == 'POST' and video.processing_status == VideoFile.ProcessingStatus.PENDING:
        form = VideoProcessingForm(request.POST)
        if form.is_valid():
            # Start processing in background
            from .tasks import process_video_task
            process_video_task.delay(video.pk, form.cleaned_data)
            
            video.processing_status = VideoFile.ProcessingStatus.PROCESSING
            video.save()
            
            messages.info(request, _('Video processing started in the background.'))
            return redirect('cameras:video_detail', pk=video.pk)
    else:
        form = VideoProcessingForm()
    
    context = {
        'video': video,
        'form': form,
        'results': video.results_json if video.results_json else {},
    }
    return render(request, 'cameras/video_detail.html', context)

@login_required
def video_processing_status(request, pk):
    """Get video processing status (AJAX endpoint)."""
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

@login_required
def start_video_processing(request, pk):
    """Start processing a video manually."""
    video = get_object_or_404(VideoFile, pk=pk)
    
    if video.uploaded_by != request.user and not request.user.is_superuser:
        messages.error(request, _('You do not have permission to process this video.'))
        return redirect('cameras:video_list')
    
    if video.processing_status != VideoFile.ProcessingStatus.PENDING:
        messages.warning(request, _('Video is already being processed or completed.'))
        return redirect('cameras:video_detail', pk=video.pk)
    
    # This would start actual OpenCV processing
    # For now, we'll simulate it
    video.processing_status = VideoFile.ProcessingStatus.PROCESSING
    video.processing_started = timezone.now()
    video.save()
    
    # In Phase 4, this will call OpenCV processing
    messages.info(request, _('Video processing started. Check back for results.'))
    
    return redirect('cameras:video_detail', pk=video.pk)