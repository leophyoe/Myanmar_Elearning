import uuid

from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.common.services import qr_response
from .models import Certificate, AssociateCredential

class CertificateListView(LoginRequiredMixin, ListView):
    model = Certificate
    template_name = 'certificates/certificate_list.html'
    context_object_name = 'certificates'

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user, is_revoked=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['associate_credential'] = getattr(self.request.user, 'associate_credential', None)
        return context


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
        raw = self.kwargs.get('cert_id') or self.kwargs.get('code')
        try:
            val_uuid = uuid.UUID(str(raw))
            return get_object_or_404(Certificate, id=val_uuid)
        except ValueError:
            return get_object_or_404(Certificate, certificate_code__iexact=raw)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        certificate = context['certificate']
        context['revoked'] = certificate.is_revoked
        context['verify_url'] = self.request.build_absolute_uri(
            reverse('certificate-verify', kwargs={'cert_id': certificate.pk})
        )
        return context


class AssociateCredentialVerificationView(DetailView):
    """
    Publicly accessible Associate Credential verification portal.
    """
    model = AssociateCredential
    template_name = 'certificates/verify_associate.html'
    context_object_name = 'credential'
    pk_url_kwarg = 'cred_id'

    def get_object(self, queryset=None):
        return get_object_or_404(AssociateCredential, id=self.kwargs['cred_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credential = context['credential']
        context['revoked'] = credential.is_revoked
        context['verify_url'] = self.request.build_absolute_uri(
            reverse('associate-verify', kwargs={'cred_id': credential.pk})
        )
        return context


class CertificateLookupView(View):
    """
    Paste a certificate ID (UUID) or serial (`MEL-CERT-2026-…`, `MEL-ASSOC-2026-...`)
    and land on the matching public verification page.
    """
    template_name = 'certificates/lookup.html'

    def get(self, request, *args, **kwargs):
        code = (request.GET.get('code') or '').strip()
        if not code:
            return render(request, self.template_name, {'code': '', 'not_found': False})

        # Check Associate serial format first
        if code.upper().startswith('MEL-ASSOC-'):
            assoc = AssociateCredential.objects.filter(credential_code__iexact=code).first()
            if assoc:
                return redirect('associate-verify', cred_id=assoc.pk)

        # Check UUID
        try:
            parsed_uuid = uuid.UUID(code)
        except ValueError:
            pass
        else:
            cert = Certificate.objects.filter(pk=parsed_uuid).first()
            if cert:
                return redirect('certificate-verify', cert_id=cert.pk)
            assoc = AssociateCredential.objects.filter(pk=parsed_uuid).first()
            if assoc:
                return redirect('associate-verify', cred_id=assoc.pk)

        # Search by certificate serial code
        certificate = Certificate.objects.filter(certificate_code__iexact=code).first()
        if certificate:
            return redirect('certificate-verify', cert_id=certificate.pk)

        # Search by associate serial code
        assoc = AssociateCredential.objects.filter(credential_code__iexact=code).first()
        if assoc:
            return redirect('associate-verify', cred_id=assoc.pk)

        return render(
            request, self.template_name,
            {'code': code, 'not_found': True},
        )


class CertificateQRView(View):
    """PNG QR code for the public verification URL of one certificate."""

    def get(self, request, *args, **kwargs):
        certificate = get_object_or_404(Certificate, pk=self.kwargs['cert_id'])
        url = request.build_absolute_uri(
            reverse('certificate-verify', kwargs={'cert_id': certificate.pk})
        )
        return qr_response(url, filename=f'{certificate.certificate_code}.png')


class AssociateCredentialQRView(View):
    """PNG QR code for the public verification URL of one associate credential."""

    def get(self, request, *args, **kwargs):
        credential = get_object_or_404(AssociateCredential, pk=self.kwargs['cred_id'])
        url = request.build_absolute_uri(
            reverse('associate-verify', kwargs={'cred_id': credential.pk})
        )
        return qr_response(url, filename=f'{credential.credential_code}.png')
