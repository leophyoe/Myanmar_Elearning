import os
from .base import *

DEBUG = True

# Ensure ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS allow 192.168.100.7 and all devices on LAN
for host in ['192.168.100.7', '0.0.0.0', '127.0.0.1', 'localhost', '*']:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

for origin in [
    'http://192.168.100.7:8000',
    'http://192.168.100.7:8080',
    'http://192.168.100.7:3000',
    'http://192.168.100.7',
    'http://localhost:8000',
    'http://localhost:8080',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8080',
]:
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)


# Database Configuration
# Uses PostgreSQL if DB_ENGINE or POSTGRES_HOST is provided, otherwise falls back to SQLite for local development/testing.
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', '')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'cyberrange_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'cyberrange_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'cyberrange_secure_password_2026!')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')

if POSTGRES_HOST and POSTGRES_HOST not in ('localhost', '127.0.0.1'):
    import socket
    can_resolve = False
    try:
        socket.gethostbyname(POSTGRES_HOST)
        can_resolve = True
    except socket.gaierror:
        can_resolve = False

    if can_resolve:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': POSTGRES_DB,
                'USER': POSTGRES_USER,
                'PASSWORD': POSTGRES_PASSWORD,
                'HOST': POSTGRES_HOST,
                'PORT': POSTGRES_PORT,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Email Backend for Development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# In local dev/testing, Celery can execute synchronously if REDIS is unreachable
if os.environ.get('CELERY_ALWAYS_EAGER', 'False').lower() in ('true', '1'):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

