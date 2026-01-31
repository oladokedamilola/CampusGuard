from django.urls import path
from . import views

app_name = 'cameras'

urlpatterns = [
    # ============================================
    # CAMERA MANAGEMENT URLs
    # ============================================
    
    # Camera URLs
    path('', views.CameraListView.as_view(), name='list'),
    path('dashboard/', views.camera_dashboard, name='dashboard'),
    path('create/', views.CameraCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CameraDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CameraUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.CameraDeleteView.as_view(), name='delete'),
    path('bulk-toggle/', views.bulk_toggle_cameras, name='bulk_toggle'),
    path('<int:pk>/toggle/', views.toggle_camera_status, name='toggle_status'),
    path('export/', views.export_cameras, name='export'),
    path('<int:pk>/health-check/', views.camera_health_check, name='health_check'),
    
    # Camera Group URLs
    path('groups/', views.CameraGroupListView.as_view(), name='group_list'),
    path('groups/create/', views.CameraGroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/edit/', views.CameraGroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.CameraGroupDeleteView.as_view(), name='group_delete'),
    
    # ============================================
    # LEGACY VIDEO PROCESSING URLs (for backward compatibility)
    # ============================================
    
    # Video upload and processing (legacy)
    path('videos/legacy/', views.video_list_view, name='video_list'),
    path('videos/legacy/upload/', views.video_upload_view, name='video_upload'),
    path('videos/legacy/<int:pk>/', views.video_detail_view, name='video_detail'),
    path('videos/legacy/<int:pk>/status/', views.video_processing_status, name='video_status'),
    
    # ============================================
    # NEW MEDIA UPLOAD SYSTEM URLs (with FastAPI)
    # ============================================
    
    # Media Upload URLs
    path('media/selection/', views.media_selection, name='media_selection'),
    path('media/upload/', views.upload_media, name='upload_media'),
    path('media/gallery/', views.media_gallery, name='media_gallery'),
    path('media/<int:upload_id>/status/', views.media_processing_status, name='media_processing_status'),
    path('media/<int:upload_id>/results/', views.media_analysis_results, name='media_analysis_results'),
    path('media/<int:upload_id>/delete/', views.delete_media_upload, name='media_delete'),
    path('media/<int:upload_id>/status-json/', views.get_processing_status, name='media_status_json'),
    path('media/health-check/', views.fastapi_health_check, name='fastapi_health_check'),
    
    
    # Live camera configuration and streaming URLs
    path('configure/', views.configure_camera, name='configure_camera'),
    path('configure/<int:camera_id>/', views.configure_camera, name='configure_camera_detail'),
    path('live/<int:camera_id>/', views.live_stream, name='live_stream'),
    
    
    # Legacy redirect URLs for template compatibility
    path('analysis-results/', views.analysis_results_redirect, name='analysis_results'),
    path('analysis-results/<int:upload_id>/', views.analysis_results_redirect, name='analysis_results_detail'),
    
    
    
    path('test-fapi/', views.test_fastapi_connection, name='test_fastapi'),
]