# smart_surveillance/dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main entry point - redirects based on role
    path('', views.index, name='index'),
    
    # Role-specific dashboards (simplified to 3 roles)
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('viewer/', views.viewer_dashboard, name='viewer_dashboard'),
    
    # Common dashboard components
    path('notifications/', views.notifications_view, name='notifications'),
    path('activity-log/', views.activity_log_view, name='activity_log'),
    
    # Legacy route for compatibility
    path('home/', views.dashboard_home, name='home'),
]