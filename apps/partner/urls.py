from django.urls import path
from .views import (
    PartnerPortalDashboardView, InstitutionListView, InstitutionDetailView,
    CohortDetailView, InstitutionListAPIView, PartnerPortalStatsAPIView,
    PartnerCourseListView, PartnerCourseCreateView,
    PartnerEnrollmentListView, PartnerInstructorManageView,
    PartnerRevenueReportView,
    PartnerApplyView, PartnerApplySuccessView,
    PartnerInviteStudentView, PartnerInvitationAcceptView, PartnerInvitationDeclineView,
    PartnerCohortExportCSVView, PartnerCohortEnrollStudentView, PartnerEnrollmentExportCSVView,
)

urlpatterns = [
    path('', PartnerPortalDashboardView.as_view(), name='partner-portal-home'),
    path('portal/', PartnerPortalDashboardView.as_view(), name='partner-portal'),
    path('dashboard/', PartnerPortalDashboardView.as_view(), name='partner-dashboard'),
    path('directory/', InstitutionListView.as_view(), name='partner-list'),
    path('directory/<slug:slug>/', InstitutionDetailView.as_view(), name='partner-detail'),
    path('cohorts/<uuid:cohort_id>/', CohortDetailView.as_view(), name='partner-cohort-detail'),
    path('cohorts/<uuid:cohort_id>/export/csv/', PartnerCohortExportCSVView.as_view(), name='partner-cohort-export-csv'),
    path('cohorts/<uuid:cohort_id>/students/add/', PartnerCohortEnrollStudentView.as_view(), name='partner-cohort-enroll-student'),

    # Phase 2 — Institutional Course & Staff Management
    path('courses/', PartnerCourseListView.as_view(), name='partner-courses'),
    path('courses/create/', PartnerCourseCreateView.as_view(), name='partner-course-create'),
    path('enrollments/', PartnerEnrollmentListView.as_view(), name='partner-enrollments'),
    path('enrollments/export/csv/', PartnerEnrollmentExportCSVView.as_view(), name='partner-enrollments-export-csv'),
    path('instructors/', PartnerInstructorManageView.as_view(), name='partner-instructors'),

    # Phase 4 — Partner Revenue & Financial Accounting
    path('revenue/', PartnerRevenueReportView.as_view(), name='partner-revenue-report'),

    # Partner Application & Student Invitation Workflow
    path('apply/', PartnerApplyView.as_view(), name='partner-apply'),
    path('apply/success/', PartnerApplySuccessView.as_view(), name='partner-apply-success'),
    path('students/invite/', PartnerInviteStudentView.as_view(), name='partner-invite-student'),
    path('invitations/<uuid:pk>/accept/', PartnerInvitationAcceptView.as_view(), name='partner-invitation-accept'),
    path('invitations/<uuid:pk>/decline/', PartnerInvitationDeclineView.as_view(), name='partner-invitation-decline'),

    # REST APIs
    path('api/institutions/', InstitutionListAPIView.as_view(), name='api-partner-institutions'),
    path('api/portal/stats/', PartnerPortalStatsAPIView.as_view(), name='api-partner-stats'),
]
