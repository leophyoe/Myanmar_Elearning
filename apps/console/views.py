import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView, View

from django.core.paginator import Paginator
from apps.billing.models import Payment
from apps.courses.models import Course, Enrollment
from apps.common.permissions import RoleRequiredMixin
from apps.portfolio.models import ExternalCertificate
from apps.users.models import AdminProfile, StudentProfile, TeacherProfile, UserRole
from apps.analytics.models import ActivityLog, SystemLog, ActivityAction, SystemLogLevel
from apps.ctf.models import FlagSubmission
from .forms import AdminPasswordResetForm, AdminUserCreateForm, AdminUserUpdateForm

User = get_user_model()


class AdminRequiredMixin(RoleRequiredMixin):
    """Restricts a view to ADMIN accounts (administrators always pass)."""
    allowed_roles = ['admin']


def ensure_role_profile(user):
    """A role change must leave the user with the profile of their new role."""
    role = user.role
    if role == UserRole.STUDENT and not hasattr(user, 'student_profile'):
        student_id = f"MEL-2026-{random.randint(1000, 9999)}"
        while StudentProfile.objects.filter(student_id=student_id).exists():
            student_id = f"MEL-2026-{random.randint(1000, 9999)}"
        StudentProfile.objects.create(user=user, student_id=student_id)
    elif role == UserRole.TEACHER and not hasattr(user, 'teacher_profile'):
        TeacherProfile.objects.create(user=user)
    elif role == UserRole.ADMIN and not hasattr(user, 'admin_profile'):
        AdminProfile.objects.create(user=user)


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------
class ConsoleHomeView(AdminRequiredMixin, TemplateView):
    template_name = 'console/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        approved = Payment.objects.filter(status=Payment.Status.APPROVED)
        context.update({
            'students': User.objects.filter(role=UserRole.STUDENT).count(),
            'teachers': User.objects.filter(role=UserRole.TEACHER).count(),
            'admins': User.objects.filter(role=UserRole.ADMIN).count(),
            'deactivated': User.objects.filter(is_active=False).count(),
            'pending_teachers': User.objects.filter(
                role=UserRole.TEACHER, is_active=False
            ).count(),
            'courses': Course.objects.count(),
            'published_courses': Course.objects.filter(is_published=True).count(),
            'paid_courses': Course.objects.exclude(price=0).count(),
            'enrolments': Enrollment.objects.count(),
            'pending_payments': Payment.objects.filter(
                status=Payment.Status.PENDING
            ).count(),
            'gross': approved.aggregate(v=Sum('amount'))['v'] or 0,
            'platform_fee': approved.aggregate(v=Sum('platform_fee'))['v'] or 0,
            'teacher_share': approved.aggregate(v=Sum('teacher_amount'))['v'] or 0,
        })
        return context


