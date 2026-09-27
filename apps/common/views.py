from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.db import connection
import os

class LandingPageView(TemplateView):
    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Summary metrics for landing page showcase
        from apps.courses.models import Course, Module
        from apps.labs.models import Lab
        from apps.ctf.models import Challenge

        context['courses_count'] = Course.objects.filter(is_published=True).count()
        context['modules_count'] = Module.objects.count()
        context['labs_count'] = Lab.objects.filter(is_active=True).count()
        context['ctf_count'] = Challenge.objects.filter(is_active=True).count()
        return context


class HealthCheckView(View):
    """System health check endpoint verifying Database, Redis, and Docker daemon status."""

    def get(self, request, *args, **kwargs):
        health = {
            'status': 'healthy',
            'components': {
                'database': {'status': 'unknown'},
                'redis': {'status': 'unknown'},
                'docker': {'status': 'unknown'},
            }
        }

        # 1. Database Check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            health['components']['database']['status'] = 'connected'
        except Exception as e:
            health['components']['database']['status'] = f'error: {str(e)}'
            health['status'] = 'degraded'

        # 2. Redis Check
        try:
            import redis
            from django.conf import settings
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            r.ping()
            health['components']['redis']['status'] = 'connected'
        except Exception as e:
            health['components']['redis']['status'] = f'unavailable: {str(e)}'
            # In local dev SQLite mode, Redis being down is non-fatal

        # 3. Docker Daemon Check
        try:
            import docker
            client = docker.from_env(timeout=2)
            client.ping()
            health['components']['docker']['status'] = 'connected'
        except Exception as e:
            health['components']['docker']['status'] = f'daemon unreachable: {str(e)}'

        status_code = 200 if health['status'] == 'healthy' else 207
        return JsonResponse(health, status=status_code)

