from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, ListView, DetailView
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Institution, InstitutionCohort, CohortStudent
from .serializers import InstitutionSerializer, InstitutionCohortSerializer


class PartnerPortalDashboardView(LoginRequiredMixin, TemplateView):
    """
    Institutional portal dashboard for University / College / Academy partners.
    Allows managing academic batches (cohorts), monitoring enrolled students, and tracking progress.
    """
    template_name = 'partner/portal_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_admin or request.user.is_partner):
            messages.error(request, "Access restricted to institutional partners and administrators.")
            return redirect('landing-page')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_admin:
            institutions = Institution.objects.all()
        else:
            institutions = Institution.objects.filter(contact_person=user)

        cohorts = InstitutionCohort.objects.filter(institution__in=institutions).select_related('institution', 'course')
        total_students = CohortStudent.objects.filter(cohort__in=cohorts).count()

        context['institutions'] = institutions
        context['cohorts'] = cohorts
        context['total_students'] = total_students
        context['active_cohorts_count'] = cohorts.filter(is_active=True).count()
        return context


class InstitutionListView(ListView):
    """
    Public directory of academic, school, and industry training partners.
    """
    model = Institution
    template_name = 'partner/institution_list.html'
    context_object_name = 'institutions'

    def get_queryset(self):
        return Institution.objects.filter(is_verified=True).order_by('name')


class InstitutionDetailView(DetailView):
    """
    Public profile of an educational partner institution.
    """
    model = Institution
    template_name = 'partner/institution_detail.html'
    context_object_name = 'institution'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cohorts'] = self.object.cohorts.filter(is_active=True).select_related('course')
        return context


class CohortDetailView(LoginRequiredMixin, DetailView):
    """
    Detailed cohort view showing roster of enrolled students.
    """
    model = InstitutionCohort
    template_name = 'partner/cohort_detail.html'
    context_object_name = 'cohort'
    pk_url_kwarg = 'cohort_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['students'] = self.object.students.select_related('student').order_by('student_id_number', 'student__username')
        return context


# -----------------------------------------------------------------------------
# REST API Endpoints
# -----------------------------------------------------------------------------

class InstitutionListAPIView(APIView):
    """
    GET /partner/api/institutions/
    List verified partner institutions.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        institutions = Institution.objects.filter(is_verified=True).order_by('name')
        serializer = InstitutionSerializer(institutions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PartnerPortalStatsAPIView(APIView):
    """
    GET /partner/api/portal/stats/
    Returns institutional metrics for authenticated partner.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.is_admin or user.is_partner):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        if user.is_admin:
            institutions = Institution.objects.all()
        else:
            institutions = Institution.objects.filter(contact_person=user)

        cohorts = InstitutionCohort.objects.filter(institution__in=institutions)
        students_count = CohortStudent.objects.filter(cohort__in=cohorts).count()

        return Response({
            'institutions_count': institutions.count(),
            'cohorts_count': cohorts.count(),
            'students_count': students_count,
        }, status=status.HTTP_200_OK)