# ----------------------------------------------------------------------
# User management
# ----------------------------------------------------------------------
class UserListView(AdminRequiredMixin, TemplateView):
    template_name = 'console/user_list.html'

    ROLE_FILTERS = set(UserRole.values) | {'all'}
    STATUS_FILTERS = {'all', 'active', 'inactive'}

    def get_params(self):
        query = (self.request.GET.get('q') or '').strip()
        role = self.request.GET.get('role', 'all')
        status = self.request.GET.get('status', 'all')
        if role not in self.ROLE_FILTERS:
            role = 'all'
        if status not in self.STATUS_FILTERS:
            status = 'all'
        return query, role, status

    def get_queryset(self):
        query, role, status = self.get_params()
        qs = User.objects.all()
        if query:
            qs = qs.filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        if role != 'all':
            qs = qs.filter(role=role)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query, role, status = self.get_params()
        page_number = self.request.GET.get('page', '1')
        from django.core.paginator import Paginator
        paginator = Paginator(self.get_queryset(), 25)
        try:
            page_number = max(int(page_number), 1)
        except (TypeError, ValueError):
            page_number = 1

        context.update({
            'q': query,
            'role': role,
            'status': status,
            'page_obj': paginator.get_page(page_number),
            'roles': UserRole.choices,
            'role_options': [
                (value, label, User.objects.filter(role=value).count())
                for value, label in UserRole.choices
            ],
            'total_users': User.objects.count(),
            'counts': {
                'all': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'inactive': User.objects.filter(is_active=False).count(),
            },
            'role_counts': {
                value: User.objects.filter(role=value).count()
                for value in UserRole.values
            },
        })
        return context


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = AdminUserCreateForm
    template_name = 'console/user_form.html'
    success_url = reverse_lazy('console-user-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Account “{self.object.username}” created as '
            f'{self.object.get_role_display()}.'
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'New account'
        return context


class UserDetailView(AdminRequiredMixin, DetailView):
    model = User
    template_name = 'console/user_detail.html'
    context_object_name = 'subject_user'
    pk_url_kwarg = 'user_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        context['enrollments'] = (
            Enrollment.objects.filter(student=target)
            .select_related('course')
            .order_by('-enrolled_at')
        )
        context['completed_count'] = sum(
            1 for e in context['enrollments'] if e.status == Enrollment.Status.COMPLETED
        )
        context['payments'] = Payment.objects.filter(student=target).select_related(
            'course'
        )[:20]
        context['payment_totals'] = Payment.objects.filter(
            student=target, status=Payment.Status.APPROVED
        ).aggregate(gross=Sum('amount'), fee=Sum('platform_fee'))
        try:
            from apps.certificates.models import Certificate
            context['certificates'] = Certificate.objects.filter(
                student=target, is_revoked=False
            ).select_related('course')
        except Exception:
            context['certificates'] = []
        return context


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = User
    form_class = AdminUserUpdateForm
    template_name = 'console/user_form.html'
    pk_url_kwarg = 'user_id'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('console-user-detail', kwargs={'user_id': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        ensure_role_profile(self.object)
        messages.success(self.request, f'Account “{self.object.username}” updated.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Edit account'
        context['subject_user'] = self.object
        return context


class UserPasswordResetView(AdminRequiredMixin, View):
    template_name = 'console/user_password_reset.html'

    def get_user(self):
        return get_object_or_404(User, pk=self.kwargs['user_id'])

    def get(self, request, *args, **kwargs):
        target = self.get_user()
        return render(request, self.template_name, {
            'subject_user': target,
            'form': AdminPasswordResetForm(target),
        })

    def post(self, request, *args, **kwargs):
        target = self.get_user()
        form = AdminPasswordResetForm(target, request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, target)
            messages.success(request, f'Password reset for “{target.username}”.')
            return redirect('console-user-detail', user_id=target.pk)
        messages.error(request, ' '.join(
            error for errors in form.errors.values() for error in errors
        ))
        return render(request, self.template_name, {
            'subject_user': target,
            'form': form,
        })


class UserToggleActiveView(AdminRequiredMixin, View):
    """POST-only activate / deactivate."""

    def post(self, request, *args, **kwargs):
        target = get_object_or_404(User, pk=self.kwargs['user_id'])
        if target.pk == request.user.pk:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('console-user-detail', user_id=target.pk)

        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])

        if target.is_active:
            messages.success(request, f'“{target.username}” reactivated.')
        else:
            messages.warning(
                request,
                f'“{target.username}” deactivated — they can no longer sign in. '
                f'Related data is kept.'
            )
        return redirect('console-user-detail', user_id=target.pk)


# ----------------------------------------------------------------------
# Courses & fees
# ----------------------------------------------------------------------
class AdminCourseListView(AdminRequiredMixin, TemplateView):
    template_name = 'console/course_list.html'

    def get_queryset(self):
        query = (self.request.GET.get('q') or '').strip()
        qs = Course.objects.select_related('owner', 'subject').annotate(
            enrolled=Count('enrollments', distinct=True),
            learners=Count(
                'enrollments', distinct=True,
                filter=Q(enrollments__status=Enrollment.Status.ACTIVE),
            ),
        )
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(slug__icontains=query))
        order = self.request.GET.get('order', 'title')
        order = order if order in ('title', '-price', 'price', '-enrolled') else 'title'
        return qs.order_by(order)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courses = list(self.get_queryset())
        revenue = {
            row['course_id']: row
            for row in Payment.objects.filter(status=Payment.Status.APPROVED)
            .values('course_id')
            .annotate(gross=Sum('amount'), fee=Sum('platform_fee'),
                      teacher=Sum('teacher_amount'), sales=Count('id'))
        }
        for course in courses:
            row = revenue.get(course.id, {})
            course.gross = row.get('gross') or 0
            course.fee = row.get('fee') or 0
            course.teacher_share = row.get('teacher') or 0
            course.sales = row.get('sales') or 0
        context.update({
            'courses': courses,
            'q': (self.request.GET.get('q') or '').strip(),
            'order': self.request.GET.get('order', 'title'),
            'free_count': sum(1 for c in courses if c.is_free),
            'paid_count': sum(1 for c in courses if not c.is_free),
        })
        return context


class FeeOverviewView(AdminRequiredMixin, TemplateView):
    template_name = 'console/fee_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        approved = Payment.objects.filter(status=Payment.Status.APPROVED)
        totals = approved.aggregate(
            sales=Count('id'),
            gross=Sum('amount'),
            fee=Sum('platform_fee'),
            teacher=Sum('teacher_amount'),
        )
        context.update({
            'commission_rate': round(
                getattr(settings, 'PAYMENT_PLATFORM_COMMISSION_RATE', 0.25) * 100
            ),
            'currency': getattr(settings, 'PLATFORM_CURRENCY', 'MMK'),
            'teacher_share_pct': 100 - round(
                getattr(settings, 'PAYMENT_PLATFORM_COMMISSION_RATE', 0.25) * 100
            ),
            'totals': totals,
            'counts': {
                status: Payment.objects.filter(status=status).count()
                for status in Payment.Status.values
            },
            'status_options': [
                (value, label, Payment.objects.filter(status=value).count())
                for value, label in Payment.Status.choices
            ],
            'pending': Payment.objects.filter(status=Payment.Status.PENDING)
            .select_related('student', 'course')
            .order_by('created_at')[:15],
            'recent': approved.select_related('student', 'course').order_by(
                '-reviewed_at'
            )[:15],
        })
        return context


class PaymentRefundView(AdminRequiredMixin, View):
    """POST-only: mark an approved payment as refunded."""

    def post(self, request, *args, **kwargs):
        payment = get_object_or_404(Payment, pk=self.kwargs['payment_id'])
        if payment.status != Payment.Status.APPROVED:
            messages.info(request, 'Only approved payments can be refunded.')
        else:
            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=['status'])
            messages.warning(
                request,
                f'Refunded {payment.amount} {payment.currency} from '
                f'{payment.student.username}. The enrolment is unchanged — '
                f'drop it from the course page if access must end.'
            )
        return redirect('console-fee-overview')



