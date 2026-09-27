import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

django_asgi_app = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack

    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        # WebSocket channels will be connected for future real-time notifications/lab terminals
    })
except ImportError:
    application = django_asgi_app

