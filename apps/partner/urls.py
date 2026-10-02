from django.urls import path
from .views import (
    PartnerPortalDashboardView, InstitutionListView, InstitutionDetailView,
    CohortDetailView, InstitutionListAPIView, PartnerPortalStatsAPIView
)

urlpatterns = [
    path('portal/', PartnerPortalDashboardView.as_view(), name='partner-portal'),
    path('directory/', InstitutionListView.as_view(), name='partner-list'),
    path('directory/<slug:slug>/', InstitutionDetailView.as_view(), name='partner-detail'),
    path('cohorts/<uuid:cohort_id>/', CohortDetailView.as_view(), name='partner-cohort-detail'),

    # REST APIs
    path('api/institutions/', InstitutionListAPIView.as_view(), name='api-partner-institutions'),
    path('api/portal/stats/', PartnerPortalStatsAPIView.as_view(), name='api-partner-stats'),
]
