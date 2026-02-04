# smart_surveillance/reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # ======================
    # VIEWER URLS
    # ======================
    path('', views.report_list, name='list'),
    path('new/', views.create_report, name='create'),
    path('my/', views.my_reports, name='my_reports'),
    path('<uuid:report_id>/', views.report_detail, name='detail'),
    path('<uuid:report_id>/add-image/', views.add_image, name='add_image'),
    
    # ======================
    # MANAGER URLS
    # ======================
    path('manager/queue/', views.reports_queue, name='reports_queue'),
    path('manager/process/<uuid:report_id>/', views.process_report, name='process_report'),
    path('manager/cases/', views.case_management, name='case_management'),
    path('manager/analytics/', views.analytics_dashboard, name='analytics'),
    path('manager/search/', views.search_reports, name='search'),
    path('manager/bulk-actions/', views.bulk_actions, name='bulk_actions'),
    
    # ======================
    # ADMIN URLS (Shared with Manager)
    # ======================
    path('admin/export/', views.export_reports, name='export_reports'),
    path('admin/system-stats/', views.system_statistics, name='system_stats'),
    
    # ======================
    # API ENDPOINTS
    # ======================
    path('api/get-locations/', views.get_locations, name='api_locations'),
    path('api/get-categories/', views.get_categories, name='api_categories'),
    path('api/report-stats/', views.report_statistics_api, name='api_report_stats'),
    path('api/analytics-data/', views.analytics_data_api, name='api_analytics_data'),
    
    # ======================
    # AJAX ENDPOINTS
    # ======================
    path('ajax/update-status/<uuid:report_id>/', views.ajax_update_status, name='ajax_update_status'),
    path('ajax/add-note/<uuid:report_id>/', views.ajax_add_note, name='ajax_add_note'),
    path('ajax/analyze-image/<uuid:image_id>/', views.ajax_analyze_image, name='ajax_analyze_image'),
    path('ajax/get-report-data/<uuid:report_id>/', views.ajax_get_report_data, name='ajax_get_report_data'),
]