from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
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

