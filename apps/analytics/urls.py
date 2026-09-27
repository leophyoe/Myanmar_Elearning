from django.urls import path
from .views import InstructorDashboardView, SystemTelemetryView

urlpatterns = [
    path('instructor/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('system/', SystemTelemetryView.as_view(), name='system-telemetry'),
]

