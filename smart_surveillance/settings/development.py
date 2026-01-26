"""
Development settings for smart_surveillance project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Development apps
# INSTALLED_APPS += [
#     'debug_toolbar',
# ]

# Development middleware
# MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# # Debug toolbar settings
# INTERNAL_IPS = [
#     '127.0.0.1',
# ]

# # Email backend for development
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# # Disable password validators for easier testing
# AUTH_PASSWORD_VALIDATORS = []