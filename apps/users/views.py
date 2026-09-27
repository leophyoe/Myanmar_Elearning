from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import User, StudentProfile
from .forms import StudentRegistrationForm, UserLoginForm, StudentProfileUpdateForm


def role_dashboard_url(user):
    """Resolve the dashboard route that matches a user's role."""
    if user.is_admin:
        return 'admin-dashboard'
    if user.is_teacher:
        return 'teacher-dashboard'
    return 'dashboard'


class StudentRegisterView(CreateView):
    """Public self-registration is student-only; teachers and admins are provisioned by an administrator."""
    model = User
    form_class = StudentRegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, f"Welcome to Myanmar E-Learning, {self.object.username}! Your student environment is ready.")
        return response


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

        from apps.courses.models import Module, UserProgress
        from apps.labs.models import LabInstance, Lab
        from apps.ctf.models import SolvedChallenge
        from apps.scoring.models import UserBadge
        from apps.certificates.models import Certificate

        # 1. Academic Metrics
        total_modules = Module.objects.count() or 14
        completed_modules = UserProgress.objects.filter(user=user, is_completed=True).count()
        progress_percentage = int((completed_modules / total_modules) * 100) if total_modules > 0 else 0

        # 2. Lab Activity
        active_instances = LabInstance.objects.filter(user=user, status='running')
        total_labs_count = Lab.objects.filter(is_active=True).count()
        completed_labs_count = UserProgress.objects.filter(user=user, lab__isnull=False, is_completed=True).count()

        # 3. CTF & Badges
        solved_challenges = SolvedChallenge.objects.filter(user=user).select_related('challenge')
        badges = UserBadge.objects.filter(user=user).select_related('badge')
        certificates = Certificate.objects.filter(student=user)

        context.update({
            'profile': profile,
            'total_modules': total_modules,
            'completed_modules': completed_modules,
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
