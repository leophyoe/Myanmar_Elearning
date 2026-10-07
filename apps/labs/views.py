from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View,
)

from apps.common.permissions import TeacherRequiredMixin
from apps.ctf.models import Challenge, SolvedChallenge

from .bundles import BundleError
from .forms import LabBundleUploadForm, LabForm, LabTemplateForm
from .models import Lab, LabCategory, LabDifficulty, LabInstance, LabTemplate
from .orchestrator import orchestrator

class LabListView(ListView):
    model = Lab
    template_name = 'labs/lab_list.html'
    context_object_name = 'labs'

    def get_queryset(self):
        queryset = Lab.objects.filter(is_active=True).select_related('template')
        category = self.request.GET.get('category')
        difficulty = self.request.GET.get('difficulty')
        q = self.request.GET.get('q')
        if category:
            queryset = queryset.filter(template__category=category)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        if q:
            queryset = queryset.filter(title__icontains=q)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['categories'] = LabCategory.choices
        context['difficulties'] = LabDifficulty.choices
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        context['search_query'] = self.request.GET.get('q', '')

        all_active = Lab.objects.filter(is_active=True)
        context['total_labs_count'] = all_active.count()
        context['total_points_pool'] = all_active.aggregate(Sum('points'))['points__sum'] or 0

        if user.is_authenticated:
            context['active_instance'] = LabInstance.objects.filter(
                user=user,
                status__in=['running', 'provisioning']
            ).first()
            context['solved_lab_ids'] = list(
                SolvedChallenge.objects.filter(
                    user=user,
                    challenge__lab__isnull=False
                ).values_list('challenge__lab_id', flat=True)
            )
        else:
            context['active_instance'] = None
            context['solved_lab_ids'] = []

        return context


class LabDetailView(LoginRequiredMixin, DetailView):
    model = Lab
    template_name = 'labs/lab_detail.html'
    context_object_name = 'lab'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        lab = self.get_object()

        # Check for active instance
        active_instance = LabInstance.objects.filter(
            lab=lab,
            user=user,
            status__in=['provisioning', 'running']
        ).first()

        challenge = Challenge.objects.filter(lab=lab, is_active=True).first()
        is_solved = False
        if challenge and user.is_authenticated:
            is_solved = SolvedChallenge.objects.filter(user=user, challenge=challenge).exists()

        context['active_instance'] = active_instance
        context['challenge'] = challenge
        context['is_solved'] = is_solved
        context['max_extensions'] = getattr(settings, 'LAB_MAX_EXTENSIONS', 2)
        context['extension_minutes'] = getattr(settings, 'LAB_EXTENSION_MINUTES', 30)
        return context


class LabStartView(LoginRequiredMixin, View):
    def post(self, request, lab_id):
        lab = get_object_or_404(Lab, id=lab_id)

        # Enforce quota: Stop any other running instance for this student
        existing_instances = LabInstance.objects.filter(
            user=request.user,
            status__in=['running', 'provisioning']
        )
        for inst in existing_instances:
            orchestrator.stop_instance(inst)

        # Create fresh instance record
        instance = LabInstance.objects.create(
            lab=lab,
            user=request.user,
            status='provisioning'
        )

        success = orchestrator.start_instance(instance)
        if success:
            messages.success(request, f"Lab '{lab.title}' started successfully. Terminal session ready.")
        else:
            messages.error(request, f"Failed to start lab environment: {instance.error_log}")

        return redirect('lab-detail', slug=lab.slug)


class LabStopView(LoginRequiredMixin, View):
    def post(self, request, instance_id):
        instance = get_object_or_404(LabInstance, id=instance_id, user=request.user)
        orchestrator.stop_instance(instance)
        messages.info(request, "Lab environment stopped and resources released.")
        return redirect('lab-detail', slug=instance.lab.slug)


class LabResetView(LoginRequiredMixin, View):
    def post(self, request, instance_id):
        instance = get_object_or_404(LabInstance, id=instance_id, user=request.user)
        orchestrator.reset_instance(instance)
        messages.success(request, "Lab environment cleanly reset with a fresh flag.")
        return redirect('lab-detail', slug=instance.lab.slug)


class LabStatusApiView(LoginRequiredMixin, View):
    def get(self, request, instance_id):
        instance = get_object_or_404(LabInstance, id=instance_id, user=request.user)
        return JsonResponse({
            'id': str(instance.id),
            'status': instance.status,
            'target_ip': instance.target_ip,
            'remaining_seconds': instance.remaining_seconds(),
            'is_expired': instance.is_expired(),
        })


class LabExtendView(LoginRequiredMixin, View):
    def post(self, request, instance_id):
        instance = get_object_or_404(LabInstance, id=instance_id, user=request.user)
        max_extensions = getattr(settings, 'LAB_MAX_EXTENSIONS', 2)
        ext_minutes = getattr(settings, 'LAB_EXTENSION_MINUTES', 30)

        if instance.status == 'running' and instance.extensions_used < max_extensions:
            base_time = instance.expires_at if (instance.expires_at and instance.expires_at > timezone.now()) else timezone.now()
            instance.expires_at = base_time + timedelta(minutes=ext_minutes)
            instance.extensions_used += 1
            instance.save(update_fields=['expires_at', 'extensions_used'])
            messages.success(request, f"Lab sandbox extended by {ext_minutes} minutes.")
        else:
            messages.warning(request, "Lab instance cannot be extended or maximum extensions reached.")

        return redirect('lab-detail', slug=instance.lab.slug)



