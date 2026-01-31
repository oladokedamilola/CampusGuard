# smart_surveillance/core/context_processors.py

import datetime
from django.conf import settings
from datetime import datetime

def error_context(request):
    """
    Context processor for error pages.
    """
    return {
        'site_name': 'CampusGuard AI',
        'support_email': 'support@campusguard.ai',
        'current_year': datetime.now().year,
        'is_debug': settings.DEBUG,
    }