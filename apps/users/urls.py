from django.urls import path
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
    path('apply-instructor/', InstructorApplyView.as_view(), name='apply-instructor'),
    path('instructor/apply/', InstructorApplyView.as_view(), name='instructor-apply'),
    path('instructors/<str:username>/', PublicInstructorProfileView.as_view(), name='public-instructor-profile'),

    # REST API endpoints (Mobile Apps & Single-Page Clients)
    path('api/login/', AuthLoginAPIView.as_view(), name='api-auth-login'),
    path('api/register/', AuthRegisterAPIView.as_view(), name='api-auth-register'),
    path('api/profile/', UserProfileAPIView.as_view(), name='api-auth-profile'),
]
