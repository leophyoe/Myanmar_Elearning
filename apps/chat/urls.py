from django.urls import path
from apps.chat import views

app_name = 'chat'

urlpatterns = [
    path('', views.InboxView.as_view(), name='inbox'),
    path('start/', views.StartConversationView.as_view(), name='start-conversation-post'),
    path('start/<uuid:recipient_id>/', views.StartConversationView.as_view(), name='start-conversation'),
    path('api/unread/', views.UnreadCountAPIView.as_view(), name='api-unread-count'),
    path('api/recipients/', views.EligibleRecipientsAPIView.as_view(), name='api-recipients'),
    path('api/<uuid:conversation_id>/', views.ConversationMessagesAPIView.as_view(), name='api-messages'),
    path('api/<uuid:conversation_id>/send/', views.SendMessageAPIView.as_view(), name='api-send-message'),
    path('api/<uuid:conversation_id>/read/', views.MarkReadAPIView.as_view(), name='api-mark-read'),
    path('block/<uuid:user_id>/', views.BlockUserView.as_view(), name='block-user'),
    path('report/<uuid:message_id>/', views.ReportMessageView.as_view(), name='report-message'),
]

