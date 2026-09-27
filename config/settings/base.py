import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'ftcr-insecure-dev-secret-key-change-in-production-cyber-range-2026!#'
)

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,web,0.0.0.0').split(',')
    if h.strip()
]

# Core Django Applications
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Third-Party Applications (Dynamically added if installed)
THIRD_PARTY_APPS = []

try:
    import rest_framework
    THIRD_PARTY_APPS.append('rest_framework')
except ImportError:
    pass

try:
    import channels
    THIRD_PARTY_APPS.append('channels')
except ImportError:
    pass

# Custom Myanmar E-Learning Modular Apps
LOCAL_APPS = [
    'apps.common',
    'apps.users',
    'apps.courses',
    'apps.labs',
    'apps.ctf',
    'apps.scoring',
    'apps.certificates',
    'apps.projects',
    'apps.analytics',
    'apps.terminal',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.analytics.middleware.ActivityAuditMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.common.context_processors.platform_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Custom Abstract User Model
AUTH_USER_MODEL = 'users.User'

# Authentication redirects (named URLs from apps.users.urls)
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing-page'

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Redis & Channels Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Platform Business Constants
PLATFORM_NAME = os.environ.get('PLATFORM_NAME', 'Myanmar E-Learning')
ORGANIZATION_NAME = os.environ.get('ORGANIZATION_NAME', PLATFORM_NAME)
DIPLOMA_PROGRAM_TITLE = os.environ.get('DIPLOMA_PROGRAM_TITLE', 'Diploma in Cyber Security')
DIPLOMA_DURATION_MONTHS = 10
LAB_DEFAULT_DURATION_MINUTES = int(os.environ.get('LAB_DEFAULT_DURATION_MINUTES', 90))
LAB_MAX_EXTENSIONS = int(os.environ.get('LAB_MAX_EXTENSIONS', 2))
LAB_EXTENSION_MINUTES = int(os.environ.get('LAB_EXTENSION_MINUTES', 30))
LAB_MAX_CONCURRENT_PER_USER = int(os.environ.get('LAB_MAX_CONCURRENT_PER_USER', 1))
FLAG_SALT = os.environ.get('FLAG_SALT', 'ftcr_dynamic_salt_2026_secure')
FLAG_PREFIX = os.environ.get('FLAG_PREFIX', 'FTCR{')
FLAG_SUFFIX = os.environ.get('FLAG_SUFFIX', '}')

