import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import Alert, AlertRule, NotificationPreference
from incidents.models import Incident
from accounts.models import User

logger = logging.getLogger(__name__)

class AlertService:
    """Service for creating and sending alerts."""
    
    @staticmethod
    def create_incident_alert(incident, camera):
        """
        Create alerts for a new incident from a live camera.
        
        Args:
            incident: Incident object
            camera: Camera object that detected the incident
        
        Returns:
            List of created Alert objects
        """
        # Skip if incident is from video upload (not live camera)
        if incident.video_file:
            logger.info(f"Skipping alerts for incident from video upload: {incident.incident_id}")
            return []
        
        # Get active alert rules
        rules = AlertRule.objects.filter(is_active=True)
        
        created_alerts = []
        
        for rule in rules:
            if rule.should_trigger(incident=incident, camera=camera):
                recipients = rule.get_recipients()
                
                for recipient in recipients:
                    # Check user preferences
                    pref = AlertService._get_user_preferences(recipient)
                    if not pref or not pref.should_receive_alert(
                        incident.incident_type, incident.severity
                    ):
                        continue
                    
                    # Create alert
                    alert = AlertService._create_alert_for_recipient(
                        rule=rule,
                        incident=incident,
                        camera=camera,
                        recipient=recipient,
                        preferences=pref
                    )
                    
                    if alert:
                        created_alerts.append(alert)
        
        # Send alerts immediately (could be async in production)
        for alert in created_alerts:
            AlertService._send_alert(alert)
        
        logger.info(f"Created {len(created_alerts)} alerts for incident {incident.incident_id}")
        return created_alerts
    
    @staticmethod
    def create_camera_status_alert(camera, status, reason=""):
        """
        Create alerts for camera status changes.
        
        Args:
            camera: Camera object
            status: New status (offline, error, etc.)
            reason: Reason for status change
        
        Returns:
            List of created Alert objects
        """
        # Only alert for offline/error status
        if status not in ['offline', 'error']:
            return []
        
        # Get rules for camera status alerts
        rules = AlertRule.objects.filter(
            is_active=True,
            trigger_type='camera_status',
            condition_operator='equals',
            condition_value=status
        )
        
        created_alerts = []
        
        for rule in rules:
            if rule.should_trigger(camera=camera):
                recipients = rule.get_recipients()
                
                for recipient in recipients:
                    # Check user preferences
                    pref = AlertService._get_user_preferences(recipient)
                    if not pref or not pref.email_enabled:
                        continue
                    
                    # Create alert
                    alert = Alert.objects.create(
                        title=f"Camera {camera.name} is {status}",
                        message=f"Camera {camera.name} at {camera.location.name} is {status}. {reason}",
                        alert_type='camera_offline',
                        camera=camera,
                        recipient=recipient,
                        channels=['email'],  # Camera status only via email
                        metadata={
                            'severity': 'high',
                            'camera_id': camera.id,
                            'camera_name': camera.name,
                            'status': status,
                            'reason': reason,
                        }
                    )
                    
                    created_alerts.append(alert)
        
        # Send alerts
        for alert in created_alerts:
            AlertService._send_alert(alert)
        
        return created_alerts
    
    @staticmethod
    def _get_user_preferences(user):
        """Get user notification preferences."""
        try:
            return NotificationPreference.objects.get(user=user)
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            return NotificationPreference.objects.create(
                user=user,
                email_enabled=True,
                in_app_enabled=True,
                severity_preferences=['medium', 'high', 'critical']
            )
    
    @staticmethod
    def _create_alert_for_recipient(rule, incident, camera, recipient, preferences):
        """Create an alert for a specific recipient."""
        # Determine channels based on preferences
        channels = []
        if 'email' in rule.channels and preferences.email_enabled:
            channels.append('email')
        if 'in_app' in rule.channels and preferences.in_app_enabled:
            channels.append('in_app')
        
        if not channels:
            return None
        
        # Format message
        message = rule.format_message(incident=incident, camera=camera)
        
        # Create alert
        alert = Alert.objects.create(
            title=f"Incident {incident.incident_id}: {incident.title}",
            message=message,
            alert_type='incident_detected',
            incident=incident,
            camera=camera,
            recipient=recipient,
            channels=channels,
            metadata={
                'severity': incident.severity,
                'incident_id': incident.incident_id,
                'incident_type': incident.incident_type,
                'camera_id': camera.id,
                'camera_name': camera.name,
                'rule_id': rule.id,
                'rule_name': rule.name,
            }
        )
        
        return alert
    
    @staticmethod
    def _send_alert(alert):
        """Send alert through configured channels."""
        try:
            # Send via each channel
            for channel in alert.channels:
                if channel == 'email':
                    AlertService._send_email_alert(alert)
                elif channel == 'in_app':
                    AlertService._send_in_app_alert(alert)
            
            alert.mark_as_sent('system')
            logger.info(f"Alert {alert.alert_id} sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send alert {alert.alert_id}: {str(e)}")
            alert.mark_as_failed('system', str(e))
    
    @staticmethod
    def _send_email_alert(alert):
        """Send alert via email."""
        try:
            # Prepare email content
            subject = f"[Smart Surveillance] {alert.title}"
            
            # Use email template if available, otherwise plain message
            if alert.incident and alert.incident.alertrule_set.exists():
                rule = alert.incident.alertrule_set.first()
                if rule.email_template:
                    html_message = rule.email_template.format(
                        incident_id=alert.incident.incident_id,
                        incident_title=alert.incident.title,
                        camera_name=alert.camera.name if alert.camera else 'N/A',
                        detected_at=alert.incident.detected_at.strftime('%Y-%m-%d %H:%M:%S'),
                        message=alert.message
                    )
                else:
                    html_message = render_to_string('alerts/email_incident.html', {
                        'alert': alert,
                        'incident': alert.incident,
                        'camera': alert.camera,
                    })
            else:
                html_message = alert.message
            
            # Send email
            send_mail(
                subject=subject,
                message=alert.message,  # Plain text fallback
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[alert.recipient.email],
                fail_silently=False,
            )
            
            alert.email_sent = True
            alert.mark_as_delivered('email')
            logger.info(f"Email sent for alert {alert.alert_id} to {alert.recipient.email}")
            
        except Exception as e:
            logger.error(f"Failed to send email for alert {alert.alert_id}: {str(e)}")
            raise
    
    @staticmethod
    def _send_in_app_alert(alert):
        """Store in-app notification (will be displayed in UI)."""
        # Just mark as delivered since it's stored in DB
        alert.mark_as_delivered('in_app')
        logger.info(f"In-app alert created: {alert.alert_id}")

