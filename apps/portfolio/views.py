from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, View

from apps.common.services import absolute_uri, qr_response
from apps.certificates.models import Certificate
from .forms import ExternalCertificateForm, PortfolioLinkForm, SkillForm
from .models import ExternalCertificate, PortfolioLink, Skill

User = get_user_model()

RESOURCES = {
    'skill': (SkillForm, Skill),
    'link': (PortfolioLinkForm, PortfolioLink),
    'cert': (ExternalCertificateForm, ExternalCertificate),
}


def own_object(resource, pk, owner):
    form, model = RESOURCES[resource]
    if not pk:
        return None
    return get_object_or_404(model, pk=pk, owner=owner)


# ----------------------------------------------------------------------
# Public portfolio
# ----------------------------------------------------------------------
class PortfolioDetailView(DetailView):
    """Public profile: skills, links and credentials for one account."""
    template_name = 'portfolio/detail.html'
    context_object_name = 'portfolio_user'

    def get_object(self, queryset=None):
        return get_object_or_404(
            User, username=self.kwargs['username'], is_active=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        viewer = self.request.user
        is_owner = bool(
            viewer.is_authenticated and (viewer.pk == target.pk or viewer.is_admin)
        )

        platform_certs = Certificate.objects.filter(
            student=target, is_revoked=False
        ).select_related('course')

        external_qs = ExternalCertificate.objects.filter(owner=target)
        if not is_owner:
            # Pending / rejected submissions stay private until an admin checks them.
            external_qs = external_qs.filter(is_verified=True)

        explicit = list(target.portfolio_links.all())
        links = [
            {'label': link.display_label, 'url': link.url, 'kind': link.kind}
            for link in explicit
        ]
        # The bio form's GitHub / LinkedIn fields feed the same list.
        profile = getattr(target, 'student_profile', None)
        if profile:
            legacy = {
                PortfolioLink.Kind.GITHUB: (profile.github_url, 'GitHub'),
                PortfolioLink.Kind.LINKEDIN: (profile.linkedin_url, 'LinkedIn'),
            }
            for kind, (url, label) in legacy.items():
                if url and not any(link.kind == kind for link in explicit):
                    links.append({'label': label, 'url': url, 'kind': kind})

        context.update({
            'is_owner': is_owner,
            'platform_certificates': platform_certs,
            'external_certificates': external_qs,
            'skills': list(target.skills.all()),
            'links': links,
            'profile': profile,
            'portfolio_url': absolute_uri(
                self.request,
                reverse('portfolio-detail', kwargs={'username': target.username}),
            ),
            'qr_url': absolute_uri(
                self.request,
                reverse('portfolio-user-qr', kwargs={'username': target.username}),
            ),
            'nfc_url': absolute_uri(
                self.request,
                reverse('portfolio-user-nfc', kwargs={'username': target.username}),
            ),
        })
        return context


# ----------------------------------------------------------------------
# Owner editor
# ----------------------------------------------------------------------
class PortfolioEditView(LoginRequiredMixin, View):
    """One page that creates, edits and deletes skills, links and certificates."""
    template_name = 'portfolio/edit.html'

    def _context(self, form=None, resource='', pk=''):
        user = self.request.user
        return {
            'form': form,
            'resource': resource,
            'pk': pk,
            'resource_choices': [
                ('skill', 'Skill', SkillForm),
                ('link', 'Link', PortfolioLinkForm),
                ('cert', 'External certificate', ExternalCertificateForm),
            ],
            'skills': list(user.skills.all()),
            'links': list(user.portfolio_links.all()),
            'external_certificates': list(user.external_certificates.all()),
        }

    def get(self, request, *args, **kwargs):
        resource = request.GET.get('resource', '')
        pk = request.GET.get('pk', '')
        form = None
        if resource in RESOURCES:
            instance = own_object(resource, pk, request.user)
            form = RESOURCES[resource][0](instance=instance)
        return render(request, self.template_name, self._context(form, resource, pk))

    def post(self, request, *args, **kwargs):
        resource = request.POST.get('resource', '')
        if resource not in RESOURCES:
            messages.error(request, 'Unknown section — nothing was changed.')
            return redirect('portfolio-edit')

        form_class, model = RESOURCES[resource]
        pk = request.POST.get('pk', '')
        instance = own_object(resource, pk, request.user)
        action = request.POST.get('action', 'save')

        if action == 'delete':
            if instance is None:
                messages.info(request, 'That item is already gone.')
            else:
                label = getattr(instance, 'name', None) or getattr(
                    instance, 'title', None
                ) or str(instance)
                instance.delete()
                messages.success(request, f'“{label}” removed from your portfolio.')
            return redirect('portfolio-edit')

        form = form_class(request.POST, request.FILES, instance=instance)
        if not form.is_valid():
            messages.error(request, 'Please fix the highlighted fields.')
            return render(
                request, self.template_name,
                self._context(form, resource, pk),
            )

        obj = form.save(commit=False)
        obj.owner = request.user
        if resource == 'cert':
            # Any save — first submission or an edit — goes back into the queue
            # so an admin never validates a credential the owner has since changed.
            obj.is_verified = False
            obj.verified_by = None
            obj.verified_at = None
            obj.rejection_reason = ''
        try:
            obj.save()
        except IntegrityError:
            messages.error(request, 'You already have an item with those details.')
            return redirect('portfolio-edit')

        verb = 'Updated' if instance else 'Added'
        messages.success(
            request,
            f'{verb} '
            f'{getattr(obj, "name", None) or getattr(obj, "title", None) or obj}.'
        )
        return redirect('portfolio-edit')


# ----------------------------------------------------------------------
# QR + NFC payloads
# ----------------------------------------------------------------------
class PortfolioQRView(View):
    """PNG QR code encoding the public portfolio URL (for printing / NFC tags)."""

    def get(self, request, username=None):
        if username is None:
            if not request.user.is_authenticated:
                return redirect('login')
            target = request.user
        else:
            target = get_object_or_404(User, username=username, is_active=True)
        url = absolute_uri(
            request,
            reverse('portfolio-detail', kwargs={'username': target.username}),
        )
        return qr_response(url, filename=f'portfolio-{target.username}.png')


class PortfolioNFCView(View):
    """
    Plain-text payload to write onto an NFC tag.

    Any tag writer that accepts a URI/URL record can paste this verbatim; scanning
    the tag then opens the portfolio.
    """

    def get(self, request, username=None):
        if username is None:
            if not request.user.is_authenticated:
                return redirect('login')
            target = request.user
        else:
            target = get_object_or_404(User, username=username, is_active=True)
        url = absolute_uri(
            request,
            reverse('portfolio-detail', kwargs={'username': target.username}),
        )
        response = HttpResponse(url, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = (
            f'inline; filename="{target.username}-portfolio-nfc.txt"'
        )
        return response
