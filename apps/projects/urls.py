from django.urls import path
from .views import (
    ProjectListView,
    ProjectProposalSubmitView,
    ProjectSubmissionDetailView,
    ProjectReportUploadView,
)

urlpatterns = [
    path('', ProjectListView.as_view(), name='project-list'),
    path('<slug:slug>/proposal/', ProjectProposalSubmitView.as_view(), name='project-submit-proposal'),
    path('<slug:slug>/submission/', ProjectSubmissionDetailView.as_view(), name='project-submission-detail'),
    path('<slug:slug>/upload-report/', ProjectReportUploadView.as_view(), name='project-upload-report'),
    path('<slug:slug>/submit-report/', ProjectReportUploadView.as_view(), name='project-submit-report'),
]
