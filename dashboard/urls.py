# smart_surveillance/dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main entry point - redirects based on role
    path('', views.index, name='index'),
    
    # Role-specific dashboards
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('security-manager/', views.security_manager_dashboard, name='security_manager_dashboard'),
    path('security-guard/', views.security_guard_dashboard, name='security_guard_dashboard'),
    path('ict-staff/', views.ict_dashboard, name='ict_dashboard'),
    path('institution-admin/', views.institution_admin_dashboard, name='institution_admin_dashboard'),
    path('viewer/', views.viewer_dashboard, name='viewer_dashboard'),
    
    # Common dashboard components
    path('notifications/', views.notifications_view, name='notifications'),
    path('activity-log/', views.activity_log_view, name='activity_log'),

    path('', views.dashboard_home, name='index'),
    path('quick-stats/', views.quick_stats, name='quick_stats'),
]

