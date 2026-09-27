from django.conf import settings
from django.db.models import Count, Sum
from django.views.generic import TemplateView
from apps.common.permissions import RoleRequiredMixin
from apps.billing.models import Payment
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


# ----------------------------------------------------------------------
# Phase 4 - operational reports for teachers and administrators
# ----------------------------------------------------------------------
def _score_pct(aggregation):
    """Turn a Sum('score') / Sum('max_score') pair into a percentage."""
    total = aggregation.get('total') or 0
    possible = aggregation.get('possible') or 0
    if not possible:
        return None
    return round(total * 100 / possible)


class CourseReportView(RoleRequiredMixin, TemplateView):
    """Per-course enrolment, progress, grading and certificate report."""
    template_name = 'dashboards/report_courses.html'
    allowed_roles = ['teacher']

    def get_context_data(self, **kwargs):
        from django.db.models import Avg, Count, Sum, Q
        from apps.courses.models import Course, Lesson, Enrollment
        from apps.certificates.models import Certificate

        context = super().get_context_data(**kwargs)
        rows = []
        for course in Course.objects.all().select_related('subject'):
            summary = Enrollment.objects.filter(course=course).aggregate(
                enrolled=Count('id'),
                active=Count('id', filter=Q(status=Enrollment.Status.ACTIVE)),
                completed=Count('id', filter=Q(status=Enrollment.Status.COMPLETED)),
                avg_progress=Avg('progress_pct'),
            )
            score = AssignmentSubmission.objects.filter(
                score__isnull=False,
                assignment__module__course=course,
            ).aggregate(total=Sum('score'), possible=Sum('assignment__max_score'))

            rows.append({
                'course': course,
                'lessons': Lesson.objects.filter(module__course=course).count(),
                'enrolled': summary['enrolled'],
                'active': summary['active'],
                'completed': summary['completed'],
                'avg_progress': round(summary['avg_progress'] or 0),
                'avg_score': _score_pct(score),
                'certificates': Certificate.objects.filter(course=course, is_revoked=False).count(),
            })

        context['rows'] = rows
        context['totals'] = {
            'courses': len(rows),
            'enrolled': sum(r['enrolled'] for r in rows),
            'completed': sum(r['completed'] for r in rows),
            'certificates': sum(r['certificates'] for r in rows),
        }
        return context


class StudentReportView(RoleRequiredMixin, TemplateView):
    """Per-student progress, grading and credential report."""
    template_name = 'dashboards/report_students.html'
    allowed_roles = ['teacher']

    def get_context_data(self, **kwargs):
        from django.db.models import Avg, Count, Sum, Q
        from apps.courses.models import Enrollment
        from apps.certificates.models import Certificate

        context = super().get_context_data(**kwargs)

        grade_rows = (AssignmentSubmission.objects.filter(score__isnull=False)
                      .values('student_id')
                      .annotate(total=Sum('score'), possible=Sum('assignment__max_score')))
        grade_map = {row['student_id']: row for row in grade_rows}

        cert_map = dict(
            Certificate.objects.filter(is_revoked=False)
            .values_list('student_id')
            .annotate(n=Count('id'))
        )

        students = (
            User.objects.filter(role='student')
            .select_related('student_profile')
            .order_by('username')
        )

        rows = []
        for student in students:
            summary = Enrollment.objects.filter(student=student).aggregate(
                enrolled=Count('id'),
                completed=Count('id', filter=Q(status=Enrollment.Status.COMPLETED)),
                avg_progress=Avg('progress_pct'),
            )
            pending = AssignmentSubmission.objects.filter(
                student=student, score__isnull=True
            ).count()
            profile = getattr(student, 'student_profile', None)
            rows.append({
                'student': student,
                'profile': profile,
                'enrolled': summary['enrolled'],
                'completed': summary['completed'],
                'avg_progress': round(summary['avg_progress'] or 0),
                'points': profile.points if profile else 0,
                'avg_score': _score_pct(grade_map.get(student.pk, {})),
                'pending': pending,
                'certificates': cert_map.get(student.pk, 0),
            })

        context['rows'] = rows
        context['totals'] = {
            'students': len(rows),
            'enrolled': sum(r['enrolled'] for r in rows),
            'completed': sum(r['completed'] for r in rows),
            'pending': sum(r['pending'] for r in rows),
        }
        return context


class EarningsReportView(RoleRequiredMixin, TemplateView):
    """Revenue split report: platform share vs teacher share of approved payments."""
    template_name = 'dashboards/report_earnings.html'
    allowed_roles = ['teacher']

    def get_queryset(self):
        qs = Payment.objects.filter(status=Payment.Status.APPROVED)
        if not self.request.user.is_admin:
            qs = qs.filter(course__owner=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_admin = self.request.user.is_admin

        rows = list(
            self.get_queryset()
            .values('course_id', 'course__title', 'course__slug', 'course__owner__username')
            .annotate(
                sales=Count('id'),
                gross=Sum('amount'),
                fee=Sum('platform_fee'),
                earned=Sum('teacher_amount'),
            )
            .order_by('-earned')
        )
        context['rows'] = rows
        context['is_admin'] = is_admin
        context['totals'] = {
            'sales': sum(r['sales'] for r in rows),
            'gross': sum((r['gross'] or 0) for r in rows),
            'fee': sum((r['fee'] or 0) for r in rows),
            'earned': sum((r['earned'] or 0) for r in rows),
            'pending': (
                Payment.objects.filter(status=Payment.Status.PENDING)
                if is_admin else
                Payment.objects.filter(
                    status=Payment.Status.PENDING, course__owner=self.request.user
                )
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        context['commission_rate'] = round(
            getattr(settings, 'PAYMENT_PLATFORM_COMMISSION_RATE', 0.25) * 100
        )
        return context
