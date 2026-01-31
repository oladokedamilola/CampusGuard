from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cameras/', include('cameras.urls')),
    path('incidents/', include('incidents.urls')),
    path('dashboard/', include('dashboard.urls')), 
    path('alerts/', include('alerts.urls')),
    path('', include('landing.urls')),    # Landing page URLs
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)