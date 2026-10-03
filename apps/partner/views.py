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
            from django.db.models import Q
            institutions = Institution.objects.filter(
                Q(contact_person=user) | Q(memberships__user=user, memberships__status='active')
            ).distinct()

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


# ----------------------------------------------------------------------
# Phase 2 — Partner Course & Curriculum Ownership
# ----------------------------------------------------------------------
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.views.generic import CreateView, View
from apps.users.models import User, UserRole
from apps.courses.models import Course, Enrollment
from apps.courses.forms import CourseForm
from .models import PartnerMembership


def get_user_partner_institutions(user):
    """
    Returns QuerySet of Institution instances managed by the given user.
    """
    if getattr(user, 'is_admin', False):
        return Institution.objects.all()
    return Institution.objects.filter(
        Q(contact_person=user) |
        Q(memberships__user=user, memberships__status=PartnerMembership.Status.ACTIVE)
    ).distinct()


class PartnerCourseListView(LoginRequiredMixin, ListView):
    """
    Lists courses belonging specifically to the authenticated partner's institution.
    Object-level authorization prevents accessing another partner's courses.
    """
    model = Course
    template_name = 'partner/course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        institutions = get_user_partner_institutions(self.request.user)
        if not institutions.exists() and not self.request.user.is_admin:
            raise PermissionDenied("You do not have administrative partner permissions.")
        return Course.objects.filter(
            partner_institution__in=institutions
        ).select_related('partner_institution', 'subject', 'owner').prefetch_related('modules__lessons')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['institutions'] = get_user_partner_institutions(self.request.user)
        return context


