# smart_surveillance/accounts/email_utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

def send_invitation_email(invitation, request=None):
    """Send invitation email to user."""
    try:
        # Build registration URL
        if request:
            scheme = 'https' if request.is_secure() else 'http'
            domain = request.get_host()
        else:
            scheme = 'http'
            domain = 'localhost:8000'  # Default for development
        
        registration_url = f"{scheme}://{domain}/accounts/register/{invitation.token}/"
        
        # Email context
        context = {
            'invitation': invitation,
            'registration_url': registration_url,
            'inviter': invitation.invited_by.get_full_name() or invitation.invited_by.email,
            'expires_at': invitation.expires_at,
            'role': invitation.get_role_display(),
        }
        
        # Render email content
        html_message = render_to_string('accounts/emails/invitation_email.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=_('Invitation to Join CampusGuard AI'),
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        # Update sent timestamp
        from django.utils import timezone
        invitation.sent_at = timezone.now()
        invitation.save()
        
        logger.info(f"Invitation email sent to {invitation.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send invitation email to {invitation.email}: {str(e)}")
        return False

def send_welcome_email(user, request=None):
    """Send welcome email to new user."""
    try:
        context = {
            'user': user,
            'login_url': f"{request.scheme}://{request.get_host()}/accounts/login/" if request else None,
        }
        
        html_message = render_to_string('accounts/emails/welcome_email.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=_('Welcome to CampusGuard AI!'),
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False