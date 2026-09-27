"""URLs for the Cyber Range studio — one section for labs and challenges.

Mounted at ``/cyber/`` so the whole range (lab templates, lab exercises and
CTF challenges) lives behind a single route tree, mirroring the single
``cyber/`` content folder on disk.
"""

from django.urls import path

from apps.ctf.views import (
    ChallengeCreateView, ChallengeDeleteView, ChallengeManageListView,
    ChallengeUpdateView,
)
from .views import (
    CyberHomeView, LabBundleUploadView, LabCreateView, LabDeleteView,
    LabManageListView, LabTemplateBuildView, LabTemplateListView,
    LabTemplateUpdateView, LabUpdateView,
)

urlpatterns = [
    path('', CyberHomeView.as_view(), name='cyber-home'),

    path('labs/', LabManageListView.as_view(), name='cyber-lab-list'),
    path('labs/upload/', LabBundleUploadView.as_view(), name='cyber-lab-upload'),
    path('labs/new/', LabCreateView.as_view(), name='cyber-lab-create'),
    path('labs/<uuid:lab_id>/edit/', LabUpdateView.as_view(), name='cyber-lab-edit'),
    path('labs/<uuid:lab_id>/delete/', LabDeleteView.as_view(), name='cyber-lab-delete'),

    path('templates/', LabTemplateListView.as_view(), name='cyber-template-list'),
    path('templates/<uuid:template_id>/edit/',
         LabTemplateUpdateView.as_view(), name='cyber-template-edit'),
    path('templates/<uuid:template_id>/build/',
         LabTemplateBuildView.as_view(), name='cyber-template-build'),

    path('challenges/', ChallengeManageListView.as_view(), name='cyber-challenge-list'),
    path('challenges/new/', ChallengeCreateView.as_view(), name='cyber-challenge-create'),
    path('challenges/<uuid:challenge_id>/edit/',
         ChallengeUpdateView.as_view(), name='cyber-challenge-edit'),
    path('challenges/<uuid:challenge_id>/delete/',
         ChallengeDeleteView.as_view(), name='cyber-challenge-delete'),
]
