import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, ListView, UpdateView, View,
)

from apps.common.permissions import TeacherRequiredMixin
from apps.labs.bundles import BundleError

from .forms import ChallengeForm
from .models import Challenge, ChallengeCategory, SolvedChallenge
from .services import FlagVerificationService

class CtfBoardView(LoginRequiredMixin, ListView):
    model = Challenge
    template_name = 'ctf/ctf_board.html'
    context_object_name = 'challenges'

    def get_queryset(self):
        return Challenge.objects.filter(is_active=True).select_related('lab')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        solved_challenge_ids = set(
            SolvedChallenge.objects.filter(user=user).values_list('challenge_id', flat=True)
        )
        context['solved_challenge_ids'] = solved_challenge_ids
        context['categories'] = ChallengeCategory.choices

        # Group challenges by category for board layout
        grouped = {}
        for cat_key, cat_name in ChallengeCategory.choices:
            challenges_in_cat = [c for c in context['challenges'] if c.category == cat_key]
            if challenges_in_cat:
                grouped[cat_name] = challenges_in_cat
        context['grouped_challenges'] = grouped
        return context


class FlagSubmitView(LoginRequiredMixin, View):
    """AJAX flag submission endpoint."""

    def post(self, request, challenge_id):
        challenge = get_object_or_404(Challenge, id=challenge_id, is_active=True)

        try:
            data = json.loads(request.body)
            flag = data.get('flag', '')
        except (ValueError, KeyError):
            flag = request.POST.get('flag', '')

        if not flag:
            return JsonResponse({'success': False, 'message': 'Please enter a flag.'}, status=400)

        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        result = FlagVerificationService.verify_flag(
            user=request.user,
            challenge=challenge,
            submitted_flag_raw=flag,
            client_ip=client_ip
        )
        return JsonResponse(result)



# ----------------------------------------------------------------------
# Cyber Range studio — challenge authoring (/cyber/challenges/)
# ----------------------------------------------------------------------
class ChallengeManageListView(TeacherRequiredMixin, ListView):
    model = Challenge
    template_name = 'cyber/challenge_list.html'
    context_object_name = 'challenges'

    def get_queryset(self):
        return Challenge.objects.select_related('lab', 'module').order_by('category', 'points')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.labs.views import bundle_folders
        from django.conf import settings
        context['folders'] = bundle_folders(settings.CYBER_CHALLENGE_DIR)
        return context


class ChallengeCreateView(TeacherRequiredMixin, CreateView):
    model = Challenge
    form_class = ChallengeForm
    template_name = 'cyber/challenge_form.html'

    def get_success_url(self):
        return reverse('cyber-challenge-edit', kwargs={'challenge_id': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
        except BundleError as exc:
            form.add_error('bundle', str(exc))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Challenge “{self.object.title}” created"
            + (f" — bundle unpacked to cyber/challenges/{self.object.category}/{self.object.slug}/"
               if form.cleaned_data.get('bundle') else '.'),
        )
        return redirect(self.get_success_url())


class ChallengeUpdateView(TeacherRequiredMixin, UpdateView):
    model = Challenge
    form_class = ChallengeForm
    template_name = 'cyber/challenge_form.html'
    pk_url_kwarg = 'challenge_id'

    def get_success_url(self):
        return reverse('cyber-challenge-edit', kwargs={'challenge_id': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
        except BundleError as exc:
            form.add_error('bundle', str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"Challenge “{self.object.title}” updated.")
        return redirect(self.get_success_url())


class ChallengeDeleteView(TeacherRequiredMixin, DeleteView):
    model = Challenge
    template_name = 'cyber/challenge_confirm_delete.html'
    pk_url_kwarg = 'challenge_id'
    success_url = reverse_lazy('cyber-challenge-list')

    def form_valid(self, form):
        messages.info(
            self.request,
            "Challenge removed. Its bundle files stay in cyber/challenges/.",
        )
        return super().form_valid(form)
