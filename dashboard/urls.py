from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='index'),
    path('quick-stats/', views.quick_stats, name='quick_stats'),
]