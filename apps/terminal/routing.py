from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/terminal/(?P<instance_id>[0-9a-fA-F-]+)/$', consumers.TerminalConsumer.as_asgi()),
]

