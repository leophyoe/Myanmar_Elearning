from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import StudentRegisterView, UserLoginView, StudentDashboardView, UserProfileView

urlpatterns = [
    path('register/', StudentRegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='landing-page'), name='logout'),
    path('dashboard/', StudentDashboardView.as_view(), name='dashboard'),
    path('profile/', UserProfileView.as_view(), name='profile'),
]

