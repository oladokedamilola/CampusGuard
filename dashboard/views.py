# smart_surveillance/dashboard/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from accounts.decorators import role_required, role_redirect
from accounts.models import User
from cameras.models import Camera, CameraGroup
from django.utils import timezone
from datetime import timedelta
import random

@login_required
@role_redirect
def index(request):
    """
    Main dashboard entry point that redirects users based on their role.
    This view acts as a bridge/router.
    """
    # The role_redirect decorator handles the redirection
    pass

# ===== ROLE-SPECIFIC DASHBOARDS =====

@login_required
@role_required(['admin'])
def admin_dashboard(request):
    """Dashboard for System Administrators."""
    # Get real statistics
    total_users = User.objects.count()
    total_cameras = Camera.objects.count()
    active_cameras = Camera.objects.filter(is_active=True, status='active').count()
    
    # Get camera status breakdown
    camera_statuses = Camera.objects.values('status').annotate(count=Count('id'))
    status_counts = {status['status']: status['count'] for status in camera_statuses}
    
    # Get recent users (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_users = User.objects.filter(date_joined__gte=seven_days_ago).count()
    
    # Get camera groups
    camera_groups = CameraGroup.objects.all()[:5]
    
    # Quick actions
    quick_actions = [
        {'title': 'Manage Users', 'url': '#', 'icon': 'users', 'color': 'primary'},
        {'title': 'Camera Setup', 'url': 'cameras:list', 'icon': 'video', 'color': 'success'},
        {'title': 'System Settings', 'url': 'admin:index', 'icon': 'cogs', 'color': 'warning'},
        {'title': 'View Reports', 'url': '#', 'icon': 'chart-bar', 'color': 'info'},
        {'title': 'Media Analysis', 'url': 'cameras:media_selection', 'icon': 'cloud-upload-alt', 'color': 'secondary'},
        {'title': 'Database', 'url': 'admin:index', 'icon': 'database', 'color': 'dark'},
    ]
    
    # System health metrics (simulated for now)
    system_health = {
        'database': 'Healthy',
        'api_connection': 'Connected' if random.random() > 0.1 else 'Warning',
        'storage': '85% used',
        'last_backup': (timezone.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M'),
        'security_status': 'All systems secure',
    }
    
    context = {
        'title': 'System Administrator Dashboard',
        'page_title': 'Administrator Control Panel',
        'stats': {
            'total_users': total_users,
            'recent_users': recent_users,
            'total_cameras': total_cameras,
            'active_cameras': active_cameras,
            'offline_cameras': status_counts.get('offline', 0),
            'maintenance_cameras': status_counts.get('maintenance', 0),
        },
        'quick_actions': quick_actions,
        'system_health': system_health,
        'camera_groups': camera_groups,
        'recent_activities': [
            {'time': '10 min ago', 'action': f'User "{request.user.email}" logged in', 'type': 'login'},
            {'time': '1 hour ago', 'action': 'Database maintenance completed', 'type': 'system'},
            {'time': '2 hours ago', 'action': 'System backup completed successfully', 'type': 'backup'},
            {'time': '5 hours ago', 'action': '3 new cameras added to Building A', 'type': 'camera'},
            {'time': 'Yesterday', 'action': 'Security audit completed', 'type': 'security'},
        ]
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
@role_required(['security_manager'])
def security_manager_dashboard(request):
    """Dashboard for Security Managers."""
    context = {
        'title': _('Security Manager Dashboard'),
        'page_title': _('Security Operations Center'),
        'stats': {
            'active_incidents': 0,
            'resolved_today': 0,
            'guards_on_duty': 0,
            'cameras_online': 0,
        },
        'quick_actions': [
            {'title': _('Monitor Cameras'), 'url': '#', 'icon': 'video'},
            {'title': _('Manage Incidents'), 'url': '#', 'icon': 'exclamation-triangle'},
            {'title': _('Guard Roster'), 'url': '#', 'icon': 'user-shield'},
            {'title': _('Generate Reports'), 'url': '#', 'icon': 'file-alt'},
        ],
    }
    return render(request, 'dashboard/security_manager_dashboard.html', context)

@login_required
@role_required(['security_guard'])
def security_guard_dashboard(request):
    """Dashboard for Security Guards."""
    context = {
        'title': 'Security Guard Dashboard',
        'page_title': 'Security Monitoring Panel',
        'assigned_cameras': Camera.objects.filter(is_active=True)[:6],
        'current_shift': 'Day Shift (08:00 - 16:00)',
    }
    return render(request, 'dashboard/security_guard_dashboard.html', context)

@login_required
@role_required(['ict_staff'])
def ict_dashboard(request):
    """Dashboard for ICT Staff."""
    context = {
        'title': 'ICT Staff Dashboard',
        'page_title': 'Technical Operations Center',
        'stats': {
            'total_cameras': Camera.objects.count(),
            'network_health': '98%',
            'storage_usage': '1.2TB / 2TB',
            'api_status': 'Online',
        }
    }
    return render(request, 'dashboard/ict_staff_dashboard.html', context)

@login_required
@role_required(['institution_admin'])
def institution_admin_dashboard(request):
    """Dashboard for Institution Administrators."""
    context = {
        'title': 'Institution Administrator Dashboard',
        'page_title': 'Institution Overview',
        'stats': {
            'total_staff': User.objects.count(),
            'active_cameras': Camera.objects.filter(is_active=True).count(),
            'monthly_incidents': 0,
            'system_uptime': '99.9%',
        }
    }
    return render(request, 'dashboard/institution_admin_dashboard.html', context)

def viewer_dashboard(request):
    """Dashboard for Viewers (Read-only)."""
    context = {
        'title': 'Viewer Dashboard',
        'page_title': 'Monitoring Dashboard',
        'stats': {
            'live_cameras': Camera.objects.filter(is_active=True, status='active').count(),
            'system_status': 'All systems operational',
        }
    }
    return render(request, 'dashboard/viewer_dashboard.html', context)



# ===== COMMON DASHBOARD COMPONENTS =====

@login_required
def notifications_view(request):
    """Display user notifications."""
    context = {
        'title': _('Notifications'),
        'notifications': request.user.notification_set.all()[:50],  # You'll need to create this model
    }
    return render(request, 'dashboard/notifications.html', context)

@login_required
def activity_log_view(request):
    """Display user activity log."""
    context = {
        'title': _('Activity Log'),
        'activities': [],  # Populate with activity log entries
    }
    return render(request, 'dashboard/activity_log.html', context)

class DashboardBaseView(TemplateView):
    """Base view for all dashboards with common context."""
    template_name = 'dashboard/base_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['current_role'] = self.request.user.get_role_display()
        context['user_permissions'] = self.request.user.get_permission_codes()
        return context




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