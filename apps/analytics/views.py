from django.views.generic import TemplateView
from apps.common.permissions import RoleRequiredMixin
from apps.users.models import User, StudentProfile
from apps.labs.models import LabInstance
from apps.courses.models import UserProgress, AssignmentSubmission
from apps.ctf.models import Challenge, SolvedChallenge
from .models import SystemLog, ActivityLog


class TeacherDashboardView(RoleRequiredMixin, TemplateView):
    """Teacher Command Center - students, submissions and live class activity."""
    template_name = 'dashboards/instructor_dashboard.html'
    allowed_roles = ['teacher']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'total_students': StudentProfile.objects.count(),
            'active_students': User.objects.filter(role='student', is_active=True).count(),
            'active_labs': LabInstance.objects.filter(status='running').count(),
            'total_lab_completions': UserProgress.objects.filter(lab__isnull=False, is_completed=True).count(),
            'recent_submissions': AssignmentSubmission.objects.filter(score__isnull=True)[:10],
            'recent_activity': ActivityLog.objects.select_related('user')[:15],
            'total_challenges': Challenge.objects.count(),
            'total_solves': SolvedChallenge.objects.count(),
        })
        return context


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    """Administrator Command Center - platform health, users and lab infrastructure."""
    template_name = 'dashboards/admin_dashboard.html'
    allowed_roles = ['admin']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db import connection

        # Check DB status
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            db_status = "Connected (Healthy)"
        except Exception as e:
            db_status = f"Error: {e}"

        # Check Redis status
        try:
            import redis
            from django.conf import settings
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            r.ping()
            redis_status = "Connected (Online)"
        except Exception:
            redis_status = "Offline / Local Mode"

        # Check Docker Engine
        try:
            import docker
            client = docker.from_env(timeout=2)
            containers = client.containers.list()
            docker_status = f"Operational ({len(containers)} containers running)"
        except Exception:
            docker_status = "Simulation / Daemon Inactive"

        context.update({
            'db_status': db_status,
            'redis_status': redis_status,
            'docker_status': docker_status,
            'total_users': User.objects.count(),
            'total_teachers': User.objects.filter(role='teacher', is_active=True).count(),
            'total_students': User.objects.filter(role='student', is_active=True).count(),
            'active_instances': LabInstance.objects.filter(status='running'),
            'system_logs': SystemLog.objects.all()[:20],
            'recent_activities': ActivityLog.objects.select_related('user')[:20],
        })
        return context


# Legacy aliases (kept for imports that still use the old names)
InstructorDashboardView = TeacherDashboardView
SystemTelemetryView = AdminDashboardView