# ----------------------------------------------------------------------
# External credential review
# ----------------------------------------------------------------------
class CredentialReviewView(AdminRequiredMixin, TemplateView):
    """Queue of student-submitted external certificates awaiting a verdict."""
    template_name = 'console/credential_list.html'

    STATUSES = ('pending', 'verified', 'rejected', 'all')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get('status', 'pending')
        if status not in self.STATUSES:
            status = 'pending'

        credentials = ExternalCertificate.objects.select_related(
            'owner', 'verified_by'
        )
        if status == 'pending':
            credentials = credentials.filter(
                is_verified=False
            ).filter(Q(rejection_reason='') | Q(rejection_reason__isnull=True))
        elif status == 'verified':
            credentials = credentials.filter(is_verified=True)
        elif status == 'rejected':
            credentials = credentials.exclude(
                Q(rejection_reason='') | Q(rejection_reason__isnull=True)
            ).filter(is_verified=False)

        context['active'] = 'credentials'
        context['status'] = status
        context['status_options'] = [
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
            ('all', 'All'),
        ]
        context['credentials'] = credentials
        context['pending_count'] = ExternalCertificate.objects.filter(
            is_verified=False
        ).filter(Q(rejection_reason='') | Q(rejection_reason__isnull=True)).count()
        return context


class CredentialActionView(AdminRequiredMixin, View):
    """POST-only approve / reject so a credential can reach the public portfolio."""

    def post(self, request, *args, **kwargs):
        credential = get_object_or_404(ExternalCertificate, pk=self.kwargs['cert_id'])
        action = self.kwargs['action']

        if action == 'verify':
            credential.is_verified = True
            credential.rejection_reason = ''
            credential.verified_by = request.user
            credential.verified_at = timezone.now()
            credential.save()
            messages.success(request, f'“{credential.title}” verified and published.')
        elif action == 'reject':
            reason = (request.POST.get('reason') or '').strip()
            if not reason:
                messages.error(request, 'Add a reason before rejecting a credential.')
                return redirect('console-credential-list')
            credential.is_verified = False
            credential.rejection_reason = reason
            credential.verified_by = request.user
            credential.verified_at = timezone.now()
            credential.save()
            messages.warning(request, f'“{credential.title}” rejected.')
        else:
            messages.error(request, 'Unknown action — nothing was changed.')

        return redirect(
            reverse('console-credential-list') + f'?status={request.POST.get("status", "pending")}'
        )


class AdminLogListView(AdminRequiredMixin, TemplateView):
    """Multi-tab audit log viewer for administrators (Activity, System, CTF Flags)."""
    template_name = 'console/log_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab = self.request.GET.get('tab', 'activity')
        q = self.request.GET.get('q', '').strip()
        page_number = self.request.GET.get('page', 1)

        if tab == 'system':
            qs = SystemLog.objects.all().order_by('-created_at')
            level = self.request.GET.get('level', '')
            if level:
                qs = qs.filter(level=level)
            if q:
                qs = qs.filter(Q(component__icontains=q) | Q(message__icontains=q))
        elif tab == 'flags':
            qs = FlagSubmission.objects.select_related('user', 'challenge').all().order_by('-created_at')
            correct = self.request.GET.get('correct', '')
            if correct == '1' or correct == 'yes':
                qs = qs.filter(is_correct=True)
            elif correct == '0' or correct == 'no':
                qs = qs.filter(is_correct=False)
            if q:
                qs = qs.filter(
                    Q(user__username__icontains=q) |
                    Q(challenge__title__icontains=q) |
                    Q(submitted_flag_clean__icontains=q)
                )
        else:
            tab = 'activity'
            qs = ActivityLog.objects.select_related('user').all().order_by('-created_at')
            action = self.request.GET.get('action', '')
            if action:
                qs = qs.filter(action=action)
            if q:
                qs = qs.filter(
                    Q(user__username__icontains=q) |
                    Q(action__icontains=q) |
                    Q(path__icontains=q)
                )

        paginator = Paginator(qs, 50)
        page_obj = paginator.get_page(page_number)

        context.update({
            'active_tab': tab,
            'page_obj': page_obj,
            'logs': page_obj.object_list,
            'q': q,
            'action_filter': self.request.GET.get('action', ''),
            'level_filter': self.request.GET.get('level', ''),
            'correct_filter': self.request.GET.get('correct', ''),
            'activity_actions': ActivityAction.choices,
            'system_levels': SystemLogLevel.choices,
            'total_count': paginator.count,
        })
        return context

