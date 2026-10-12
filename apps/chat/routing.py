from django.urls import re_path
from apps.chat import consumers

websocket_urlpatterns = [
    re_path(r'^ws/chat/(?P<conversation_id>[0-9a-fA-F-]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'^ws/chat/$', consumers.ChatConsumer.as_asgi()),
]

