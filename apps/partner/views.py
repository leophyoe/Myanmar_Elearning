import csv
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DetailView, ListView, TemplateView, View,
)
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course, Enrollment
from apps.ctf.models import SolvedChallenge
from apps.users.models import User, UserRole

from .models import (
    CohortStudent, Institution, InstitutionCohort, PartnerApplication,
    PartnerMembership, PartnerStudent,
)
from .serializers import InstitutionCohortSerializer, InstitutionSerializer


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
    Detailed cohort view showing roster of enrolled students, progress matrix, and gradebook.
    """
    model = InstitutionCohort
    template_name = 'partner/cohort_detail.html'
    context_object_name = 'cohort'
    pk_url_kwarg = 'cohort_id'

    def dispatch(self, request, *args, **kwargs):
        cohort = self.get_object()
        institutions = get_user_partner_institutions(request.user)
        if not institutions.filter(id=cohort.institution_id).exists() and not request.user.is_admin:
            raise PermissionDenied("You do not have access to view this cohort's roster.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cohort = self.object
        cohort_students = list(
            cohort.students.select_related('student').order_by('student_id_number', 'student__username')
        )

        enrollments_by_student = {}
        if cohort.course:
            enrollments = Enrollment.objects.filter(
                course=cohort.course,
                student__in=[cs.student for cs in cohort_students]
            )
            enrollments_by_student = {e.student_id: e for e in enrollments}

        student_users = [cs.student for cs in cohort_students]
        solves_qs = SolvedChallenge.objects.filter(user__in=student_users).values('user_id').annotate(total=Count('id'))
        solves_by_student = {s['user_id']: s['total'] for s in solves_qs}

        progress_list = []
        completed_count = 0

        for cs in cohort_students:
            enr = enrollments_by_student.get(cs.student_id)
            if enr:
                cs.progress_pct = enr.progress_pct
                cs.enrollment_status = enr.get_status_display()
                if enr.status == 'completed' or enr.progress_pct == 100:
                    completed_count += 1
            else:
                cs.progress_pct = 0
                cs.enrollment_status = 'Not Enrolled'
            progress_list.append(cs.progress_pct)
            cs.ctf_solves_count = solves_by_student.get(cs.student_id, 0)

        total_count = len(cohort_students)
        avg_progress = round(sum(progress_list) / total_count, 1) if total_count else 0.0

        context['students'] = cohort_students
        context['total_students_count'] = total_count
        context['avg_progress'] = avg_progress
        context['completed_count'] = completed_count
        return context


class PartnerCohortExportCSVView(LoginRequiredMixin, View):
    """
    Exports institutional cohort student roster and academic progress matrix to CSV.
    """
    def get(self, request, cohort_id):
        cohort = get_object_or_404(InstitutionCohort.objects.select_related('institution', 'course'), id=cohort_id)
        institutions = get_user_partner_institutions(request.user)
        if not institutions.filter(id=cohort.institution_id).exists() and not request.user.is_admin:
            raise PermissionDenied("You do not have permission to export this cohort's records.")

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        date_str = timezone.localdate().strftime('%Y%m%d')
        response['Content-Disposition'] = f'attachment; filename="cohort_{cohort.code}_roster_{date_str}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Student Account ID',
            'Full Name',
            'Username',
            'Email',
            'Institutional ID',
            'Course',
            'Progress (%)',
            'Status',
            'CTF Challenges Solved',
            'Joined Date',
        ])

        cohort_students = list(cohort.students.select_related('student').order_by('student_id_number', 'student__username'))
        enrollments_by_student = {}
        if cohort.course:
            enrollments = Enrollment.objects.filter(
                course=cohort.course,
                student__in=[cs.student for cs in cohort_students]
            )
            enrollments_by_student = {e.student_id: e for e in enrollments}

        student_users = [cs.student for cs in cohort_students]
        solves_qs = SolvedChallenge.objects.filter(user__in=student_users).values('user_id').annotate(total=Count('id'))
        solves_by_student = {s['user_id']: s['total'] for s in solves_qs}

        for cs in cohort_students:
            enr = enrollments_by_student.get(cs.student_id)
            progress = enr.progress_pct if enr else 0
            status_text = enr.get_status_display() if enr else 'Not Enrolled'
            ctf_count = solves_by_student.get(cs.student_id, 0)
            course_title = cohort.course.title if cohort.course else 'N/A'

            writer.writerow([
                cs.student.account_id or 'N/A',
                cs.student.get_full_name() or cs.student.username,
                cs.student.username,
                cs.student.email,
                cs.student_id_number or '-',
                course_title,
                progress,
                status_text,
                ctf_count,
                cs.joined_at.strftime('%Y-%m-%d %H:%M') if cs.joined_at else '-',
            ])

        return response


class PartnerCohortEnrollStudentView(LoginRequiredMixin, View):
    """
    Enrolls a student into an institutional cohort and automatically provisions
    course enrollment with source='partner'.
    """
    def post(self, request, cohort_id):
        cohort = get_object_or_404(InstitutionCohort.objects.select_related('institution', 'course'), id=cohort_id)
        institutions = get_user_partner_institutions(request.user)
        if not institutions.filter(id=cohort.institution_id).exists() and not request.user.is_admin:
            raise PermissionDenied("You do not manage this cohort.")

        identifier = request.POST.get('identifier', '').strip()
        student_id_num = request.POST.get('student_id_number', '').strip()

        if not identifier:
            messages.error(request, "Please enter a student Account ID, Email, or Username.")
            return redirect('partner-cohort-detail', cohort_id=cohort.id)

        target_student = User.objects.filter(
            Q(account_id__iexact=identifier) |
            Q(email__iexact=identifier) |
            Q(username__iexact=identifier)
        ).first()

        if not target_student:
            messages.error(request, f"No student found matching '{identifier}'.")
            return redirect('partner-cohort-detail', cohort_id=cohort.id)

        # Check seats limit
        current_seats = CohortStudent.objects.filter(cohort__institution=cohort.institution).count()
        if current_seats >= cohort.institution.max_student_seats:
            messages.warning(
                request,
                f"Institution seat limit reached ({cohort.institution.max_student_seats} seats). Contact administration to expand seat quota."
            )

        # Create or update CohortStudent
        cs, created = CohortStudent.objects.get_or_create(
            cohort=cohort,
            student=target_student,
            defaults={'student_id_number': student_id_num}
        )
        if not created and student_id_num and cs.student_id_number != student_id_num:
            cs.student_id_number = student_id_num
            cs.save(update_fields=['student_id_number'])

        # Ensure partner affiliation
        PartnerStudent.objects.get_or_create(
            institution=cohort.institution,
            student=target_student,
            defaults={
                'status': PartnerStudent.Status.ACTIVE,
                'class_group': cohort.code,
            }
        )

        # If cohort has an associated course, enroll the student
        if cohort.course:
            Enrollment.objects.get_or_create(
                course=cohort.course,
                student=target_student,
                defaults={
                    'source': Enrollment.Source.PARTNER,
                    'partner_institution': cohort.institution,
                    'status': Enrollment.Status.ACTIVE,
                }
            )

        messages.success(request, f"Student {target_student.get_full_name() or target_student.username} successfully enrolled in cohort {cohort.name}.")
        return redirect('partner-cohort-detail', cohort_id=cohort.id)


class PartnerEnrollmentExportCSVView(LoginRequiredMixin, View):
    """
    Exports all institutional course enrollments to CSV.
    """
    def get(self, request):
        institutions = get_user_partner_institutions(request.user)
        if not institutions.exists() and not request.user.is_admin:
            raise PermissionDenied("You do not have access to partner enrollment records.")

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        date_str = timezone.localdate().strftime('%Y%m%d')
        response['Content-Disposition'] = f'attachment; filename="partner_enrollments_{date_str}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Institution',
            'Course',
            'Student Account ID',
            'Full Name',
            'Username',
            'Email',
            'Channel / Source',
            'Progress (%)',
            'Status',
            'Enrolled Date',
            'Completed Date',
        ])

        enrollments = Enrollment.objects.filter(
            Q(course__partner_institution__in=institutions) |
            Q(partner_institution__in=institutions)
        ).select_related('course', 'student', 'partner_institution', 'course__partner_institution').order_by('-enrolled_at')

        for enr in enrollments:
            inst = enr.partner_institution or enr.course.partner_institution
            inst_name = inst.name if inst else 'N/A'
            writer.writerow([
                inst_name,
                enr.course.title,
                enr.student.account_id or 'N/A',
                enr.student.get_full_name() or enr.student.username,
                enr.student.username,
                enr.student.email,
                enr.get_source_display(),
                enr.progress_pct,
                enr.get_status_display(),
                enr.enrolled_at.strftime('%Y-%m-%d %H:%M') if enr.enrolled_at else '-',
                enr.completed_at.strftime('%Y-%m-%d %H:%M') if enr.completed_at else '-',
            ])

        return response


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


# ----------------------------------------------------------------------
# Partner Management Portal Extended Views
# ----------------------------------------------------------------------
from apps.certificates.models import Certificate


class PartnerInstitutionSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'partner/institution_settings.html'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institutions = get_user_partner_institutions(self.request.user)
        if not institutions.exists() and not self.request.user.is_admin:
            raise PermissionDenied("You do not manage any partner institution.")
        selected_id = self.request.GET.get('institution_id')
        if selected_id:
            institution = get_object_or_404(institutions, id=selected_id)
        else:
            institution = institutions.first()
        context['institutions'] = institutions
        context['institution'] = institution
        return context

    def post(self, request, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        inst_id = request.POST.get('institution_id')
        if not inst_id:
            institution = institutions.first()
        else:
            institution = get_object_or_404(institutions, id=inst_id)
        if not institution and not request.user.is_admin:
            raise PermissionDenied("You do not manage this institution.")

        if 'name' in request.POST:
            institution.name = request.POST['name'].strip()
        if 'website' in request.POST:
            institution.website = request.POST['website'].strip()
        if 'notes' in request.POST:
            institution.notes = request.POST['notes'].strip()
        if 'email' in request.POST:
            institution.contact_email = request.POST['email'].strip()
        institution.save()
        messages.success(request, f"Institution {institution.name} profile updated successfully.")
        return redirect('partner-institution-settings')


class PartnerCohortListView(LoginRequiredMixin, ListView):
    model = InstitutionCohort
    template_name = 'partner/cohort_list.html'
    context_object_name = 'cohorts'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        institutions = get_user_partner_institutions(self.request.user)
        if self.request.user.is_admin:
            return InstitutionCohort.objects.all().select_related('institution', 'course')
        return InstitutionCohort.objects.filter(institution__in=institutions).select_related('institution', 'course')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['institutions'] = get_user_partner_institutions(self.request.user)
        return context


class PartnerCohortCreateView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        courses = Course.objects.all()
        return render(request, 'partner/cohort_form.html', {
            'institutions': institutions,
            'courses': courses,
        })

    def post(self, request, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        inst_id = request.POST.get('institution_id')
        if inst_id:
            institution = get_object_or_404(institutions, id=inst_id)
        else:
            institution = institutions.first()

        if not institution:
            raise PermissionDenied("No partner institution found.")

        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        course_id = request.POST.get('course_id')
        is_active = request.POST.get('is_active') in ['on', 'true', '1']

        cohort = InstitutionCohort.objects.create(
            institution=institution,
            name=name,
            code=code,
            course_id=course_id if course_id else None,
            is_active=is_active
        )
        messages.success(request, f"Cohort '{cohort.name}' created.")
        return redirect('partner-cohort-detail', cohort_id=cohort.id)


class PartnerCohortEditView(LoginRequiredMixin, View):
    def dispatch(self, request, cohort_id, *args, **kwargs):
        cohort = get_object_or_404(InstitutionCohort, id=cohort_id)
        institutions = get_user_partner_institutions(request.user)
        if cohort.institution not in institutions and not request.user.is_admin:
            raise PermissionDenied("You do not have access to edit this cohort.")
        return super().dispatch(request, cohort_id, *args, **kwargs)

    def get(self, request, cohort_id, *args, **kwargs):
        cohort = get_object_or_404(InstitutionCohort, id=cohort_id)
        courses = Course.objects.all()
        return render(request, 'partner/cohort_form.html', {
            'cohort': cohort,
            'courses': courses,
            'institutions': [cohort.institution],
        })

    def post(self, request, cohort_id, *args, **kwargs):
        cohort = get_object_or_404(InstitutionCohort, id=cohort_id)
        if 'name' in request.POST:
            cohort.name = request.POST['name'].strip()
        if 'code' in request.POST:
            cohort.code = request.POST['code'].strip()
        if 'course_id' in request.POST:
            c_id = request.POST['course_id']
            cohort.course_id = c_id if c_id else None
        if 'is_active' in request.POST:
            cohort.is_active = request.POST['is_active'] in ['on', 'true', '1']
        cohort.save()
        messages.success(request, f"Cohort '{cohort.name}' updated.")
        return redirect('partner-cohort-detail', cohort_id=cohort.id)


class PartnerLearnerListView(LoginRequiredMixin, ListView):
    model = PartnerStudent
    template_name = 'partner/learner_list.html'
    context_object_name = 'partner_students'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        institutions = get_user_partner_institutions(self.request.user)
        if self.request.user.is_admin:
            return PartnerStudent.objects.all().select_related('student', 'institution')
        return PartnerStudent.objects.filter(institution__in=institutions).select_related('student', 'institution')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['learners'] = qs
        context['institutions'] = get_user_partner_institutions(self.request.user)
        return context


class PartnerLearnerRemoveView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        ps = get_object_or_404(PartnerStudent, id=pk, institution__in=institutions)
        student_name = ps.student.get_full_name() or ps.student.username
        ps.delete()
        messages.success(request, f"Student {student_name} removed from institution.")
        return redirect('partner-learners')


class PartnerInstructorRemoveView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        institutions = get_user_partner_institutions(request.user)
        pm = get_object_or_404(PartnerMembership, id=pk, institution__in=institutions)
        user_name = pm.user.get_full_name() or pm.user.username
        pm.delete()
        messages.success(request, f"Faculty instructor {user_name} removed from institution.")
        return redirect('partner-instructors')


class PartnerCertificateListView(LoginRequiredMixin, ListView):
    model = Certificate
    template_name = 'partner/certificate_list.html'
    context_object_name = 'certificates'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        institutions = get_user_partner_institutions(self.request.user)
        if self.request.user.is_admin:
            return Certificate.objects.all().select_related('student', 'course')
        return Certificate.objects.filter(
            Q(course__partner_institution__in=institutions) |
            Q(student__partner_memberships__institution__in=institutions)
        ).select_related('student', 'course').distinct()


class PartnerReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'partner/reports.html'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'is_partner', False) and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institutions = get_user_partner_institutions(self.request.user)
        context['institutions'] = institutions
        if self.request.user.is_admin:
            cohorts = InstitutionCohort.objects.all().select_related('institution', 'course')
            students_qs = PartnerStudent.objects.all().select_related('student', 'institution')
            courses_qs = Course.objects.all()
        else:
            cohorts = InstitutionCohort.objects.filter(institution__in=institutions).select_related('institution', 'course')
            students_qs = PartnerStudent.objects.filter(institution__in=institutions).select_related('student', 'institution')
            courses_qs = Course.objects.filter(partner_institution__in=institutions)

        cohort_reports = []
        for cohort in cohorts:
            students = cohort.students.all()
            st_count = students.count()
            avg_prog = 0
            comp_count = 0
            if st_count and cohort.course:
                enrs = Enrollment.objects.filter(course=cohort.course, student__in=[s.student for s in students])
                if enrs.exists():
                    from django.db.models import Avg
                    avg_prog = round(enrs.aggregate(Avg('progress_pct'))['progress_pct__avg'] or 0)
                    comp_count = enrs.filter(status='completed').count()
            cohort_reports.append({
                'cohort': cohort,
                'students_count': st_count,
                'avg_progress': avg_prog,
                'completed_count': comp_count,
            })

        course_reports = []
        for c in courses_qs:
            enrs = Enrollment.objects.filter(course=c)
            e_count = enrs.count()
            c_comp = enrs.filter(status='completed').count()
            comp_rate = round((c_comp / e_count * 100) if e_count else 0)
            course_reports.append({
                'course': c,
                'enrollments_count': e_count,
                'completions_count': c_comp,
                'completion_rate': comp_rate,
            })

        context['cohorts'] = cohorts
        context['cohort_reports'] = cohort_reports
        context['course_reports'] = course_reports
        context['partner_students'] = students_qs
        return context


class PartnerReportsLearnersCSVView(LoginRequiredMixin, View):
    def get(self, request):
        institutions = get_user_partner_institutions(request.user)
        if not institutions.exists() and not request.user.is_admin:
            raise PermissionDenied("Partner access required.")

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="partner_learners_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student Username', 'Full Name', 'Email', 'Institution', 'Status'])

        if request.user.is_admin:
            qs = PartnerStudent.objects.all().select_related('student', 'institution')
        else:
            qs = PartnerStudent.objects.filter(institution__in=institutions).select_related('student', 'institution')

        for ps in qs:
            writer.writerow([
                ps.student.username,
                ps.student.get_full_name() or ps.student.username,
                ps.student.email,
                ps.institution.name,
                ps.get_status_display(),
            ])
        return response




