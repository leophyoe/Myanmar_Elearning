from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, View

from apps.common.services import absolute_uri, qr_response
from apps.certificates.models import Certificate
from apps.courses.models import Enrollment
from .forms import (
    ExternalCertificateForm, PortfolioEntryForm, PortfolioLinkForm,
    PortfolioProjectForm, SkillForm,
)
from .models import (
    ExternalCertificate, PortfolioEntry, PortfolioLink, PortfolioProject, Skill,
)

User = get_user_model()

RESOURCES = {
    'skill': (SkillForm, Skill),
    'link': (PortfolioLinkForm, PortfolioLink),
    'cert': (ExternalCertificateForm, ExternalCertificate),
    'project': (PortfolioProjectForm, PortfolioProject),
    'entry': (PortfolioEntryForm, PortfolioEntry),
}

RESOURCE_ORDER = ['project', 'cert', 'skill', 'entry', 'link']
RESOURCE_LABELS = {
    'project': 'Work sample',
    'cert': 'Credential',
    'skill': 'Skill',
    'entry': 'Education / Experience',
    'link': 'Profile link',
}


def own_object(resource, pk, owner):
    form, model = RESOURCES[resource]
    if not pk:
        return None
    return get_object_or_404(model, pk=pk, owner=owner)


def _date_key(value, fallback='1970-01-01'):
    return value.isoformat() if value else fallback


# ----------------------------------------------------------------------
# Public portfolio directory & individual portfolio
# ----------------------------------------------------------------------
class PortfolioListView(ListView):
    """
    Public directory of student, instructor and associate portfolios.
    Allows searching by query, filtering by role, and filtering by skills.
    Publicly accessible to guests and authenticated users.
    """
    model = User
    template_name = 'portfolio/list.html'
    context_object_name = 'portfolio_users'
    paginate_by = 12

    def get_queryset(self):
        qs = User.objects.filter(is_active=True).select_related(
            'student_profile', 'teacher_profile'
        ).prefetch_related(
            'skills', 'portfolio_projects', 'certificates', 'external_certificates'
        )

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(account_id__icontains=q) |
                Q(student_profile__bio__icontains=q) |
                Q(student_profile__student_id__icontains=q) |
                Q(skills__name__icontains=q)
            ).distinct()

        role = self.request.GET.get('role', '').strip().lower()
        if role == 'student':
            qs = qs.filter(role='student')
        elif role in ('teacher', 'instructor'):
            qs = qs.filter(role__in=['teacher', 'instructor'])
        elif role == 'associate':
            qs = qs.filter(is_associate=True)

        skill = self.request.GET.get('skill', '').strip()
        if skill:
            qs = qs.filter(skills__name__iexact=skill).distinct()

        return qs.order_by('-is_associate', '-student_profile__points', 'username')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        role = self.request.GET.get('role', '').strip().lower()
        skill = self.request.GET.get('skill', '').strip()

        popular_skills = (
            Skill.objects.values('name')
            .annotate(user_count=Count('owner', distinct=True))
            .order_by('-user_count', 'name')[:15]
        )

        total_active = User.objects.filter(is_active=True).count()
        students_count = User.objects.filter(is_active=True, role='student').count()
        teachers_count = User.objects.filter(is_active=True, role__in=['teacher', 'instructor']).count()
        associates_count = User.objects.filter(is_active=True, is_associate=True).count()

        context.update({
            'q': q,
            'role': role,
            'skill': skill,
            'popular_skills': popular_skills,
            'total_active': total_active,
            'students_count': students_count,
            'teachers_count': teachers_count,
            'associates_count': associates_count,
        })
        return context


