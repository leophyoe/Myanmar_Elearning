from django.urls import path
from .views import NotificationCenterView, MarkNotificationReadView, MarkAllNotificationsReadView

app_name = 'notifications'

urlpatterns = [
    path('', NotificationCenterView.as_view(), name='center'),
    path('<uuid:pk>/read/', MarkNotificationReadView.as_view(), name='mark-read'),
    path('mark-all-read/', MarkAllNotificationsReadView.as_view(), name='mark-all-read'),
]

