# smart_surveillance/core/utils/error_utils.py
import logging
from django.core.mail import mail_admins
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

def log_error(error_type, request, exception=None, user=None):
    """
    Log errors with detailed information.
    """
    error_data = {
        'error_type': error_type,
        'timestamp': timezone.now().isoformat(),
        'path': request.path if request else None,
        'method': request.method if request else None,
        'user_agent': request.META.get('HTTP_USER_AGENT') if request else None,
        'ip_address': request.META.get('REMOTE_ADDR') if request else None,
        'user': str(user) if user else 'Anonymous',
        'exception': str(exception) if exception else None,
    }
    
    logger.error(f"{error_type} Error: {error_data}")
    
    return error_data

def notify_admins_about_error(error_data, subject_prefix="System Error"):
    """
    Send email notification to admins about critical errors.
    """
    if not settings.DEBUG:
        subject = f"[{settings.SITE_NAME}] {subject_prefix}: {error_data.get('error_type')}"
        
        message = f"""
        Error Type: {error_data.get('error_type')}
        Timestamp: {error_data.get('timestamp')}
        Path: {error_data.get('path')}
        Method: {error_data.get('method')}
        User: {error_data.get('user')}
        IP Address: {error_data.get('ip_address')}
        
        Exception Details:
        {error_data.get('exception', 'No exception details')}
        
        User Agent:
        {error_data.get('user_agent')}
        """
        
        try:
            mail_admins(subject, message, fail_silently=True)
            logger.info(f"Error notification sent to admins: {error_data.get('error_type')}")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

def get_client_ip(request):
    """
    Get client IP address from request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip