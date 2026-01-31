# smart_surveillance/core/middleware/maintenance_middleware.py
from django.http import HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class MaintenanceModeMiddleware:
    """
    Middleware to enable/disable maintenance mode.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if maintenance mode is enabled
        if getattr(settings, 'MAINTENANCE_MODE', False):
            # Allow access to admin, login, and error pages
            allowed_paths = [
                reverse('admin:index'),
                reverse('login'),
                reverse('logout'),
                '/static/',
                '/media/',
                '/maintenance/',  # Custom maintenance page if needed
            ]
            
            # Check if current path is allowed
            if not any(request.path.startswith(path) for path in allowed_paths):
                # If user is not staff/admin, redirect to maintenance page
                if not (request.user.is_authenticated and request.user.is_staff):
                    from ..views.error_views import handler503
                    return handler503(request)
        
        response = self.get_response(request)
        return response