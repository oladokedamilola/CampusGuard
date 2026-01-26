from django.urls import path
from . import views

app_name = 'alerts'

urlpatterns = [
    # User alert views
    path('', views.AlertListView.as_view(), name='list'),
    path('<int:pk>/', views.alert_detail, name='detail'),
    path('<int:pk>/read/', views.mark_alert_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_alerts_as_read, name='mark_all_read'),
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # Alert rule management (admin only)
    path('rules/', views.AlertRuleListView.as_view(), name='rule_list'),
    path('rules/create/', views.AlertRuleCreateView.as_view(), name='rule_create'),
    path('rules/<int:pk>/edit/', views.AlertRuleUpdateView.as_view(), name='rule_edit'),
    path('rules/<int:pk>/delete/', views.AlertRuleDeleteView.as_view(), name='rule_delete'),
    path('rules/<int:pk>/toggle/', views.toggle_alert_rule, name='rule_toggle'),
    
    # API endpoints
    path('api/unread-count/', views.get_unread_alerts_count, name='api_unread_count'),
    path('api/recent-alerts/', views.get_recent_alerts, name='api_recent_alerts'),
]