class PartnerCourseCreateView(LoginRequiredMixin, CreateView):
    """
    Enables partner staff to create institutional curriculum in DRAFT status.
    """
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'

    def dispatch(self, request, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        if not institutions.exists() and not request.user.is_admin:
            raise PermissionDenied("Partner access required to create institutional courses.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        institutions = get_user_partner_institutions(self.request.user)
        from django import forms
        form.fields['partner_institution'] = forms.ModelChoiceField(
            queryset=institutions,
            required=True,
            initial=institutions.first(),
        )
        return form

    def form_valid(self, form):
        course = form.save(commit=False)
        institutions = get_user_partner_institutions(self.request.user)
        partner_inst = form.cleaned_data.get('partner_institution')
        if partner_inst not in institutions and not self.request.user.is_admin:
            raise PermissionDenied("You cannot create courses for an institution you do not manage.")

        course.owner = self.request.user
        course.partner_institution = partner_inst
        course.owner_type = Course.OwnerType.PARTNER
        course.status = Course.Status.DRAFT
        course.is_published = False
        course.is_official = False
        course.save()
        messages.success(self.request, f"Partner course “{course.title}” created in Draft status.")
        return redirect('course-edit', slug=course.slug)


class PartnerEnrollmentListView(LoginRequiredMixin, ListView):
    """
    Object-level authorized roster of student enrollments and progress for partner courses.
    """
    model = Enrollment
    template_name = 'partner/enrollment_list.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        institutions = get_user_partner_institutions(self.request.user)
        if not institutions.exists() and not self.request.user.is_admin:
            raise PermissionDenied("You do not have access to partner student records.")
        return Enrollment.objects.filter(
            Q(course__partner_institution__in=institutions) |
            Q(partner_institution__in=institutions)
        ).select_related('course', 'student', 'partner_institution').order_by('-enrolled_at')


class PartnerInstructorManageView(LoginRequiredMixin, View):
    """
    Allows partner administrators to view and add faculty instructors to their institution.
    """
    template_name = 'partner/instructor_manage.html'

    def get(self, request):
        institutions = get_user_partner_institutions(request.user)
        if not institutions.exists() and not request.user.is_admin:
            raise PermissionDenied("You do not have administrative partner permissions.")
        memberships = PartnerMembership.objects.filter(
            institution__in=institutions,
            role=PartnerMembership.Role.TEACHER
        ).select_related('institution', 'user')
        return render(request, self.template_name, {
            'institutions': institutions,
            'memberships': memberships,
        })

    def post(self, request):
        institutions = get_user_partner_institutions(request.user)
        inst_id = request.POST.get('institution_id')
        username = (request.POST.get('username') or '').strip()

        institution = get_object_or_404(Institution, id=inst_id)
        if institution not in institutions and not request.user.is_admin:
            raise PermissionDenied("You do not manage this institution.")

        target_user = get_object_or_404(User, username=username)

        # Create or activate membership as TEACHER
        membership, created = PartnerMembership.objects.update_or_create(
            institution=institution,
            user=target_user,
            defaults={
                'role': PartnerMembership.Role.TEACHER,
                'status': PartnerMembership.Status.ACTIVE,
            }
        )

        # Promote user to instructor
        if hasattr(target_user, 'add_role'):
            target_user.add_role('instructor')
        else:
            target_user.role = UserRole.TEACHER
            target_user.save(update_fields=['role'])

        messages.success(request, f"Instructor {target_user.username} successfully added to {institution.name}.")
        return redirect('partner-instructors')


class PartnerRevenueReportView(LoginRequiredMixin, TemplateView):
    """
    Displays financial performance, sales count, student enrollments,
    gross revenue, MEL share, partner share, refunds, and outstanding balance
    for institutional partners.
    Strict object-level permission check: partner can only view their own institutions' revenue.
    """
    template_name = 'partner/revenue_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institutions = get_user_partner_institutions(self.request.user)
        if not institutions.exists() and not self.request.user.is_admin:
            raise PermissionDenied("You do not have administrative partner permissions.")

        selected_id = self.request.GET.get('institution_id')
        if selected_id:
            institution = get_object_or_404(institutions, id=selected_id)
        else:
            institution = institutions.first()

        context['institutions'] = institutions
        context['selected_institution'] = institution

        if institution:
            from apps.billing.services import get_partner_revenue_summary
            context['summary'] = get_partner_revenue_summary(institution)
        else:
            context['summary'] = None

        return context


# ----------------------------------------------------------------------
# Partner Application & Student Invitation Views
# ----------------------------------------------------------------------
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from .models import PartnerApplication, PartnerStudent


class PartnerApplyView(LoginRequiredMixin, CreateView):
    """
    Formal application submitted by teachers or educational leaders to establish a Partner Organization.
    Workflow: Teacher -> PartnerApplication -> Admin Review -> Approved -> Partner Organization.
    """
    model = PartnerApplication
    fields = [
        'organization_name', 'institution_type', 'country', 'city',
        'address', 'website', 'contact_person_name', 'contact_email',
        'contact_phone', 'registration_number', 'description'
    ]
    template_name = 'partner/apply.html'
    success_url = reverse_lazy('partner-apply-success')

    def form_valid(self, form):
        form.instance.applicant = self.request.user
        form.instance.status = PartnerApplication.Status.PENDING
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Your partnership application for “{form.instance.organization_name}” has been submitted for review."
        )
        return response


class PartnerApplySuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'partner/apply_success.html'


class PartnerInviteStudentView(LoginRequiredMixin, View):
    """
    Enables partner institutions to invite existing MEL students by MEL Account ID, Email, or Username.
    Creates a PartnerStudent with status=PENDING until accepted by student.
    """
    def post(self, request, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        if not institutions.exists() and not request.user.is_admin:
            raise PermissionDenied("You do not have partner administrative privileges.")

        inst_id = request.POST.get('institution_id')
        if inst_id:
            institution = get_object_or_404(institutions, id=inst_id)
        else:
            institution = institutions.first()
            if not institution:
                messages.error(request, "No partner institution found.")
                return redirect('partner-portal')

        identifier = request.POST.get('identifier', '').strip()
        class_group = request.POST.get('class_group', '').strip()
        note = request.POST.get('invitation_note', '').strip()

        if not identifier:
            messages.error(request, "Please enter a MEL ID, Email, or Username.")
            return redirect('partner-enrollments')

        target_student = User.objects.filter(
            Q(account_id__iexact=identifier) |
            Q(email__iexact=identifier) |
            Q(username__iexact=identifier)
        ).first()

        if not target_student:
            messages.error(request, f"No student found with MEL ID or Email '{identifier}'.")
            return redirect('partner-enrollments')

        partner_student, created = PartnerStudent.objects.update_or_create(
            institution=institution,
            student=target_student,
            defaults={
                'status': PartnerStudent.Status.PENDING,
                'class_group': class_group,
                'invitation_note': note,
            }
        )

        from apps.users.models import Notification
        Notification.objects.create(
            user=target_student,
            title="Institutional Partner Invitation",
            message=f"{institution.name} wants to associate you with their organization.",
            link=reverse('dashboard')
        )

        messages.success(request, f"Partnership invitation sent to {target_student.get_full_name() or target_student.username} ({target_student.account_id}).")
        return redirect('partner-enrollments')


class PartnerInvitationAcceptView(LoginRequiredMixin, View):
    """
    Student accepts an institutional partnership invitation.
    """
    def post(self, request, pk, *args, **kwargs):
        invitation = get_object_or_404(
            PartnerStudent,
            id=pk,
            student=request.user,
            status=PartnerStudent.Status.PENDING
        )
        invitation.status = PartnerStudent.Status.ACTIVE
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])

        messages.success(request, f"You have accepted the affiliation with {invitation.institution.name}.")
        return redirect('dashboard')

    def get(self, request, pk, *args, **kwargs):
        return self.post(request, pk, *args, **kwargs)


class PartnerInvitationDeclineView(LoginRequiredMixin, View):
    """
    Student declines an institutional partnership invitation.
    """
    def post(self, request, pk, *args, **kwargs):
        invitation = get_object_or_404(
            PartnerStudent,
            id=pk,
            student=request.user,
            status=PartnerStudent.Status.PENDING
        )
        invitation.status = PartnerStudent.Status.DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at'])

        messages.info(request, f"You have declined the affiliation with {invitation.institution.name}.")
        return redirect('dashboard')

    def get(self, request, pk, *args, **kwargs):
        return self.post(request, pk, *args, **kwargs)



