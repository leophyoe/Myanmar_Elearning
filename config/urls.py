import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.common.views import LandingPageView, HealthCheckView

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),

    # System Health Check
    path('api/health/', HealthCheckView.as_view(), name='api-health'),

    # Web Pages & Portals
    path('', LandingPageView.as_view(), name='landing-page'),
    path('auth/', include('apps.users.urls')),
    path('courses/', include('apps.courses.urls')),
    path('vpn/', include('apps.vpn.urls')),
    path('labs/vpn/', include('apps.vpn.urls')),
    path('labs/', include('apps.labs.urls')),
    path('cyber/', include('apps.labs.manage_urls')),
    path('terminal/', include('apps.terminal.urls')),
    path('ctf/', include('apps.ctf.urls')),
    path('leaderboard/', include('apps.scoring.urls')),
    path('certificates/', include('apps.certificates.urls')),
    path('projects/', include('apps.projects.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('billing/', include('apps.billing.urls')),
    path('console/', include('apps.console.urls')),
    path('portfolio/', include('apps.portfolio.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

