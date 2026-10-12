from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from .views import (
    RegisterPendingView,
    RegisterView,
    UserLoginView,
    SwitchUserModeView,
    StudentDashboardView,
    UserProfileView,
    InstructorApplyView,
    AuthLoginAPIView,
    AuthRegisterAPIView,
    UserProfileAPIView,
    PublicInstructorProfileView,
)
from apps.portfolio.views import PortfolioDetailView

urlpatterns = [
    # Web Authentication & Workspace
    path('register/', RegisterView.as_view(), name='register'),
    path('register/pending/', RegisterPendingView.as_view(), name='register-pending'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='landing-page'), name='logout'),
    path('switch-mode/', SwitchUserModeView.as_view(), name='switch-user-mode'),
    path('mode/switch/', SwitchUserModeView.as_view(), name='switch-mode'),
    path('dashboard/', StudentDashboardView.as_view(), name='dashboard'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/<str:username>/', PortfolioDetailView.as_view(), name='profile-view'),
    path('apply-instructor/', InstructorApplyView.as_view(), name='apply-instructor'),
    path('instructor/apply/', InstructorApplyView.as_view(), name='instructor-apply'),
    path('instructors/<str:username>/', PublicInstructorProfileView.as_view(), name='public-instructor-profile'),

    # Password Reset & Recovery
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.html',
        subject_template_name='users/password_reset_subject.txt',
        success_url='/auth/password-reset/done/',
    ), name='password-reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'
    ), name='password-reset-done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url='/auth/password-reset/complete/',
    ), name='password-reset-confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'
    ), name='password-reset-complete'),

    # In-App Password Change
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='users/password_change.html',
        success_url='/auth/password-change/done/',
    ), name='password-change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='users/password_change_done.html'
    ), name='password-change-done'),

    # REST API endpoints (Mobile Apps & Single-Page Clients)
    path('api/login/', AuthLoginAPIView.as_view(), name='api-auth-login'),
    path('api/register/', AuthRegisterAPIView.as_view(), name='api-auth-register'),
    path('api/profile/', UserProfileAPIView.as_view(), name='api-auth-profile'),
]
