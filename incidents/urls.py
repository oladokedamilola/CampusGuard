from django.urls import path
from . import views

app_name = 'incidents'

urlpatterns = [
    # Incident URLs
    path('', views.IncidentListView.as_view(), name='list'),
    path('dashboard/', views.incident_dashboard, name='dashboard'),
    path('create/', views.IncidentCreateView.as_view(), name='create'),
    path('<int:pk>/', views.IncidentDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.IncidentUpdateView.as_view(), name='edit'),
    path('<int:pk>/acknowledge/', views.acknowledge_incident, name='acknowledge'),
    path('<int:pk>/resolve/', views.resolve_incident, name='resolve'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('<int:pk>/evidence/', views.upload_evidence, name='upload_evidence'),
    
    # Bulk actions
    path('bulk-action/', views.bulk_action, name='bulk_action'),
    
    # Export
    path('export/', views.incident_export, name='export'),
]