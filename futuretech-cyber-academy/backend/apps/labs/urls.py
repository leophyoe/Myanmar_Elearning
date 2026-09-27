from django.urls import path
from .views import (
    LabListView, LabDetailView,
    LabStartView, LabStopView, LabResetView,
    LabExtendView, LabStatusView, LabTerminalView,
    LabGatewayView, LabAiHintView,
    ChallengeListView, ChallengeDetailView,
    LeaderboardView, CTFEventListView,
    LinuxLabListView, LinuxChallengeListView, LinuxChallengeDetailView, HackerTestView
)

app_name = 'labs'

urlpatterns = [
    # Labs & Machines Catalog
    path('', LabListView.as_view(), name='lab-list'),
    path('linux/', LinuxLabListView.as_view(), name='linux-lab-list'),
    path('machines/', LabListView.as_view(), name='machine-list'),

    # Challenges & CTF
    path('challenges/', ChallengeListView.as_view(), name='challenge-list'),
    path('challenges/hackertest/', HackerTestView.as_view(), name='hackertest-resource-internal'),
    path('challenges/<slug:slug>/', ChallengeDetailView.as_view(), name='challenge-detail'),
    path('ctf/linux/', LinuxChallengeListView.as_view(), name='linux-ctf-list-internal'),
    path('ctf/linux/<slug:slug>/', LinuxChallengeDetailView.as_view(), name='linux-challenge-detail-internal'),
    path('events/', CTFEventListView.as_view(), name='event-list'),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),

    # Lab Instance Controls & Terminal Gateway
    path('<slug:slug>/start/', LabStartView.as_view(), name='lab-start'),
    path('<slug:slug>/stop/', LabStopView.as_view(), name='lab-stop'),
    path('<slug:slug>/reset/', LabResetView.as_view(), name='lab-reset'),
    path('<slug:slug>/extend/', LabExtendView.as_view(), name='lab-extend'),
    path('<slug:slug>/status/', LabStatusView.as_view(), name='lab-status'),
    path('<slug:slug>/terminal/', LabTerminalView.as_view(), name='lab-terminal'),

    # Controlled Reverse-Proxy Gateway & Web Security Workspace
    path('i/<uuid:token>/', LabGatewayView.as_view(), name='lab-gateway'),
    path('i/<uuid:token>/hint/', LabAiHintView.as_view(), name='lab-ai-hint'),

    # Lab Details Briefing
    path('<slug:slug>/', LabDetailView.as_view(), name='lab-detail'),
]

