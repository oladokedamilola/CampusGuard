from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Count, Q

from incidents.models import Incident
from cameras.models import Camera, CameraHealthLog
from alerts.models import Alert

@login_required
def dashboard_home(request):
    """
    Main dashboard view with overview statistics and recent activity.
    """
    # Get current user and their institution
    user = request.user
    today = timezone.now().date()
    
    # Get incidents statistics
    incidents = Incident.objects.all()
    
    # For non-admin users, filter by their institution
    if not user.is_superuser and user.institution:
        incidents = incidents.filter(camera__location__institution=user.institution)
    
    # Calculate statistics
    total_incidents = incidents.count()
    today_incidents = incidents.filter(detected_at__date=today).count()
    open_incidents = incidents.exclude(status__in=['resolved', 'false_alarm']).count()
    critical_incidents = incidents.filter(severity='critical', status='detected').count()
    
    # Get recent incidents (last 24 hours)
    recent_incidents = incidents.filter(
        detected_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).select_related('camera', 'camera__location').order_by('-detected_at')[:10]
    
    # Get camera statistics
    cameras = Camera.objects.all()
    if not user.is_superuser and user.institution:
        cameras = cameras.filter(location__institution=user.institution)
    
    total_cameras = cameras.count()
    active_cameras = cameras.filter(is_active=True, status='active').count()
    offline_cameras = cameras.filter(status__in=['offline', 'error']).count()
    
    # Get recent camera health logs
    recent_health_issues = CameraHealthLog.objects.filter(
        camera__in=cameras,
        status__in=['offline', 'error'],
        recorded_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).select_related('camera').order_by('-recorded_at')[:5]
    
    # Get user's unread alerts
    unread_alerts = Alert.objects.filter(
        recipient=user,
        is_read=False
    ).count()
    
    # Get incidents by type (for chart)
    incidents_by_type = incidents.values('incident_type').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get incidents by severity (for chart)
    incidents_by_severity = incidents.values('severity').annotate(
        count=Count('id')
    ).order_by('severity')
    
    context = {
        'user': user,
        'today': today,
        
        # Incident statistics
        'total_incidents': total_incidents,
        'today_incidents': today_incidents,
        'open_incidents': open_incidents,
        'critical_incidents': critical_incidents,
        'recent_incidents': recent_incidents,
        
        # Camera statistics
        'total_cameras': total_cameras,
        'active_cameras': active_cameras,
        'offline_cameras': offline_cameras,
        'camera_uptime': (active_cameras / total_cameras * 100) if total_cameras > 0 else 0,
        'recent_health_issues': recent_health_issues,
        
        # Alert statistics
        'unread_alerts': unread_alerts,
        
        # Chart data
        'incidents_by_type': list(incidents_by_type),
        'incidents_by_severity': list(incidents_by_severity),
        
        # Permissions context
        'can_manage_cameras': user.can_manage_cameras(),
        'can_acknowledge_incidents': user.can_acknowledge_incidents(),
        'can_view_analytics': user.can_view_analytics(),
    }
    
    return render(request, 'dashboard/home.html', context)

@login_required
def quick_stats(request):
    """
    Quick stats view for HTMX updates.
    """
    user = request.user
    today = timezone.now().date()
    
    # Get filtered incidents
    incidents = Incident.objects.all()
    if not user.is_superuser and user.institution:
        incidents = incidents.filter(camera__location__institution=user.institution)
    
    # Quick stats
    stats = {
        'today_incidents': incidents.filter(detected_at__date=today).count(),
        'open_incidents': incidents.exclude(status__in=['resolved', 'false_alarm']).count(),
        'critical_incidents': incidents.filter(severity='critical', status='detected').count(),
        'unread_alerts': Alert.objects.filter(recipient=user, is_read=False).count(),
    }
    
    return render(request, 'dashboard/partials/quick_stats.html', {'stats': stats})