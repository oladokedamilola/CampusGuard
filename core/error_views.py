# smart_surveillance/core/views/error_views.py
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def handler400(request, exception=None):
    """
    Custom 400 Bad Request error page.
    """
    logger.warning(f"400 Bad Request: {request.path} - Exception: {exception}")
    
    context = {
        'error_code': 400,
        'error_title': _('Bad Request'),
        'error_message': _('The server could not understand your request.'),
        'error_description': _('Please check your request and try again.'),
        'exception': str(exception) if exception else None,
        'request_path': request.path,
    }
    
    return render(request, 'errors/400.html', context, status=400)

def handler403(request, exception=None):
    """
    Custom 403 Forbidden error page.
    """
    logger.warning(f"403 Forbidden: {request.path} - User: {request.user} - Exception: {exception}")
    
    context = {
        'error_code': 403,
        'error_title': _('Access Forbidden'),
        'error_message': _('You do not have permission to access this page.'),
        'error_description': _('Please contact your administrator if you believe this is an error.'),
        'exception': str(exception) if exception else None,
        'request_path': request.path,
        'user': request.user,
    }
    
    return render(request, 'errors/403.html', context, status=403)

def handler404(request, exception=None):
    """
    Custom 404 Not Found error page.
    """
    logger.warning(f"404 Not Found: {request.path} - Exception: {exception}")
    
    context = {
        'error_code': 404,
        'error_title': _('Page Not Found'),
        'error_message': _('The page you are looking for does not exist.'),
        'error_description': _('Please check the URL or navigate back to the homepage.'),
        'exception': str(exception) if exception else None,
        'request_path': request.path,
    }
    
    return render(request, 'errors/404.html', context, status=404)

def handler500(request):
    """
    Custom 500 Internal Server Error page.
    """
    logger.error(f"500 Internal Server Error: {request.path}")
    
    context = {
        'error_code': 500,
        'error_title': _('Internal Server Error'),
        'error_message': _('Something went wrong on our end.'),
        'error_description': _('Our team has been notified and is working to fix the issue.'),
        'request_path': request.path,
    }
    
    # In production, you might want to send an email notification here
    if not settings.DEBUG:
        from django.core.mail import mail_admins
        mail_admins(
            subject=f"500 Error on {settings.SITE_NAME}",
            message=f"500 Internal Server Error occurred at {request.path}\n\nUser: {request.user}\nIP: {request.META.get('REMOTE_ADDR')}",
            fail_silently=True
        )
    
    return render(request, 'errors/500.html', context, status=500)

def handler503(request, exception=None):
    """
    Custom 503 Service Unavailable error page (for maintenance mode).
    """
    logger.warning(f"503 Service Unavailable: {request.path}")
    
    context = {
        'error_code': 503,
        'error_title': _('Service Unavailable'),
        'error_message': _('The system is currently undergoing maintenance.'),
        'error_description': _('Please try again later. We apologize for the inconvenience.'),
        'exception': str(exception) if exception else None,
        'request_path': request.path,
        'maintenance_message': getattr(settings, 'MAINTENANCE_MESSAGE', ''),
        'estimated_downtime': getattr(settings, 'ESTIMATED_DOWNTIME', ''),
    }
    
    return render(request, 'errors/503.html', context, status=503)

def handler_csrf_failure(request, reason=""):
    """
    Custom CSRF failure page.
    """
    logger.warning(f"CSRF Failure: {request.path} - Reason: {reason}")
    
    context = {
        'error_code': 403,
        'error_title': _('Security Error'),
        'error_message': _('Invalid or missing security token.'),
        'error_description': _('This request was blocked for security reasons. Please try again.'),
        'reason': reason,
        'request_path': request.path,
    }
    
    return render(request, 'errors/csrf.html', context, status=403)

def custom_error_test(request, error_code=None):
    """
    View for testing custom error pages (only in DEBUG mode).
    """
    if not settings.DEBUG:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Error testing is only available in DEBUG mode.")
    
    error_code = error_code or 404
    
    error_views = {
        400: handler400,
        403: handler403,
        404: handler404,
        500: handler500,
        503: handler503,
    }
    
    view = error_views.get(error_code, handler404)
    return view(request, exception=f"Test error for code {error_code}")