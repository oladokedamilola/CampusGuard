# smart_surveillance/surveillance/urls.py
from django.urls import path
from . import views

app_name = 'surveillance'

urlpatterns = [
    # Image processing
    path('process-image/', views.process_image_view, name='process_image'),
    
    # Video processing
    path('process-video/', views.process_video_view, name='process_video'),
    path('process-video/<int:video_id>/', views.process_video_view, name='process_video_id'),
    path('video-job/<str:job_id>/', views.video_job_status_view, name='video_job_status'),
    path('video-job/<str:job_id>/json/', views.video_job_status_json, name='video_job_status_json'),
    path('video-job/<str:job_id>/cancel/', views.cancel_video_job, name='cancel_video_job'),
    
    # Camera demo
    path('demo-camera/', views.demo_camera_view, name='demo_camera'),
    path('analyze-camera/<int:camera_id>/', views.analyze_camera_feed, name='analyze_camera'),
    
    # API endpoints
    path('api/process-frame/', views.api_process_frame, name='api_process_frame'),
    path('api/fastapi-health/', views.fastapi_health_check, name='fastapi_health'),
    
    # Management
    path('my-processing-jobs/', views.my_processing_jobs_view, name='my_processing_jobs'),
    path('processing-results/', views.processing_results_view, name='processing_results'),

    # Analysis results viewing
    path('analysis-results/', views.processing_results_view, name='analysis_results'),
    path('analysis-results/<int:result_id>/', views.analysis_result_detail, name='analysis_result_detail'),

    # Image processing
    # path('process-image/', views.process_image_view, name='process_image'),
    
    # # Video processing
    # path('process-video/', views.process_video_view, name='process_video'),
    # path('process-video/<int:video_id>/', views.process_video_view, name='process_video_id'),
    
    # # Camera demo (simulated for free tier)
    # path('demo-camera/', views.demo_camera_view, name='demo_camera'),
    # path('analyze-camera/<int:camera_id>/', views.analyze_camera_feed, name='analyze_camera'),
    
    # # API endpoints
    # path('api/process-frame/', views.api_process_frame, name='api_process_frame'),
]