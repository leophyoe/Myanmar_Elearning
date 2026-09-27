from django.urls import path
from .views import (
    TeacherDashboardView, AdminDashboardView,
    CourseReportView, StudentReportView, EarningsReportView,
)

urlpatterns = [
    path('instructor/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('system/', AdminDashboardView.as_view(), name='admin-dashboard'),
    # Legacy aliases so older bookmarks keep working
    path('teacher/', TeacherDashboardView.as_view(), name='instructor-dashboard'),
    path('admin/', AdminDashboardView.as_view(), name='system-telemetry'),
    # Phase 4 - operational reports
    path('reports/courses/', CourseReportView.as_view(), name='report-courses'),
    path('reports/students/', StudentReportView.as_view(), name='report-students'),
    path('reports/earnings/', EarningsReportView.as_view(), name='report-earnings'),
]
