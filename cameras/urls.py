# smart_surveillance/cameras/urls.py
from django.urls import path
from . import views

app_name = 'cameras'

urlpatterns = [
    # ============================================
    # CAMERA MANAGEMENT URLs
    # ============================================
    
    # Camera URLs (Class-Based Views)
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
    
    # Camera URLs (Functional Views - New)
    path('camera/list/', views.camera_list_functional, name='camera_list_functional'),
    path('camera/<str:camera_id>/', views.camera_detail_functional, name='camera_detail_functional'),
    path('camera/create/', views.camera_create_functional, name='camera_create_functional'),
    path('camera/<str:camera_id>/edit/', views.camera_update_functional, name='camera_update_functional'),
    path('camera/<str:camera_id>/delete/', views.camera_delete_functional, name='camera_delete_functional'),
    
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
    
    # Video upload URLs (Functional Views - New)
    path('videos/', views.video_upload_list_functional, name='video_upload_list_functional'),
    path('videos/upload/', views.video_upload_create_functional, name='video_upload_create_functional'),
    
    # ============================================
    # MEDIA SELECTION & GALLERY URLs
    # ============================================
    
    # Media selection page
    path('media/selection/', views.media_selection, name='media_selection'),
    
    # Media gallery
    path('media/gallery/', views.media_gallery, name='media_gallery'),
    
    # ============================================
    # MEDIA UPLOAD URLs
    # ============================================
    
    # New media upload (FastAPI integrated version) - MAIN UPLOAD
    path('media/upload/', views.media_upload_create, name='media_upload_create'),
    
    # Legacy media upload (for backward compatibility)
    path('media/upload/legacy/', views.upload_media, name='upload_media'),
    
    # ============================================
    # MEDIA MANAGEMENT URLs
    # ============================================
    
    # Media list
    path('media/', views.media_upload_list, name='media_upload_list'),
    
    # MAIN MEDIA ANALYSIS VIEW - uses upload_id parameter
    path('media/<int:upload_id>/analysis/', views.media_analysis_results, name='media_analysis_results'),
    
    # Media detail (redirects to analysis view)
    path('media/<int:media_id>/', views.media_upload_detail_functional, name='media_upload_detail'),
    
    # Media status checking
    path('media/<int:media_id>/status/', views.media_upload_status, name='media_upload_status'),
    
    # Alternative results URL (for backward compatibility)
    path('media/<int:upload_id>/results/', views.media_analysis_results, name='media_analysis_results_alt'),
    
    # Media actions
    path('media/<int:media_id>/retry/', views.media_upload_retry, name='media_upload_retry'),
    path('media/<int:media_id>/delete/', views.media_upload_delete, name='media_upload_delete'),
    
    # Legacy delete URL (for backward compatibility)
    path('media/<int:upload_id>/delete-legacy/', views.delete_media_upload, name='media_delete'),
    
    # ============================================
    # MEDIA STATUS URLs (AJAX/JSON)
    # ============================================
    
    path('media/<int:media_id>/status-ajax/', views.media_upload_status, name='media_upload_status_ajax'),
    path('media/<int:upload_id>/status-json/', views.get_processing_status, name='media_status_json'),
    
    # ============================================
    # FASTAPI INTEGRATION URLs
    # ============================================
    
    # FastAPI Status URLs
    path('fastapi/status/', views.fastapi_status, name='fastapi_status'),
    path('fastapi/status/json/', views.fastapi_status_json, name='fastapi_status_json'),
    path('media/health-check/', views.fastapi_health_check, name='fastapi_health_check'),
    path('test-fapi/', views.test_fastapi_connection, name='test_fastapi'),
    
    # FastAPI Demo URLs
    path('fastapi/demo/', views.process_demo_image, name='process_demo_image'),
    
    # ============================================
    # API ENDPOINTS URLs (for JavaScript/AJAX)
    # ============================================

    # Media Processing API
    path('api/media/<int:media_id>/status/', views.api_media_status, name='api_media_status'),
    path('api/media/process/', views.api_process_media, name='api_process_media'),
    path('api/media/<int:media_id>/processed-image/', views.api_get_processed_image, name='api_get_processed_image'),
    path('api/media/<int:media_id>/key-frame/<int:frame_index>/', views.api_get_key_frame, name='api_get_key_frame'),

    # ============================================
    # LIVE CAMERA & STREAMING URLs
    # ============================================
    
    # Live camera configuration and streaming URLs
    path('configure/', views.configure_camera, name='configure_camera'),
    path('configure/<int:camera_id>/', views.configure_camera, name='configure_camera_detail'),
    path('live/<int:camera_id>/', views.live_stream, name='live_stream'),
    
    # ============================================
    # PROCESSED IMAGE PROXY URLs
    # ============================================
    
    path('processed-images/<str:filename>/', views.processed_image_proxy, name='processed_image_proxy'),
    
    # ============================================
    # UTILITY & DASHBOARD URLs
    # ============================================
    
    # Processing Dashboard
    path('processing/dashboard/', views.processing_dashboard, name='processing_dashboard'),
    
    # Health Check
    path('health/', views.health_check, name='health_check'),
    
    # ============================================
    # LEGACY REDIRECT URLs (for template compatibility)
    # ============================================
    
    path('analysis-results/', views.analysis_results_redirect, name='analysis_results'),
    path('analysis-results/<int:upload_id>/', views.analysis_results_redirect, name='analysis_results_detail'),
]

# Optional: URL patterns for API versioning (if needed)
api_urlpatterns = [
    path('api/v1/media/<int:media_id>/status/', views.api_media_status, name='api_v1_media_status'),
    path('api/v1/media/process/', views.api_process_media, name='api_v1_process_media'),
    path('api/v1/media/<int:media_id>/processed-image/', views.api_get_processed_image, name='api_v1_get_processed_image'),
    path('api/v1/media/<int:media_id>/key-frame/<int:frame_index>/', views.api_get_key_frame, name='api_v1_get_key_frame'),
]