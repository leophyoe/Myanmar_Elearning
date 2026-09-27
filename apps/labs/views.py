from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from .models import Lab, LabInstance, LabCategory, LabDifficulty
from .orchestrator import orchestrator

class LabListView(ListView):
    model = Lab
    template_name = 'labs/lab_list.html'
    context_object_name = 'labs'

    def get_queryset(self):
        queryset = Lab.objects.filter(is_active=True).select_related('template')
        category = self.request.GET.get('category')
        difficulty = self.request.GET.get('difficulty')
        if category:
            queryset = queryset.filter(template__category=category)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = LabCategory.choices
        context['difficulties'] = LabDifficulty.choices
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
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

        context['active_instance'] = active_instance
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

