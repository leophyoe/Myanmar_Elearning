from django.urls import path
from .views import TeacherDashboardView, AdminDashboardView

urlpatterns = [
    path('instructor/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('system/', AdminDashboardView.as_view(), name='admin-dashboard'),
    # Legacy aliases so older bookmarks keep working
    path('teacher/', TeacherDashboardView.as_view(), name='instructor-dashboard'),
    path('admin/', AdminDashboardView.as_view(), name='system-telemetry'),
]
