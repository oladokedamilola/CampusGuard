from django.urls import path
from . import views

app_name = 'cameras'

urlpatterns = [
    # Camera URLs
    path('', views.CameraListView.as_view(), name='list'),
    path('dashboard/', views.camera_dashboard, name='dashboard'),
    path('create/', views.CameraCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CameraDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CameraUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.CameraDeleteView.as_view(), name='delete'),
    path('<int:pk>/toggle/', views.toggle_camera_status, name='toggle_status'),
    path('<int:pk>/health-check/', views.camera_health_check, name='health_check'),
    
    # Camera Group URLs
    path('groups/', views.CameraGroupListView.as_view(), name='group_list'),
    path('groups/create/', views.CameraGroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/edit/', views.CameraGroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.CameraGroupDeleteView.as_view(), name='group_delete'),
    
    
    # Video upload and processing
    path('videos/', views.video_list_view, name='video_list'),
    path('videos/upload/', views.video_upload_view, name='video_upload'),
    path('videos/<int:pk>/', views.video_detail_view, name='video_detail'),
    path('videos/<int:pk>/process/', views.start_video_processing, name='video_process'),
    path('videos/<int:pk>/status/', views.video_processing_status, name='video_status'),
]