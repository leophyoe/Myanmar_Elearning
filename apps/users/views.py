from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, TemplateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import User, StudentProfile
from .forms import StudentRegistrationForm, UserLoginForm, StudentProfileUpdateForm

class StudentRegisterView(CreateView):
    model = User
    form_class = StudentRegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, f"Welcome to Future Tech Cyber Range, {self.object.username}! Your student environment is ready.")
        return response


class UserLoginView(LoginView):
    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.role == 'instructor':
            return reverse_lazy('instructor-dashboard')
        elif user.role in ['lab_admin', 'super_admin']:
            return reverse_lazy('system-telemetry')
        return reverse_lazy('dashboard')


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/student_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        from apps.courses.models import Course, Module, UserProgress
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        context['form'] = StudentProfileUpdateForm(instance=profile)
        return context