class PortfolioDetailView(DetailView):
    """
    Public CV-style portfolio, laid out like the academicpages template:
    a sticky profile sidebar on the left and CV sections on the right.
    """
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
        request = self.request
        is_owner = bool(
            viewer.is_authenticated and (viewer.pk == target.pk or viewer.is_admin)
        )

        # -- profile sidebar facts -------------------------------------
        profile = getattr(target, 'student_profile', None)
        teacher_profile = getattr(target, 'teacher_profile', None)

        explicit_links = list(target.portfolio_links.all())
        links = [
            {
                'label': link.display_label,
                'url': link.url,
                'kind': link.kind,
                'is_freelance': link.kind in PortfolioLink.FREELANCE_KINDS,
            }
            for link in explicit_links
        ]
        if profile:
            for kind, url, label in (
                (PortfolioLink.Kind.GITHUB, profile.github_url, 'GitHub'),
                (PortfolioLink.Kind.LINKEDIN, profile.linkedin_url, 'LinkedIn'),
            ):
                if url and not any(link['kind'] == kind for link in links):
                    links.append({
                        'label': label, 'url': url, 'kind': kind,
                        'is_freelance': False,
                    })
        links.sort(key=lambda link: (
            0 if link['kind'] == PortfolioLink.Kind.GITHUB else 1,
            link['label'].lower(),
        ))

        # -- credentials: one merged list, platform first by date -------
        platform_qs = Certificate.objects.filter(student=target)
        if not is_owner:
            platform_qs = platform_qs.filter(is_revoked=False)

        credentials = []
        for cert in platform_qs.select_related('course'):
            verify_path = reverse('certificate-verify', kwargs={'cert_id': cert.pk})
            credentials.append({
                'source_kind': 'platform',
                'source': 'Myanmar E-Learning',
                'title': cert.program_title or cert.course.title,
                'subtitle': f'{cert.grade} · {cert.certificate_code}',
                'issued': cert.issued_at,
                'sort_date': _date_key(cert.issued_at.date()),
                'url': verify_path,
                'qr_url': reverse('certificate-qr', kwargs={'cert_id': cert.pk}),
                'status': 'revoked' if cert.is_revoked else 'verified',
                'note': cert.revocation_reason if cert.is_revoked else '',
                'document': None,
            })

        external_qs = target.external_certificates.all()
        if not is_owner:
            external_qs = external_qs.filter(is_verified=True)
        for cert in external_qs:
            credentials.append({
                'source_kind': 'external',
                'source': cert.issuer,
                'title': cert.title,
                'subtitle': (
                    f'ID: {cert.credential_id}' if cert.credential_id else ''
                ),
                'issued': cert.issued_on,
                'sort_date': _date_key(cert.issued_on),
                'url': cert.credential_url,
                'qr_url': '',
                'status': cert.status,
                'note': cert.note,
                'document': cert.document.url if cert.document else '',
            })
        credentials.sort(key=lambda item: item['sort_date'], reverse=True)

        # -- learning ---------------------------------------------------
        enrollments = list(
            Enrollment.objects.filter(student=target)
            .exclude(status=Enrollment.Status.DROPPED)
            .select_related('course')
        )
        completed = [e for e in enrollments if e.status == Enrollment.Status.COMPLETED]

        authored_articles = []
        if hasattr(target, 'authored_articles'):
            articles_qs = target.authored_articles.all()
            if not is_owner:
                articles_qs = articles_qs.filter(is_published=True)
            authored_articles = list(articles_qs.select_related('category')[:6])

        stats = {
            'credentials': len(credentials),
            'projects': target.portfolio_projects.filter(is_published=True).count(),
            'skills': target.skills.count(),
            'courses': len(enrollments),
            'completed': len(completed),
            'articles': len(authored_articles),
            'points': profile.points if profile else 0,
            'rank': profile.rank if profile else None,
        }

        # -- empty-state checklist --------------------------------------
        missing = [
            (bool((profile and profile.bio) or teacher_profile), 'Add a short bio',
             reverse('profile')),
            (bool(target.skills.exists()), 'List your top skills',
             reverse('portfolio-edit') + '?resource=skill'),
            (bool(target.portfolio_projects.filter(is_published=True).exists()),
             'Show a work sample', reverse('portfolio-edit') + '?resource=project'),
            (bool(links), 'Add a GitHub, Upwork or LinkedIn link',
             reverse('portfolio-edit') + '?resource=link'),
            (bool(credentials), 'Upload an external credential',
             reverse('portfolio-edit') + '?resource=cert'),
        ]

        context.update({
            'is_owner': is_owner,
            'profile': profile,
            'teacher_profile': teacher_profile,
            'links': links,
            'freelance_links': [l for l in links if l['is_freelance']],
            'credentials': credentials,
            'platform_credentials': [c for c in credentials
                                     if c['source_kind'] == 'platform'],
            'external_credentials': [c for c in credentials
                                     if c['source_kind'] == 'external'],
            'projects': target.portfolio_projects.filter(is_published=True),
            'education': target.portfolio_entries.filter(
                kind=PortfolioEntry.Kind.EDUCATION
            ),
            'experience': target.portfolio_entries.filter(
                kind=PortfolioEntry.Kind.EXPERIENCE
            ),
            'skills': list(target.skills.all()),
            'enrollments': enrollments,
            'authored_articles': authored_articles,
            'stats': stats,
            'missing': [m for m in missing if not m[0]],
            'portfolio_url': absolute_uri(
                request,
                reverse('portfolio-detail', kwargs={'username': target.username}),
            ),
            'qr_url': absolute_uri(
                request,
                reverse('portfolio-user-qr', kwargs={'username': target.username}),
            ),
            'nfc_url': absolute_uri(
                request,
                reverse('portfolio-user-nfc', kwargs={'username': target.username}),
            ),
        })
        return context


# ----------------------------------------------------------------------
# Owner editor
# ----------------------------------------------------------------------
class PortfolioEditView(LoginRequiredMixin, View):
    """One page that creates, edits and deletes every portfolio section."""
    template_name = 'portfolio/edit.html'

    def _context(self, form=None, resource='', pk=''):
        user = self.request.user
        return {
            'form': form,
            'resource': resource,
            'pk': pk,
            'resource_choices': [
                (key, RESOURCE_LABELS[key], RESOURCES[key][0])
                for key in RESOURCE_ORDER
            ],
            'resource_label': RESOURCE_LABELS.get(resource, 'item'),
            'skills': list(user.skills.all()),
            'links': list(user.portfolio_links.all()),
            'external_certificates': list(user.external_certificates.all()),
            'projects': list(user.portfolio_projects.all()),
            'entries': list(user.portfolio_entries.all()),
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
                label = getattr(instance, 'title', None) or getattr(
                    instance, 'name', None
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
        label = (
            getattr(obj, 'title', None) or getattr(obj, 'name', None)
            or getattr(obj, 'institution', None) or str(obj)
        )
        messages.success(request, f'{verb} {label}.')
        return redirect('portfolio-edit')


# ----------------------------------------------------------------------
# QR + NFC payloads
# ----------------------------------------------------------------------
def _target_for(request, username):
    if username is None:
        if not request.user.is_authenticated:
            return None
        return request.user
    return get_object_or_404(User, username=username, is_active=True)


class PortfolioQRView(View):
    """PNG QR code encoding the public portfolio URL (for printing / NFC tags)."""

    def get(self, request, username=None):
        target = _target_for(request, username)
        if target is None:
            return redirect('login')
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
        target = _target_for(request, username)
        if target is None:
            return redirect('login')
        url = absolute_uri(
            request,
            reverse('portfolio-detail', kwargs={'username': target.username}),
        )
        response = HttpResponse(url, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = (
            f'inline; filename="{target.username}-portfolio-nfc.txt"'
        )
        return response
