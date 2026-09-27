import uuid

from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.common.services import qr_response
from .models import Certificate

class CertificateListView(LoginRequiredMixin, ListView):
    model = Certificate
    template_name = 'certificates/certificate_list.html'
    context_object_name = 'certificates'

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user, is_revoked=False)


class CertificateVerificationView(DetailView):
    """
    Publicly accessible certificate verification portal.
    Proves credential validity without leaking private contact information.
    """
    model = Certificate
    template_name = 'certificates/verify.html'
    context_object_name = 'certificate'
    pk_url_kwarg = 'cert_id'

    def get_object(self, queryset=None):
        return get_object_or_404(Certificate, id=self.kwargs['cert_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        certificate = context['certificate']
        context['revoked'] = certificate.is_revoked
        context['verify_url'] = self.request.build_absolute_uri(
            reverse('certificate-verify', kwargs={'cert_id': certificate.pk})
        )
        return context



class CertificateLookupView(View):
    """
    Paste a certificate ID (UUID) or serial (`MEL-CERT-2026-…`) and land on the
    matching public verification page. This is what a QR scan falls back to when
    the code is typed instead of scanned.
    """
    template_name = 'certificates/lookup.html'

    def get(self, request, *args, **kwargs):
        code = (request.GET.get('code') or '').strip()
        if not code:
            return render(request, self.template_name, {'code': '', 'not_found': False})

        certificate = None
        try:
            uuid.UUID(code)
        except ValueError:
            pass
        else:
            certificate = Certificate.objects.filter(pk=code).first()

        if certificate is None:
            certificate = Certificate.objects.filter(
                certificate_code__iexact=code
            ).first()

        if certificate is None:
            return render(
                request, self.template_name,
                {'code': code, 'not_found': True},
            )
        return redirect('certificate-verify', cert_id=certificate.pk)


class CertificateQRView(View):
    """PNG QR code for the public verification URL of one certificate."""

    def get(self, request, *args, **kwargs):
        certificate = get_object_or_404(Certificate, pk=self.kwargs['cert_id'])
        url = request.build_absolute_uri(
            reverse('certificate-verify', kwargs={'cert_id': certificate.pk})
        )
        return qr_response(url, filename=f'{certificate.certificate_code}.png')
