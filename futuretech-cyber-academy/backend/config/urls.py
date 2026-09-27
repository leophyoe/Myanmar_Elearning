import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import HomePageView, PlaceholderView

from apps.learning_paths.views import LearningPathListView
from apps.certificates.views import CertificateListView, PublicCertificateVerificationView
from apps.assessments.views import ExamPortalView, InstructorGradingQueueView
from apps.labs.views import (
    LabListView, ChallengeListView, LeaderboardView, CTFEventListView,
    LinuxChallengeListView, LinuxChallengeDetailView, HackerTestView
)

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Core Public Pages
    path('', HomePageView.as_view(), name='home'),
    path('about/', PlaceholderView.as_view(extra_context={'title': 'About Academy', 'section': 'about'}), name='about'),
    path('blog/', PlaceholderView.as_view(extra_context={'title': 'Security Intelligence Blog', 'section': 'blog'}), name='blog'),

    # Phase 2 Advanced LMS Apps & Named Shortcuts
    path('learning-paths/', include('apps.learning_paths.urls')),
    path('learning-paths/', LearningPathListView.as_view(), name='learning-paths'),
    path('assessments/', include('apps.assessments.urls')),
    path('exams/', ExamPortalView.as_view(), name='exams'),
    path('exams/', ExamPortalView.as_view(), name='exams-placeholder'),
    path('assignments/', InstructorGradingQueueView.as_view(), name='assignments'),
    path('assignments/', InstructorGradingQueueView.as_view(), name='assignments-placeholder'),
    path('certificates/', include('apps.certificates.urls')),
    path('certificates/', CertificateListView.as_view(), name='certificates'),
    path('certificates/', CertificateListView.as_view(), name='certificates-placeholder'),
    path('verify/<str:certificate_number>/', PublicCertificateVerificationView.as_view(), name='public-verify-root'),
    path('notifications/', include('apps.notifications.urls')),



    # Phase 3 Cyber Range & CTF Arena
    path('labs/', include('apps.labs.urls')),
    path('labs/', LabListView.as_view(), name='labs-placeholder'),
    path('ctf/', ChallengeListView.as_view(), name='ctf-placeholder'),
    path('ctf/linux/', LinuxChallengeListView.as_view(), name='linux-ctf-list'),
    path('ctf/linux/<slug:slug>/', LinuxChallengeDetailView.as_view(), name='linux-challenge-detail'),
    path('ctf/events/', CTFEventListView.as_view(), name='ctf-events'),
    path('challenges/hackertest/', HackerTestView.as_view(), name='hackertest-challenge'),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard-placeholder'),

    # Modular Academy Apps
    path('accounts/', include('apps.accounts.urls')),
    path('courses/', include('apps.courses.urls')),
    path('enrollments/', include('apps.enrollments.urls')),
    path('progress/', include('apps.progress.urls')),
    path('', include('apps.dashboard.urls')),

    # REST APIs
    path('api/', include('apps.core.api_urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

