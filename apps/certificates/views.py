import csv
import uuid

from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy

from apps.common.services import qr_response
from apps.common.permissions import RoleRequiredMixin
from apps.courses.models import Course
from .models import Certificate, CertificateTemplate, AssociateCredential
from .forms import CertificateTemplateForm


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
    Renders high-definition diploma (built-in theme or custom uploaded image)
    with 1-click print, high-res PNG download, and cryptographic verification status.
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
        cert_template = certificate.effective_template
        context['cert_template'] = cert_template
        font_map = {
            'cinzel': "'Cinzel', serif",
            'playfair': "'Playfair Display', serif",
            'inter': "'Inter', sans-serif",
            'great_vibes': "'Great Vibes', cursive",
        }
        if cert_template:
            context['cert_font_family'] = font_map.get(cert_template.font_choice, "'Cinzel', serif")
        else:
            context['cert_font_family'] = "'Cinzel', serif"

        # Additional student verified records on this platform
        if certificate.student:
            context['other_certificates'] = Certificate.objects.filter(
                student=certificate.student,
                is_revoked=False
            ).exclude(pk=certificate.pk).order_by('-issued_at')[:5]
            context['total_student_credentials'] = Certificate.objects.filter(
                student=certificate.student,
                is_revoked=False
            ).count()
        else:
            context['other_certificates'] = []
            context['total_student_credentials'] = 1

        context['sha256_hash'] = certificate.sha256_hash
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
        q = (request.GET.get('q') or '').strip()
        status_filter = request.GET.get('status', 'all')

        if code:
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

        # Retrieve registry records for the Certificate Record Table
        records_qs = Certificate.objects.select_related('student', 'course', 'exam', 'template').all()

        if q:
            records_qs = records_qs.filter(
                models.Q(certificate_code__icontains=q) |
                models.Q(student_name__icontains=q) |
                models.Q(program_title__icontains=q)
            )

        if status_filter == 'valid':
            records_qs = records_qs.filter(is_revoked=False)
        elif status_filter == 'revoked':
            records_qs = records_qs.filter(is_revoked=True)
        elif status_filter == 'distinction':
            records_qs = records_qs.filter(grade__icontains='Distinction')
        elif status_filter == 'exam':
            records_qs = records_qs.filter(
                models.Q(exam__isnull=False) |
                models.Q(certificate_type=Certificate.CertificateType.EXAM_VERIFIED)
            )

        records = records_qs.order_by('-issued_at')[:40]

        context = {
            'code': code,
            'not_found': bool(code),
            'records': records,
            'q': q,
            'status_filter': status_filter,
            'total_certificates': Certificate.objects.count(),
            'valid_certificates': Certificate.objects.filter(is_revoked=False).count(),
            'distinction_certificates': Certificate.objects.filter(grade__icontains='Distinction').count(),
        }

        return render(request, self.template_name, context)


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


# =============================================================================
# Certificate Studio: Templates Management (Instructors, Partners, Admins)
# =============================================================================

class CertificateTemplateListView(RoleRequiredMixin, ListView):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']
    model = CertificateTemplate
    template_name = 'certificates/template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_admin', False) or user.is_superuser:
            return CertificateTemplate.objects.all()
        return CertificateTemplate.objects.filter(
            models.Q(created_by=user) |
            models.Q(is_default=True) |
            models.Q(partner__contact_person=user)
        ).distinct()


class CertificateTemplateCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']
    model = CertificateTemplate
    form_class = CertificateTemplateForm
    template_name = 'certificates/template_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('certificate-template-list')


class CertificateTemplateUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']
    model = CertificateTemplate
    form_class = CertificateTemplateForm
    template_name = 'certificates/template_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('certificate-template-list')


class CertificateTemplateDeleteView(RoleRequiredMixin, DeleteView):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']
    model = CertificateTemplate
    template_name = 'certificates/template_confirm_delete.html'
    context_object_name = 'cert_template'
    success_url = reverse_lazy('certificate-template-list')


