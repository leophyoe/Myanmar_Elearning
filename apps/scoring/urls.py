from django.urls import path
from .views import LeaderboardView

urlpatterns = [
    path('', LeaderboardView.as_view(), name='leaderboard'),
]

