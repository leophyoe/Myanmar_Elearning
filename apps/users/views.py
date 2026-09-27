from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from .models import User, UserRole, StudentProfile
from .forms import RegistrationForm, UserLoginForm, StudentProfileUpdateForm


def role_dashboard_url(user):
    """Resolve the dashboard route that matches a user's role."""
    if user.is_admin:
        return 'admin-dashboard'
    if user.is_teacher:
        return 'teacher-dashboard'
    return 'dashboard'


class RegisterView(CreateView):
    """
    Public self-registration.

    Students activate immediately. Teacher applicants are created inactive and
    sent to a holding page — an administrator activates them in the console.
    """
    model = User
    form_class = RegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('dashboard')

    def get_success_url(self):
        if self.object and self.object.role == UserRole.TEACHER:
            return reverse('register-pending')
        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.role == UserRole.TEACHER:
            messages.info(
                self.request,
                f'Teacher application received for “{self.object.username}”. '
                'An administrator must activate it before you can sign in.',
            )
            return response
        login(self.request, self.object)
        messages.success(self.request, f"Welcome to Myanmar E-Learning, {self.object.username}! Your student environment is ready.")
        return response


class RegisterPendingView(TemplateView):
    """Landing page shown after a teacher application is submitted."""
    template_name = 'users/register_pending.html'


class UserLoginView(LoginView):
    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy(role_dashboard_url(self.request.user))


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/student_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Teachers and admins land on their own cockpit instead.
        if request.user.is_authenticated and not request.user.is_student:
            return redirect(role_dashboard_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        from apps.courses.models import Lesson, UserProgress, Enrollment
        from apps.labs.models import LabInstance, Lab
        from apps.ctf.models import SolvedChallenge
        from apps.scoring.models import UserBadge
        from apps.certificates.models import Certificate

        # 1. Academic metrics — scoped to the courses the student actually took
        enrollments = list(
            Enrollment.objects.filter(student=user)
            .select_related('course', 'course__subject')
            .order_by('enrolled_at')
        )
        enrolled_ids = [e.course_id for e in enrollments]

        completed_rows = UserProgress.objects.filter(
            user=user, is_completed=True, lesson__isnull=False
        )
        if enrolled_ids:
            total_lessons = Lesson.objects.filter(
                module__course_id__in=enrolled_ids
            ).count()
            completed_lessons = completed_rows.filter(
                course_id__in=enrolled_ids
            ).count()
        else:
            total_lessons = Lesson.objects.count()
            completed_lessons = completed_rows.count()

        progress_percentage = (
            int((completed_lessons / total_lessons) * 100) if total_lessons else 0
        )

        done_lesson_ids = set(
            UserProgress.objects.filter(user=user, is_completed=True)
            .values_list('lesson_id', flat=True)
        )
        next_lesson = None
        if enrolled_ids:
            for lesson in Lesson.objects.filter(
                module__course_id__in=enrolled_ids
            ).select_related('module').order_by('module__course', 'module__order', 'order'):
                if lesson.id not in done_lesson_ids:
                    next_lesson = lesson
                    break

        from apps.courses.views import course_progress_pct
        for enrollment in enrollments:
            enrollment.live_progress = (
                100 if enrollment.status == Enrollment.Status.COMPLETED
                else course_progress_pct(user, enrollment.course)
            )

        # 2. Lab Activity
        active_instances = LabInstance.objects.filter(user=user, status='running')
        total_labs_count = Lab.objects.filter(is_active=True).count()
        completed_labs_count = UserProgress.objects.filter(user=user, lab__isnull=False, is_completed=True).count()

        # 3. CTF & Badges
        solved_challenges = SolvedChallenge.objects.filter(user=user).select_related('challenge')
        badges = UserBadge.objects.filter(user=user).select_related('badge')
        certificates = Certificate.objects.filter(student=user, is_revoked=False)

        # 4. Upcoming live classes (Zoom / Google Meet / Microsoft Teams)
        from django.utils import timezone
        from apps.courses.models import LiveSession
        upcoming_live_sessions = []
        if enrolled_ids:
            upcoming_live_sessions = list(
                LiveSession.objects.filter(
                    course_id__in=enrolled_ids,
                    is_published=True,
                    starts_at__gte=timezone.now(),
                ).select_related('course').order_by('starts_at')[:5]
            )

        context.update({
            'profile': profile,
            'enrollments': enrollments,
            'next_lesson': next_lesson,
            'upcoming_live_sessions': upcoming_live_sessions,
            'total_modules': total_lessons,
            'completed_modules': completed_lessons,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'active_instances': active_instances,
            'total_labs_count': total_labs_count,
            'completed_labs_count': completed_labs_count,
            'solved_challenges': solved_challenges,
            'badges': badges,
            'certificates': certificates,
        })
        return context


class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'users/profile.html'

    def _role_profile(self, user):
        from .models import TeacherProfile, AdminProfile
        if user.is_teacher:
            return TeacherProfile.objects.get_or_create(user=user)[0]
        if user.is_admin:
            return AdminProfile.objects.get_or_create(user=user)[0]
        return StudentProfile.objects.get_or_create(user=user)[0]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['profile'] = self._role_profile(user)
        context['form'] = (
            StudentProfileUpdateForm(instance=user.student_profile)
            if user.is_student else None
        )
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_student:
            messages.info(request, "This account's profile is managed by an administrator.")
            return redirect('profile')

        profile, _ = StudentProfile.objects.get_or_create(user=request.user)
        form = StudentProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
        else:
            messages.error(request, "Please correct the errors below.")
        return redirect('profile')
