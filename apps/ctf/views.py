from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
import json
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

