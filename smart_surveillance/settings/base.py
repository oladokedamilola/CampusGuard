# Django base settings for smart_surveillance project.
# smart_surveillance/settings/base.py
import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-91g18xno8ih_wm7$9r=kwpg1*(6z&ksrqny_q95*nv*75!rh=!'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
     # Local apps
    'core',
    'accounts',
    'cameras',
    'incidents',
    'dashboard',
    'surveillance',
    'analytics',
    'alerts',
    'landing',
    'reports',
    
    # Third-party apps
    'django_extensions',
    'crispy_forms',
    'crispy_bootstrap5',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smart_surveillance.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
         'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                
                'core.context_processors.error_context',
                'accounts.context_processors.notification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_surveillance.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'


# Custom user model
AUTH_USER_MODEL = 'accounts.User'


AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailBackend',  # Custom email backend
    'django.contrib.auth.backends.ModelBackend',  # Default backend (fallback)
]

# Email Configuration
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('DJANGO_EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('DJANGO_EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('DJANGO_EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'CampusGuard AI <noreply@campusguard.ai>')

# Session Settings
SESSION_ENGINE = os.getenv('SESSION_ENGINE', 'django.contrib.sessions.backends.db')
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', 600))
SESSION_SAVE_EVERY_REQUEST = os.getenv('SESSION_SAVE_EVERY_REQUEST', 'True') == 'True'
SESSION_EXPIRE_AT_BROWSER_CLOSE = os.getenv('SESSION_EXPIRE_AT_BROWSER_CLOSE', 'True') == 'True'

# Token Expiry Times
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 10))
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = int(os.getenv('PASSWORD_RESET_TOKEN_EXPIRY_HOURS', 1))

# ============================================================================
# FastAPI Processing Server Configuration - UPDATED FOR BASE64 INTEGRATION
# ============================================================================
FASTAPI_CONFIG = {
    'BASE_URL': os.environ.get('FASTAPI_BASE_URL', 'http://localhost:8001'),
    'API_KEY': os.environ.get('FASTAPI_API_KEY', 'a3f8e97b12c450d6f34a8921b567d0e9f12a34b5678c9d0e1f23a45b67c89d012'),
    'TIMEOUT': 120,  # seconds for processing requests
    'RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 2,  # seconds between retries
    
    # Endpoints
    'ENDPOINTS': {
        'PROCESS_IMAGE': '/api/v1/process/image',
        'PROCESS_VIDEO': '/api/v1/process/video',
        'JOB_STATUS': '/api/v1/jobs/{job_id}/status',
        'HEALTH_CHECK': '/health',
    }
}

# Media upload settings
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']

# Base64 Processing Settings
BASE64_CONFIG = {
    'PROCESSED_IMAGES_DIR': 'processed/images/',
    'PROCESSED_VIDEOS_DIR': 'processed/videos/',
    'KEY_FRAMES_DIR': 'processed/key_frames/',
    'MAX_BASE64_SIZE': 50 * 1024 * 1024,  # 50MB max for base64 decoding
}

# If using Celery for background processing (recommended)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Custom Error Handlers
handler400 = 'core.error_views.handler400'
handler403 = 'core.error_views.handler403'
handler404 = 'core.error_views.handler404'
handler500 = 'core.error_views.handler500'
handler503 = 'core.error_views.handler503'

# Update CSRF failure view
CSRF_FAILURE_VIEW = 'core.error_views.handler_csrf_failure'

# Site Information
SITE_NAME = 'CampusGuard AI'
BASE_URL = 'http://localhost:8000'  # Change this in production

# Maintenance Mode Settings (optional)
MAINTENANCE_MODE = False
MAINTENANCE_MESSAGE = "The system is undergoing scheduled maintenance. We'll be back shortly!"
ESTIMATED_DOWNTIME = "30 minutes"

# Email settings for error notifications
ADMINS = [
    ('Admin Name', 'admin@campusguard.ai'),
]

# Create logs directory if it doesn't exist
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# Updated LOGGING configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[{server_time}] {message}',
            'style': '{',
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'errors.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_warnings': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'warnings.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_info': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'info.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
        'fastapi_debug': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'fastapi.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'file_info'],
            'level': 'INFO',
            'propagate': True,
        },
        'cameras': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'file_info', 'fastapi_debug'],
            'level': 'INFO',
            'propagate': True,
        },
        'alerts': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'file_info'],
            'level': 'INFO',
            'propagate': True,
        },
        'incidents': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'file_info'],
            'level': 'INFO',
            'propagate': True,
        },
        'surveillance': {
            'handlers': ['console', 'file_errors', 'file_warnings', 'file_info', 'fastapi_debug'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}