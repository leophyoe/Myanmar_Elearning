import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

try:
    from celery import Celery
    app = Celery('cyberrange')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()
    app.conf.beat_schedule = {
        'reap-expired-labs-every-minute': {
            'task': 'apps.labs.tasks.reap_expired_labs',
            'schedule': 60.0,
        },
        'sync-lab-telemetry-every-5-minutes': {
            'task': 'apps.labs.tasks.collect_resource_telemetry',
            'schedule': 300.0,
        },
    }
except ImportError:
    app = None

