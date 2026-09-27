import os
from .base import *

DEBUG = True

# Adaptive Database: PostgreSQL if host provided, else SQLite for offline local dev/testing
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', '')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'futuretech_academy_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'futuretech_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'futuretech_secure_pass_2026!')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')

if POSTGRES_HOST and POSTGRES_HOST != 'localhost':
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

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

