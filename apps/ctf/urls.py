from django.urls import path
from .views import CtfBoardView, FlagSubmitView

urlpatterns = [
    path('', CtfBoardView.as_view(), name='ctf-board'),
    path('<uuid:challenge_id>/submit/', FlagSubmitView.as_view(), name='flag-submit'),
]

