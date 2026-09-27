from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView, View, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import User, StudentProfile, InstructorProfile
from .forms import StudentRegistrationForm, EmailAuthenticationForm, StudentProfileForm

class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = StudentRegistrationForm
    success_url = reverse_lazy('student-dashboard')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Welcome to Future Tech Academy, {user.get_full_name()}! Your student account is now active.")
        return super().form_valid(form)


class LoginView(FormView):
    template_name = 'accounts/login.html'
    form_class = EmailAuthenticationForm

    def get_success_url(self):
        user = self.request.user
        if user.is_instructor:
            return reverse_lazy('instructor-dashboard')
        elif user.is_academy_admin:
            return reverse_lazy('academy-admin-dashboard')
        return reverse_lazy('student-dashboard')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(self.request, email=email, password=password)

        if user is not None:
            if user.is_active:
                login(self.request, user)
                messages.success(self.request, f"Authenticated successfully as {user.get_role_display()}.")
                return redirect(self.get_success_url())
            else:
                messages.error(self.request, "This account is inactive. Please contact administration.")
                return self.form_invalid(form)
        else:
            messages.error(self.request, "Invalid email or password.")
            return self.form_invalid(form)


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "You have been logged out securely.")
        return redirect('home')

    def get(self, request):
        return self.post(request)


class ProfileView(LoginRequiredMixin, View):
    template_name = 'accounts/profile.html'

    def get(self, request):
        user = request.user
        profile = getattr(user, 'student_profile', None)
        form = StudentProfileForm(instance=profile) if profile else None
        return render(request, self.template_name, {'profile': profile, 'form': form})

    def post(self, request):
        profile = getattr(request.user, 'student_profile', None)
        if not profile:
            messages.error(request, "Student profile not found.")
            return redirect('profile')
        form = StudentProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
        return render(request, self.template_name, {'profile': profile, 'form': form})


class SetLanguageView(View):
    """
    Toggles student preferred language between English ('en') and Myanmar ('my').
    Persists to User profile if authenticated, session, and cookie.
    """
    def post(self, request):
        lang = request.POST.get('language', request.GET.get('language', 'en'))
        if lang not in ['en', 'my']:
            lang = 'en'

        request.session['preferred_language'] = lang

        if request.user.is_authenticated:
            request.user.preferred_language = lang
            request.user.save(update_fields=['preferred_language'])

        redirect_url = request.POST.get('next', request.GET.get('next', request.META.get('HTTP_REFERER', '/')))
        response = redirect(redirect_url)
        response.set_cookie('preferred_language', lang, max_age=365*24*60*60)
        return response

    def get(self, request):
        return self.post(request)

