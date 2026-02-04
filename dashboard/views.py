# smart_surveillance/dashboard/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q

from accounts.decorators import role_required, role_redirect
from accounts.models import User
from reports.models import IncidentReport, IncidentCategory, IncidentLocation

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
@role_required([User.Role.ADMIN])
def admin_dashboard(request):
    """Dashboard for System Administrators."""
    
    # Get statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    pending_invitations = User.objects.filter(email_verified=False).count()
    
    # Report statistics
    total_reports = IncidentReport.objects.count()
    pending_reports = IncidentReport.objects.filter(status='pending').count()
    resolved_reports = IncidentReport.objects.filter(status='resolved').count()
    
    # Get recent users (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_users = User.objects.filter(date_joined__gte=seven_days_ago).count()
    
    # Get recent reports (last 7 days)
    recent_reports = IncidentReport.objects.filter(
        created_at__gte=seven_days_ago
    ).count()
    
    # Get user distribution by role
    users_by_role = User.objects.values('role').annotate(count=Count('id'))
    
    # Quick actions
    quick_actions = [
        {
            'title': _('Manage Users'), 
            'url': '/admin/accounts/user/', 
            'icon': 'users', 
            'color': 'primary',
            'description': _('Add, edit, or remove users')
        },
        {
            'title': _('Send Invitations'), 
            'url': '/admin/accounts/invitation/add/', 
            'icon': 'envelope', 
            'color': 'success',
            'description': _('Invite new users to the system')
        },
        {
            'title': _('System Settings'), 
            'url': '/admin/', 
            'icon': 'cogs', 
            'color': 'warning',
            'description': _('Configure system settings')
        },
        {
            'title': _('View All Reports'), 
            'url': '/reports/manager/dashboard/', 
            'icon': 'chart-bar', 
            'color': 'info',
            'description': _('View all incident reports')
        },
        {
            'title': _('Analytics'), 
            'url': '/reports/manager/analytics/', 
            'icon': 'chart-line', 
            'color': 'secondary',
            'description': _('View detailed analytics')
        },
        {
            'title': _('Categories & Locations'), 
            'url': '/admin/reports/incidentcategory/', 
            'icon': 'tags', 
            'color': 'dark',
            'description': _('Manage categories and locations')
        },
    ]
    
    context = {
        'title': _('System Administrator Dashboard'),
        'page_title': _('Administrator Control Panel'),
        'stats': {
            'total_users': total_users,
            'active_users': active_users,
            'pending_invitations': pending_invitations,
            'recent_users': recent_users,
            'total_reports': total_reports,
            'pending_reports': pending_reports,
            'resolved_reports': resolved_reports,
            'recent_reports': recent_reports,
        },
        'quick_actions': quick_actions,
        'users_by_role': users_by_role,
        'recent_activities': [
            {'time': '10 min ago', 'action': f'User "{request.user.email}" logged in', 'type': 'login'},
            {'time': '1 hour ago', 'action': 'System backup completed successfully', 'type': 'backup'},
            {'time': '2 hours ago', 'action': '3 new incident reports submitted', 'type': 'report'},
            {'time': '5 hours ago', 'action': 'Database maintenance completed', 'type': 'system'},
            {'time': 'Yesterday', 'action': 'Security audit completed', 'type': 'security'},
        ]
    }
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
@role_required([User.Role.MANAGER])
def manager_dashboard(request):
    """Dashboard for Security Managers."""
    
    # Get report statistics
    total_reports = IncidentReport.objects.count()
    pending_reports = IncidentReport.objects.filter(status='pending').count()
    processing_reports = IncidentReport.objects.filter(status='processing').count()
    resolved_reports = IncidentReport.objects.filter(status='resolved').count()
    
    # Get recent reports (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_reports = IncidentReport.objects.filter(created_at__gte=week_ago).count()
    
    # Get reports by category (top 5)
    reports_by_category = IncidentReport.objects.values(
        'category__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get reports by location (top 5)
    reports_by_location = IncidentReport.objects.values(
        'location__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get priority breakdown
    priority_counts = IncidentReport.objects.values('priority').annotate(count=Count('id'))
    
    # Get high priority reports
    high_priority_reports = IncidentReport.objects.filter(
        priority__in=['high', 'critical'],
        status='pending'
    ).count()
    
    # Quick actions for managers
    quick_actions = [
        {
            'title': _('Review Reports'), 
            'url': '/reports/manager/queue/', 
            'icon': 'inbox', 
            'color': 'primary',
            'description': _('Review and process new incident reports'),
            'badge': pending_reports if pending_reports > 0 else None
        },
        {
            'title': _('Active Cases'), 
            'url': '/reports/manager/cases/', 
            'icon': 'tasks', 
            'color': 'info',
            'description': _('Manage ongoing investigations'),
            'badge': processing_reports if processing_reports > 0 else None
        },
        {
            'title': _('Analytics'), 
            'url': '/reports/manager/analytics/', 
            'icon': 'chart-line', 
            'color': 'success',
            'description': _('View patterns and trends')
        },
        {
            'title': _('Search Reports'), 
            'url': '/reports/manager/search/', 
            'icon': 'search', 
            'color': 'warning',
            'description': _('Search and filter all reports')
        },
        {
            'title': _('All Reports'), 
            'url': '/reports/manager/dashboard/', 
            'icon': 'list', 
            'color': 'secondary',
            'description': _('View all incident reports')
        },
        {
            'title': _('Export Data'), 
            'url': '/reports/admin/export/', 
            'icon': 'download', 
            'color': 'dark',
            'description': _('Export reports for external use')
        },
    ]
    
    # Get recent reports for the activity feed
    recent_report_activity = IncidentReport.objects.select_related(
        'reporter', 'category', 'location'
    ).order_by('-created_at')[:5]
    
    context = {
        'title': _('Security Manager Dashboard'),
        'page_title': _('Security Operations Center'),
        'stats': {
            'total_reports': total_reports,
            'pending_reports': pending_reports,
            'processing_reports': processing_reports,
            'resolved_reports': resolved_reports,
            'recent_reports': recent_reports,
            'high_priority_reports': high_priority_reports,
        },
        'quick_actions': quick_actions,
        'reports_by_category': reports_by_category,
        'reports_by_location': reports_by_location,
        'priority_counts': priority_counts,
        'recent_report_activity': recent_report_activity,
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M'),
    }
    return render(request, 'dashboard/manager_dashboard.html', context)

@login_required
@role_required([User.Role.VIEWER])
def viewer_dashboard(request):
    """Dashboard for Viewers (Reporter role)."""
    
    # Get user's own report statistics
    my_reports = IncidentReport.objects.filter(reporter=request.user)
    total_my_reports = my_reports.count()
    pending_my_reports = my_reports.filter(status='pending').count()
    processing_my_reports = my_reports.filter(status='processing').count()
    resolved_my_reports = my_reports.filter(status='resolved').count()
    
    # Get recent reports from the user (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_my_reports = my_reports.filter(created_at__gte=week_ago).count()
    
    # Get user's recent reports for activity feed
    recent_reports = my_reports.order_by('-created_at')[:5]
    
    # Quick actions for viewers
    quick_actions = [
        {
            'title': _('Report Incident'), 
            'url': '/reports/new/', 
            'icon': 'flag', 
            'color': 'primary',
            'description': _('Report a new security incident')
        },
        {
            'title': _('My Reports'), 
            'url': '/reports/my/', 
            'icon': 'folder', 
            'color': 'info',
            'description': _('View all reports you submitted'),
            'badge': total_my_reports if total_my_reports > 0 else None
        },
        {
            'title': _('Add Images'), 
            'url': '#', 
            'icon': 'images', 
            'color': 'success',
            'description': _('Add images to existing reports')
        },
        {
            'title': _('Profile'), 
            'url': '/accounts/profile/', 
            'icon': 'user', 
            'color': 'warning',
            'description': _('Update your profile information')
        },
        {
            'title': _('Help Guide'), 
            'url': '#', 
            'icon': 'question-circle', 
            'color': 'secondary',
            'description': _('How to use the reporting system')
        },
        {
            'title': _('Contact Support'), 
            'url': '#', 
            'icon': 'headset', 
            'color': 'dark',
            'description': _('Get help from security team')
        },
    ]
    
    # Get system-wide statistics (limited view for viewers)
    system_stats = {
        'total_reports_system': IncidentReport.objects.count(),
        'resolved_rate': '85%',  # Example stat
        'response_time': '2-4 hours',  # Example stat
    }
    
    context = {
        'title': _('My Dashboard'),
        'page_title': _('Incident Reporting Dashboard'),
        'stats': {
            'total_my_reports': total_my_reports,
            'pending_my_reports': pending_my_reports,
            'processing_my_reports': processing_my_reports,
            'resolved_my_reports': resolved_my_reports,
            'recent_my_reports': recent_my_reports,
        },
        'quick_actions': quick_actions,
        'recent_reports': recent_reports,
        'system_stats': system_stats,
        'user': request.user,
    }
    return render(request, 'dashboard/viewer_dashboard.html', context)

# ===== COMMON DASHBOARD COMPONENTS =====

@login_required
def notifications_view(request):
    """Display user notifications."""
    # Placeholder for notifications - you can implement this later
    notifications = []
    
    context = {
        'title': _('Notifications'),
        'notifications': notifications,
    }
    return render(request, 'dashboard/notifications.html', context)

@login_required
def activity_log_view(request):
    """Display user activity log."""
    # Placeholder for activity log - you can implement this later
    activities = []
    
    context = {
        'title': _('Activity Log'),
        'activities': activities,
    }
    return render(request, 'dashboard/activity_log.html', context)

@login_required
def dashboard_home(request):
    """
    Legacy dashboard view - redirects to role-specific dashboard.
    """
    return redirect('dashboard:index')