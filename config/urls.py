import os
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from apps.common.views import LandingPageView, HealthCheckView, SetLanguageView
from apps.certificates.views import CertificateVerificationView

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),

    # System Health Check
    path('api/health/', HealthCheckView.as_view(), name='api-health'),

    # Universal REST API Gateway (Android / iOS / Web)
    path('api/v1/', include('apps.api.urls')),

    # Public Canonical Verification
    path('verify/<str:code>/', CertificateVerificationView.as_view(), name='canonical-verify'),

    # Language Switcher
    path('set-language/', SetLanguageView.as_view(), name='set-language'),

    # Web Pages & Portals
    path('', LandingPageView.as_view(), name='landing-page'),
    path('auth/', include('apps.users.urls')),
    path('courses/', include('apps.courses.urls')),
    path('vpn/', include('apps.vpn.urls')),
    path('labs/vpn/', RedirectView.as_view(pattern_name='vpn-dashboard', permanent=False)),
    path('labs/', include('apps.labs.urls')),
    path('cyber/', include('apps.labs.manage_urls')),
    path('terminal/', include('apps.terminal.urls')),
    path('ctf/', include('apps.ctf.urls')),
    path('leaderboard/', include('apps.scoring.urls')),
    path('certificates/', include('apps.certificates.urls')),
    path('projects/', include('apps.projects.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('billing/', include(('apps.billing.urls', 'billing'), namespace='billing')),
    path('billing/', include('apps.billing.urls')),
    path('pricing/', RedirectView.as_view(pattern_name='billing:pricing', permanent=False), name='pricing-redirect'),
    path('partner/', include('apps.partner.urls')),
    path('console/', include('apps.console.urls')),
    path('portfolio/', include('apps.portfolio.urls')),
    path('hub/', RedirectView.as_view(pattern_name='blog:article-list', permanent=False), name='hub-redirect'),
    path('articles/', include('apps.blog.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
