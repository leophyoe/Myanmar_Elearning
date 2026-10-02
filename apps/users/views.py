from django.shortcuts import redirect
from django.views import View
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, TemplateView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import User, UserRole, StudentProfile, TeacherProfile, AdminProfile, InstructorApplication
from .forms import RegistrationForm, UserLoginForm, StudentProfileUpdateForm, UnifiedProfileForm, InstructorApplicationForm
from .services import switch_user_mode
from .serializers import UserProfileSerializer, UserRegistrationSerializer, UserLoginSerializer


def role_dashboard_url(user):
    """Resolve the dashboard route that matches a user's role and active mode."""
    if user.is_admin:
        return 'admin-dashboard'
    if user.is_teacher:
        if getattr(user, 'active_mode', None) == 'student':
            return 'dashboard'
        return 'teacher-dashboard'
    return 'dashboard'


class RegisterView(CreateView):
    """
    Public self-registration for students and teacher applicants.
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
                'Your account is active and you can sign in immediately. Instructor course authoring privileges will be verified by an administrator.',
            )
            return response
        login(self.request, self.object, backend='apps.users.backends.UniversalAuthBackend')
        messages.success(
            self.request,
            f"Welcome to Myanmar E-Learning, {self.object.username}! Your Account ID is {self.object.account_id}."
        )
        return response


class RegisterPendingView(TemplateView):
    """Landing page shown after a teacher application is submitted."""
    template_name = 'users/register_pending.html'


class UserLoginView(LoginView):
    """
    Universal Sign-in view for all roles: Student, Instructor, Partner, Admin.
    """
    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy(role_dashboard_url(self.request.user))


class SwitchUserModeView(LoginRequiredMixin, View):
    """
    Allows instructors to toggle between Student Mode and Instructor Mode
    within the same account without re-authenticating.
    """
    def post(self, request, *args, **kwargs):
        target_mode = request.POST.get('mode', 'student').lower().strip()
        try:
            switch_user_mode(request.user, target_mode)
            messages.success(request, f"Switched to {target_mode.capitalize()} Mode.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect(role_dashboard_url(request.user))


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboards/student_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Teachers and admins land on their own cockpit instead unless in student mode.
        if request.user.is_authenticated:
            if request.user.is_admin:
                return redirect('admin-dashboard')
            if request.user.is_teacher and getattr(request.user, 'active_mode', None) != 'student':
                return redirect('teacher-dashboard')
            if not request.user.is_student and getattr(request.user, 'active_mode', None) != 'student':
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
        from apps.courses.views import course_progress_pct
        from django.utils import timezone
        from apps.courses.models import LiveSession

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

        for enrollment in enrollments:
            enrollment.live_progress = (
                100 if enrollment.status == Enrollment.Status.COMPLETED
                else course_progress_pct(user, enrollment.course)
            )

        # 2. Lab Activity
        active_instances = LabInstance.objects.filter(user=user, status='running')
        total_labs_count = Lab.objects.filter(is_active=True).count()
        completed_labs_count = UserProgress.objects.filter(user=user, lab__isnull=False, is_completed=True).count()

        # 3. CTF & Badges & Certificates
        solved_challenges = SolvedChallenge.objects.filter(user=user).select_related('challenge')
        badges = UserBadge.objects.filter(user=user).select_related('badge')
        certificates = Certificate.objects.filter(student=user, is_revoked=False).select_related('course')

        # 4. Upcoming live classes
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
            'active_labs': LabInstance.objects.filter(user=user, status__in=['pending', 'running']).select_related('lab'),
            'available_labs': Lab.objects.filter(is_active=True).order_by('difficulty', 'title')[:6],
            'user_solves': solved_challenges,
            'earned_badges': badges,
            'earned_certificates': certificates,
            'total_points': getattr(user, 'profile', None).score if hasattr(user, 'profile') else getattr(user, 'student_profile', None).points if hasattr(user, 'student_profile') else 0,
        })
        return context


class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'users/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user
        context['profile'] = user.profile
        context['form'] = UnifiedProfileForm(user=user)
        context['is_student'] = user.is_student
        context['is_teacher'] = user.is_teacher
        context['user_role_display'] = user.get_role_display()
        return context

    def post(self, request, *args, **kwargs):
        form = UnifiedProfileForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully. / ပရိုဖိုင် အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ။")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)


class InstructorApplyView(LoginRequiredMixin, CreateView):
    """
    In-app instructor application submission for existing registered users.
    Workflow: User -> Application -> Admin Review -> Approved -> Instructor.
    """
    model = InstructorApplication
    form_class = InstructorApplicationForm
    template_name = 'users/apply_instructor.html'
    success_url = reverse_lazy('apply-instructor')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing_app'] = self.request.user.instructor_applications.filter(
            status=InstructorApplication.Status.PENDING
        ).first()
        return context

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.status = InstructorApplication.Status.PENDING
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Your application to become a verified instructor has been submitted successfully and is pending academic review."
        )
        return response


# -----------------------------------------------------------------------------
# REST API Endpoints (Android / iOS / Desktop / SPA Clients)
# -----------------------------------------------------------------------------

class AuthLoginAPIView(APIView):
    """
    POST /auth/api/login/
    Accepts Account ID, Email, or Username + Password.
    Returns authenticated user profile.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user, backend='apps.users.backends.UniversalAuthBackend')
            return Response({
                'message': 'Authentication successful.',
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuthRegisterAPIView(APIView):
    """
    POST /auth/api/register/
    Registers a new student account with permanent Account ID.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user, backend='apps.users.backends.UniversalAuthBackend')
            return Response({
                'message': 'Account created successfully.',
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPIView(APIView):
    """
    GET /auth/api/profile/
    Returns current authenticated user details and assigned roles.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
