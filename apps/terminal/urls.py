from django.urls import path
from .views import TerminalView

urlpatterns = [
    path('<uuid:instance_id>/', TerminalView.as_view(), name='terminal-view'),
]

