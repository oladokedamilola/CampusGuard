# smart_surveillance/accounts/context_processors.py
def notification_context(request):
    """Add notification count to all templates."""
    context = {}
    
    if request.user.is_authenticated:
        # Check if user has received_alerts attribute
        if hasattr(request.user, 'received_alerts'):
            unread_count = request.user.received_alerts.filter(is_read=False).count()
            context['unread_notifications_count'] = unread_count
        else:
            context['unread_notifications_count'] = 0
    else:
        context['unread_notifications_count'] = 0
    
    return context