class CertificateTemplatePreviewView(RoleRequiredMixin, DetailView):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']
    model = CertificateTemplate
    template_name = 'certificates/template_preview.html'
    context_object_name = 'cert_template'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tpl = context['cert_template']
        font_map = {
            'cinzel': "'Cinzel', serif",
            'playfair': "'Playfair Display', serif",
            'inter': "'Inter', sans-serif",
            'great_vibes': "'Great Vibes', cursive",
        }
        context['cert_font_family'] = font_map.get(tpl.font_choice, "'Cinzel', serif")
        context['is_preview'] = True
        context['sample_student_name'] = "Mg Aung Kyaw Moe"
        context['sample_program_title'] = "Professional Diploma in Cyber Defense & Cloud Architecture"
        context['sample_serial'] = "MEL-CERT-2026-SAMPLE"
        context['sample_date'] = "October 12, 2026"
        context['sample_grade'] = "Distinction"
        return context


class CertificateTemplateDuplicateView(RoleRequiredMixin, View):
    allowed_roles = ['instructor', 'teacher', 'partner', 'admin']

    def post(self, request, pk, *args, **kwargs):
        return self._duplicate(request, pk)

    def get(self, request, pk, *args, **kwargs):
        return self._duplicate(request, pk)

    def _duplicate(self, request, pk):
        tpl = get_object_or_404(CertificateTemplate, pk=pk)
        new_tpl = CertificateTemplate.objects.create(
            title=f"{tpl.title} (Copy)",
            created_by=request.user,
            partner=tpl.partner,
            design_mode=tpl.design_mode,
            theme_style=tpl.theme_style,
            background_image=tpl.background_image,
            institution_name=tpl.institution_name,
            header_title=tpl.header_title,
            subtitle=tpl.subtitle,
            body_text=tpl.body_text,
            font_choice=tpl.font_choice,
            primary_color=tpl.primary_color,
            accent_color=tpl.accent_color,
            name_pos_top=tpl.name_pos_top,
            name_color=tpl.name_color,
            name_font_size=tpl.name_font_size,
            title_pos_top=tpl.title_pos_top,
            title_color=tpl.title_color,
            title_font_size=tpl.title_font_size,
            date_pos_top=tpl.date_pos_top,
            date_pos_left=tpl.date_pos_left,
            qr_pos_top=tpl.qr_pos_top,
            qr_pos_left=tpl.qr_pos_left,
            serial_pos_top=tpl.serial_pos_top,
            serial_pos_left=tpl.serial_pos_left,
            logo_image=tpl.logo_image,
            partner_logo=tpl.partner_logo,
            signature_1_image=tpl.signature_1_image,
            signature_1_name=tpl.signature_1_name,
            signature_1_title=tpl.signature_1_title,
            signature_2_image=tpl.signature_2_image,
            signature_2_name=tpl.signature_2_name,
            signature_2_title=tpl.signature_2_title,
            show_qr_code=tpl.show_qr_code,
            show_seal=tpl.show_seal,
            is_default=False,
            is_active=True,
        )
        return redirect('certificate-template-edit', pk=new_tpl.pk)


# =============================================================================
# Instructor / Teacher Student Credential Records Ledger
# =============================================================================

