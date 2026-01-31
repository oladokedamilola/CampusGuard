"""
Production settings for PythonAnywhere deployment.
"""
from .base import *
import os

# Security settings for production
DEBUG = False
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']

# Database (PythonAnywhere MySQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'yourusername$smart_surveillance',
        'USER': 'yourusername',
        'PASSWORD': os.getenv('PYTHONANYWHERE_DB_PASSWORD'),
        'HOST': 'yourusername.mysql.pythonanywhere-services.com',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

# Static files
STATIC_ROOT = '/home/yourusername/smart_surveillance/staticfiles'
STATIC_URL = '/static/'

# Media files (limited to 512MB on free tier)
MEDIA_ROOT = '/home/yourusername/smart_surveillance/media'
MEDIA_URL = '/media/'

# Email configuration (use PythonAnywhere SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Or your email provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

# File upload limits (for free tier)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
MAX_UPLOAD_SIZE = 10485760  # 10MB

# Session settings (filesystem based for free tier)
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = '/tmp/django_sessions'

# Disable background tasks (not available on free tier)
CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None

# Computer vision settings
CV_SETTINGS = {
    'MAX_IMAGE_SIZE': 1024,  # Resize images to max 1024px
    'MAX_VIDEO_DURATION': 30,  # 30 seconds max
    'MAX_VIDEO_FRAMES': 900,   # 30 seconds at 30fps
    'USE_LIGHTWEIGHT_MODELS': True,
    'ALLOW_REAL_TIME_PROCESSING': False,  # Disable for free tier
}