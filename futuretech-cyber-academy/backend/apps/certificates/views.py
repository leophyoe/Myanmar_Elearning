from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.core.audit import get_client_ip
from .models import Certificate, CertificateStatus, CertificateVerification


class CertificateListView(LoginRequiredMixin, ListView):
    model = Certificate
    template_name = 'certificates/certificate_list.html'
    context_object_name = 'certificates'

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user).select_related('course', 'template')


class CertificateDetailView(LoginRequiredMixin, DetailView):
    model = Certificate
    template_name = 'certificates/certificate_view.html'
    context_object_name = 'certificate'
    slug_field = 'certificate_number'
    slug_url_kwarg = 'certificate_number'

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor or user.is_academy_admin:
            return Certificate.objects.all().select_related('course', 'student', 'template')
        return Certificate.objects.filter(student=user).select_related('course', 'student', 'template')


class PublicCertificateVerificationView(View):
    """
    Public zero-trust verification gateway.
    Accessible without login. Returns verification badge while shielding student PII.
    """
    def get(self, request, certificate_number):
        cert = Certificate.objects.filter(
            certificate_number__iexact=certificate_number.strip()
        ).select_related('course', 'student', 'template').first()

        is_valid = False
        if cert and cert.status == CertificateStatus.ISSUED:
            is_valid = True
            # Log verification request for institutional audit
            CertificateVerification.objects.create(
                certificate=cert,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )

        return render(request, 'certificates/certificate_verify.html', {
            'certificate': cert,
            'certificate_number': certificate_number,
            'is_valid': is_valid,
        })