class InstructorCertificateListView(RoleRequiredMixin, ListView):
    """
    Instructor and Faculty Student Credential Records Ledger.
    Displays all verified completion and examination certificates awarded to students
    enrolled in courses owned or taught by the logged-in instructor.
    """
    allowed_roles = ['instructor', 'teacher', 'admin']
    model = Certificate
    template_name = 'certificates/instructor_certificate_list.html'
    context_object_name = 'certificates'
    paginate_by = 25

    def get_base_queryset(self):
        user = self.request.user
        if getattr(user, 'is_admin', False) or user.is_superuser:
            return Certificate.objects.all().select_related('student', 'course')
        return Certificate.objects.filter(course__owner=user).select_related('student', 'course')

    def get_queryset(self):
        qs = self.get_base_queryset()

        # Filter by specific course
        course_id = self.request.GET.get('course', '').strip()
        if course_id:
            qs = qs.filter(course_id=course_id)

        # Keyword search
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                models.Q(certificate_code__icontains=q) |
                models.Q(student__username__icontains=q) |
                models.Q(student__first_name__icontains=q) |
                models.Q(student__last_name__icontains=q) |
                models.Q(student__email__icontains=q) |
                models.Q(course__title__icontains=q)
            )

        # Status filtering
        status = self.request.GET.get('status', 'all').strip().lower()
        if status == 'valid':
            qs = qs.filter(is_revoked=False)
        elif status == 'revoked':
            qs = qs.filter(is_revoked=True)
        elif status == 'distinction':
            qs = qs.filter(is_revoked=False, grade__icontains='Distinction')
        elif status == 'exam':
            qs = qs.filter(
                models.Q(is_revoked=False) &
                (models.Q(exam__isnull=False) | models.Q(certificate_type=Certificate.CertificateType.EXAM_VERIFIED))
            )

        return qs.order_by('-issued_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        base_qs = self.get_base_queryset()

        if getattr(user, 'is_admin', False) or user.is_superuser:
            teacher_courses = Course.objects.all().order_by('title')
        else:
            teacher_courses = Course.objects.filter(owner=user).order_by('title')

        exam_cert_count = base_qs.filter(
            models.Q(is_revoked=False) &
            (models.Q(exam__isnull=False) | models.Q(certificate_type=Certificate.CertificateType.EXAM_VERIFIED))
        ).count()

        context.update({
            'total_issued': base_qs.count(),
            'valid_count': base_qs.filter(is_revoked=False).count(),
            'distinction_count': base_qs.filter(is_revoked=False, grade__icontains='Distinction').count(),
            'exam_count': exam_cert_count,
            'teacher_courses': teacher_courses,
            'selected_course': self.request.GET.get('course', ''),
            'query': self.request.GET.get('q', ''),
            'active_status': self.request.GET.get('status', 'all'),
        })
        return context


class InstructorCertificateExportCSVView(RoleRequiredMixin, View):
    """
    Exports the instructor's student credentials roster to CSV for academic records.
    """
    allowed_roles = ['instructor', 'teacher', 'admin']

    def get(self, request, *args, **kwargs):
        user = request.user
        if getattr(user, 'is_admin', False) or user.is_superuser:
            qs = Certificate.objects.all().select_related('student', 'course')
        else:
            qs = Certificate.objects.filter(course__owner=user).select_related('student', 'course')

        course_id = request.GET.get('course', '').strip()
        if course_id:
            qs = qs.filter(course_id=course_id)

        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                models.Q(certificate_code__icontains=q) |
                models.Q(student__username__icontains=q) |
                models.Q(student__first_name__icontains=q) |
                models.Q(student__last_name__icontains=q) |
                models.Q(student__email__icontains=q) |
                models.Q(course__title__icontains=q)
            )

        status = request.GET.get('status', 'all').strip().lower()
        if status == 'valid':
            qs = qs.filter(is_revoked=False)
        elif status == 'revoked':
            qs = qs.filter(is_revoked=True)
        elif status == 'distinction':
            qs = qs.filter(is_revoked=False, grade__icontains='Distinction')
        elif status == 'exam':
            qs = qs.filter(
                models.Q(is_revoked=False) &
                (models.Q(exam__isnull=False) | models.Q(certificate_type=Certificate.CertificateType.EXAM_VERIFIED))
            )

        qs = qs.order_by('-issued_at')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        date_str = timezone.localdate().strftime('%Y%m%d')
        response['Content-Disposition'] = f'attachment; filename="instructor_certificates_{date_str}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Serial Code',
            'Recipient Full Name',
            'Recipient Username',
            'Recipient Email',
            'Course Title',
            'Grade / Standing',
            'Certificate Type',
            'SHA-256 Ledger Fingerprint',
            'Awarded Date',
            'Ledger Status',
        ])

        for cert in qs:
            writer.writerow([
                cert.certificate_code,
                cert.student_name,
                cert.student.username,
                cert.student.email,
                cert.program_title,
                cert.grade or 'PASS',
                cert.get_certificate_type_display(),
                cert.sha256_hash,
                cert.issued_at.strftime('%Y-%m-%d %H:%M') if cert.issued_at else '-',
                'REVOKED' if cert.is_revoked else 'VALID & VERIFIED',
            ])

        return response