# ----------------------------------------------------------------------
# Cyber Range studio — teacher/admin authoring for labs and challenges
# (one section: /cyber/, one content folder: cyber/)
# ----------------------------------------------------------------------
def bundle_folders(base_dir) -> set:
    """Relative paths of every bundle folder under ``base_dir``."""
    base = Path(base_dir)
    if not base.exists():
        return set()
    return {
        str(p.relative_to(base))
        for p in base.rglob('*')
        if p.is_dir() and any(c.is_file() for c in p.iterdir())
    }


class CyberHomeView(TeacherRequiredMixin, TemplateView):
    """Single dashboard for labs, lab templates and CTF challenges."""
    template_name = 'cyber/manage_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lab_count'] = Lab.objects.filter(is_active=True).count()
        context['template_count'] = LabTemplate.objects.count()
        context['challenge_count'] = Challenge.objects.count()
        context['lab_folders'] = bundle_folders(settings.CYBER_LAB_DIR)
        context['challenge_folders'] = bundle_folders(settings.CYBER_CHALLENGE_DIR)
        context['lab_content_dir'] = 'cyber/labs'
        context['challenge_content_dir'] = 'cyber/challenges'
        context['recent_labs'] = Lab.objects.select_related('template').order_by('-created_at')[:5]
        context['recent_challenges'] = Challenge.objects.order_by('-created_at')[:5]
        return context


class LabManageListView(TeacherRequiredMixin, ListView):
    model = Lab
    template_name = 'cyber/lab_list.html'
    context_object_name = 'labs'

    def get_queryset(self):
        return Lab.objects.select_related('template').order_by('title')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['folders'] = bundle_folders(settings.CYBER_LAB_DIR)
        return context


class LabTemplateListView(TeacherRequiredMixin, ListView):
    model = LabTemplate
    template_name = 'cyber/template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return LabTemplate.objects.order_by('category', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['folders'] = bundle_folders(settings.CYBER_LAB_DIR)
        return context


class LabCreateView(TeacherRequiredMixin, CreateView):
    model = Lab
    form_class = LabForm
    template_name = 'cyber/lab_form.html'

    def get_initial(self):
        initial = super().get_initial()
        template_id = self.request.GET.get('template')
        if template_id:
            initial['template'] = template_id
        return initial

    def get_success_url(self):
        return reverse('cyber-lab-edit', kwargs={'lab_id': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
        except BundleError as exc:
            form.add_error('bundle', str(exc))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Lab “{self.object.title}” saved"
            + (f" — bundle unpacked to cyber/labs/{self.object.template.docker_compose_path}/"
               if form.cleaned_data.get('bundle') else '.'),
        )
        return redirect(self.get_success_url())


class LabUpdateView(TeacherRequiredMixin, UpdateView):
    model = Lab
    form_class = LabForm
    template_name = 'cyber/lab_form.html'
    pk_url_kwarg = 'lab_id'

    def get_success_url(self):
        return reverse('cyber-lab-edit', kwargs={'lab_id': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
        except BundleError as exc:
            form.add_error('bundle', str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"Lab “{self.object.title}” updated.")
        return redirect(self.get_success_url())


class LabDeleteView(TeacherRequiredMixin, DeleteView):
    model = Lab
    template_name = 'cyber/lab_confirm_delete.html'
    pk_url_kwarg = 'lab_id'
    success_url = reverse_lazy('cyber-lab-list')

    def form_valid(self, form):
        messages.info(
            self.request,
            "Lab removed. Its bundle files stay in cyber/labs/ for rebuilding.",
        )
        return super().form_valid(form)


class LabTemplateUpdateView(TeacherRequiredMixin, UpdateView):
    model = LabTemplate
    form_class = LabTemplateForm
    template_name = 'cyber/template_form.html'
    pk_url_kwarg = 'template_id'

    def get_success_url(self):
        return reverse('cyber-template-edit', kwargs={'template_id': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f"Template “{self.object.name}” updated.")
        return redirect(self.get_success_url())


class LabBundleUploadView(TeacherRequiredMixin, CreateView):
    """Upload a zip bundle → files land in cyber/labs/ + a LabTemplate row."""
    model = LabTemplate
    form_class = LabBundleUploadForm
    template_name = 'cyber/lab_upload.html'

    def form_valid(self, form):
        try:
            self.object = form.save()
        except BundleError as exc:
            form.add_error('bundle', str(exc))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Bundle unpacked to cyber/labs/{self.object.docker_compose_path}/. "
            "Now attach it to a lab exercise.",
        )
        return redirect(reverse('cyber-lab-create') + f'?template={self.object.pk}')


class LabTemplateBuildView(TeacherRequiredMixin, View):
    """Trigger Docker image build for a template bundle."""

    def post(self, request, template_id):
        template = get_object_or_404(LabTemplate, pk=template_id)
        from .builder import build_template_image
        ok, msg = build_template_image(template)
        if ok:
            messages.success(request, f"Image build: {msg}")
        else:
            messages.error(request, f"Image build failed: {msg}")

        next_url = request.POST.get('next') or reverse('cyber-template-list')
        return redirect(next_url)