class AlertCleanupService:
    """Service for cleaning up old alerts."""
    
    @staticmethod
    def cleanup_old_alerts(days_old=30):
        """
        Delete alerts older than specified days.
        
        Args:
            days_old: Delete alerts older than this many days
        
        Returns:
            Number of alerts deleted
        """
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        old_alerts = Alert.objects.filter(created_at__lt=cutoff_date)
        
        count = old_alerts.count()
        old_alerts.delete()
        
        logger.info(f"Deleted {count} alerts older than {days_old} days")
        return count
    
    @staticmethod
    def retry_failed_alerts():
        """Retry sending failed alerts."""
        failed_alerts = Alert.objects.filter(
            status='failed',
            retry_count__lt=3
        )
        
        retried_count = 0
        
        for alert in failed_alerts:
            try:
                AlertService._send_alert(alert)
                retried_count += 1
            except Exception as e:
                logger.error(f"Failed to retry alert {alert.alert_id}: {str(e)}")
                alert.increment_retry()
        
        logger.info(f"Retried {retried_count} failed alerts")
        return retried_count

class UserNotificationService:
    """Service for user notification management."""
    
    @staticmethod
    def get_unread_alerts(user):
        """Get unread in-app alerts for a user."""
        return Alert.objects.filter(
            recipient=user,
            channels__contains='in_app',
            is_read=False
        ).order_by('-created_at')
    
    @staticmethod
    def get_recent_alerts(user, limit=10):
        """Get recent alerts for a user."""
        return Alert.objects.filter(
            recipient=user
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all user's alerts as read."""
        updated = Alert.objects.filter(
            recipient=user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return updated