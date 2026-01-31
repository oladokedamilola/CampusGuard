# smart_surveillance/accounts/templatetags/user_tags.py
from django import template
from django.db.models import Count

register = template.Library()

@register.filter
def unread_alerts_count(user):
    """Return count of unread alerts for a user."""
    if hasattr(user, 'received_alerts'):
        return user.received_alerts.filter(is_read=False).count()
    return 0

@register.filter
def recent_alerts(user, limit=5):
    """Return recent alerts for a user."""
    if hasattr(user, 'received_alerts'):
        return user.received_alerts.filter(is_read=False).order_by('-created_at')[:limit]
    return []