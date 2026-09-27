from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count
from .models import (
    LabCategory, Lab, LabInstance, LabObjective, LabHint, LabSubmission,
    ChallengeCategory, Challenge, ChallengeSubmission,
    CTFEvent, CTFScore, LabDifficulty, LabType, LabInstanceStatus,
    ExternalResource
)
from .docker_service import docker_service
from .providers import get_lab_provider


class LabListView(ListView):
    """
    Catalog of all published training labs, machines, and guided exercises.
    """
    model = Lab
    template_name = 'labs/lab_list.html'
    context_object_name = 'labs'
    paginate_by = 12

    def get_queryset(self):
        qs = Lab.objects.filter(is_published=True).select_related('category', 'created_by').prefetch_related('objectives')
        q = self.request.GET.get('q', '').strip()
        category = self.request.GET.get('category', '').strip()
        difficulty = self.request.GET.get('difficulty', '').strip()
        lab_type = self.request.GET.get('type', '').strip()
        source = self.request.GET.get('source', '').strip()
        collection = self.request.GET.get('collection', '').strip()

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(short_description__icontains=q) |
                Q(description__icontains=q) |
                Q(category__name__icontains=q) |
                Q(source_name__icontains=q)
            ).distinct()

        if category:
            qs = qs.filter(category__slug=category)

        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        if lab_type:
            qs = qs.filter(type=lab_type)

        if source:
            qs = qs.filter(source_name__iexact=source)
        elif collection == 'beginner':
            qs = qs.filter(source_name='LabEx')

        return qs.order_by('display_order', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = LabCategory.objects.all()
        context['difficulties'] = LabDifficulty.choices
        context['lab_types'] = LabType.choices
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_source'] = self.request.GET.get('source', '')
        context['selected_collection'] = self.request.GET.get('collection', '')
        context['beginner_labs_count'] = Lab.objects.filter(is_published=True, source_name='LabEx').count()
        context['total_labs_count'] = Lab.objects.filter(is_published=True).count()

        # Active student instance if logged in
        if self.request.user.is_authenticated:
            context['active_instance'] = LabInstance.objects.filter(
                student=self.request.user,
                status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
            ).first()
        return context


class LabDetailView(DetailView):
    """
    Detailed briefing, objectives, and terminal interface access for a lab.
    """
    model = Lab
    template_name = 'labs/lab_detail.html'
    context_object_name = 'lab'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.is_instructor or user.is_staff):
            return Lab.objects.all().select_related('category', 'created_by')
        return Lab.objects.filter(is_published=True).select_related('category', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['objectives'] = self.object.objectives.all().order_by('order')
        context['hints'] = self.object.hints.all().order_by('order')

        # Check if user has an active running instance for this lab
        user = self.request.user
        if user.is_authenticated:
            context['user_instance'] = LabInstance.objects.filter(
                student=user,
                lab=self.object,
                status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
            ).first()

            # Check if user has completed this lab
            context['is_completed'] = self.object.submissions.filter(
                student=user,
                is_correct=True
            ).exists()

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.user.is_authenticated:
            messages.error(request, "Authentication required to submit flags.")
            return redirect('labs:lab-detail', slug=self.object.slug)

        submitted_flag = request.POST.get('submitted_flag', '').strip()
        objective_id = request.POST.get('objective_id', '').strip()

        if not submitted_flag:
            messages.error(request, "Please enter a flag to submit.")
            return redirect('labs:lab-detail', slug=self.object.slug)

        flags_qs = self.object.flags.all()
        if objective_id:
            flags_qs = flags_qs.filter(objective_id=objective_id)

        matched_flag = None
        for f in flags_qs:
            if f.static_flag and f.static_flag.strip() == submitted_flag:
                matched_flag = f
                break

        if matched_flag:
            already_awarded = LabSubmission.objects.filter(
                lab=self.object,
                student=request.user,
                is_correct=True,
                flag_submitted=submitted_flag
            ).exists()

            if already_awarded:
                messages.info(request, "You have already captured and claimed this flag!")
            else:
                pts = matched_flag.points
                LabSubmission.objects.create(
                    lab=self.object,
                    student=request.user,
                    flag_submitted=submitted_flag,
                    is_correct=True,
                    points_awarded=pts
                )
                score, _ = CTFScore.objects.get_or_create(student=request.user)
                score.points += pts
                score.lab_points += pts
                score.labs_completed_count += 1
                score.save()

                messages.success(request, f"🎉 Outstanding! Correct flag! You gained +{pts} points.")
        else:
            LabSubmission.objects.create(
                lab=self.object,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=False,
                points_awarded=0
            )
            messages.error(request, "❌ Incorrect flag. Verify your target exploitation.")

        return redirect('labs:lab-detail', slug=self.object.slug)


class ChallengeListView(ListView):
    """
    Jeopardy-style CTF challenge portal organized by cybersecurity disciplines.
    """
    model = Challenge
    template_name = 'labs/challenge_list.html'
    context_object_name = 'challenges'
    paginate_by = 16

    def get_queryset(self):
        qs = Challenge.objects.filter(is_active=True).select_related('category')
        category = self.request.GET.get('category', '').strip()
        difficulty = self.request.GET.get('difficulty', '').strip()

        if category:
            qs = qs.filter(category__slug=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ChallengeCategory.objects.all()
        context['difficulties'] = LabDifficulty.choices
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')

        if self.request.user.is_authenticated:
            context['solved_challenge_ids'] = set(
                ChallengeSubmission.objects.filter(
                    student=self.request.user,
                    is_correct=True
                ).values_list('challenge_id', flat=True)
            )
        else:
            context['solved_challenge_ids'] = set()
        return context


class ChallengeDetailView(DetailView):
    """
    Individual CTF challenge view with flag submission gateway.
    """
    model = Challenge
    template_name = 'labs/challenge_detail.html'
    context_object_name = 'challenge'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Challenge.objects.filter(is_active=True).select_related('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['is_solved'] = self.object.submissions.filter(
                student=self.request.user,
                is_correct=True
            ).exists()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.user.is_authenticated:
            messages.error(request, "Authentication required to submit flags.")
            return redirect('labs:challenge-detail', slug=self.object.slug)

        submitted_flag = request.POST.get('flag', '').strip()
        if not submitted_flag:
            messages.error(request, "Please enter a flag to submit.")
            return redirect('labs:challenge-detail', slug=self.object.slug)

        already_solved = ChallengeSubmission.objects.filter(
            challenge=self.object,
            student=request.user,
            is_correct=True
        ).exists()

        if already_solved:
            messages.info(request, "You have already solved this challenge!")
            return redirect('labs:challenge-detail', slug=self.object.slug)

        if submitted_flag == self.object.flag.strip():
            pts = self.object.points
            ChallengeSubmission.objects.create(
                challenge=self.object,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=True,
                points_awarded=pts
            )
            self.object.solves_count += 1
            self.object.save(update_fields=['solves_count'])

            score, _ = CTFScore.objects.get_or_create(student=request.user)
            score.points += pts
            score.challenge_points += pts
            score.solves_count += 1
            score.save()

            messages.success(request, f"🏆 Congratulations! Flag verified! You earned +{pts} points.")
        else:
            ChallengeSubmission.objects.create(
                challenge=self.object,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=False,
                points_awarded=0
            )
            messages.error(request, "❌ Incorrect flag. Try harder!")

        return redirect('labs:challenge-detail', slug=self.object.slug)


class LeaderboardView(ListView):
    """
    Global Cyber Range and CTF scoreboard.
    """
    model = CTFScore
    template_name = 'labs/leaderboard.html'
    context_object_name = 'leaderboard_entries'
    paginate_by = 50

    def get_queryset(self):
        return CTFScore.objects.select_related('student').order_by('-points', '-updated_at')


class CTFEventListView(ListView):
    """
    Competitive tournaments and hackathons schedule.
    """
    model = CTFEvent
    template_name = 'labs/ctf_events.html'
    context_object_name = 'events'

    def get_queryset(self):
        return CTFEvent.objects.all().order_by('-start_time')


class LabStartView(LoginRequiredMixin, View):
    """
    Spawns or resumes an isolated sandbox container target for the student.
    Uses the specialized LabProvider (e.g. OWASPJuiceShopProvider, WebApplicationLabProvider, DockerLabProvider).
    """
    def post(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug, is_published=True)
        try:
            provider = get_lab_provider(lab)
            instance = provider.start(request.user, lab)
            messages.success(
                request,
                f"🚀 Sandbox target '{lab.name}' online! Assigned IP: {instance.assigned_ip}"
            )
            if lab.type == LabType.WEB_APPLICATION and instance.access_url:
                return redirect(instance.access_url)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        except Exception as e:
            messages.error(request, f"Unable to start sandbox target: {e}")

        return redirect('labs:lab-detail', slug=slug)


class LabStopView(LoginRequiredMixin, View):
    """
    Terminates the student's active sandbox container.
    """
    def post(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)
        instance = LabInstance.objects.filter(
            student=request.user,
            lab=lab,
            status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
        ).first()

        if instance:
            provider = get_lab_provider(lab)
            provider.stop(instance)
            messages.info(request, f"Sandbox container for '{lab.name}' terminated.")
        else:
            messages.warning(request, "No active sandbox instance found to terminate.")

        return redirect('labs:lab-detail', slug=slug)


class LabResetView(LoginRequiredMixin, View):
    """
    Resets the container sandbox to a fresh initial state.
    """
    def post(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)
        instance = LabInstance.objects.filter(
            student=request.user,
            lab=lab,
            status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
        ).first()

        provider = get_lab_provider(lab)
        if instance:
            fresh = provider.reset(instance)
            messages.success(request, f"🔄 Sandbox for '{lab.name}' reset to fresh state.")
            if lab.type == LabType.WEB_APPLICATION and fresh.access_url:
                return redirect(fresh.access_url)
        else:
            try:
                fresh = provider.start(request.user, lab)
                messages.success(request, f"Sandbox for '{lab.name}' launched.")
                if lab.type == LabType.WEB_APPLICATION and fresh.access_url:
                    return redirect(fresh.access_url)
            except Exception as e:
                messages.error(request, f"Could not start sandbox: {e}")

        return redirect('labs:lab-detail', slug=slug)


class LabExtendView(LoginRequiredMixin, View):
    """
    Extends student's active lab runtime by 30 minutes.
    """
    def post(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)
        instance = LabInstance.objects.filter(
            student=request.user,
            lab=lab,
            status=LabInstanceStatus.RUNNING
        ).first()

        if instance:
            try:
                provider = get_lab_provider(lab)
                provider.extend(instance, minutes=30)
                messages.success(request, f"⏱️ Lab runtime extended (+30 mins). New expiration: {instance.expires_at.strftime('%H:%M:%S')} UTC")
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))
        else:
            messages.error(request, "Cannot extend runtime on an inactive machine.")

        return redirect('labs:lab-detail', slug=slug)


class LabStatusView(LoginRequiredMixin, View):
    """
    Lightweight JSON status endpoint for HTMX / Alpine live polling.
    """
    def get(self, request, slug):
        lab = get_object_or_404(Lab, slug=slug)
        instance = LabInstance.objects.filter(
            student=request.user,
            lab=lab,
            status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
        ).first()

        if not instance:
            return JsonResponse({'is_running': False, 'status': 'STOPPED'})

        now = timezone.now()
        rem_seconds = max(0, int((instance.expires_at - now).total_seconds())) if instance.expires_at else 0

        return JsonResponse({
            'is_running': instance.status == LabInstanceStatus.RUNNING,
            'status': instance.status,
            'assigned_ip': instance.assigned_ip or "10.10.x.x",
            'port_mappings': instance.port_mappings or "80/tcp, 443/tcp",
            'time_remaining_seconds': rem_seconds,
            'terminal_url': f"/labs/{lab.slug}/terminal/",
        })


class LabTerminalView(LoginRequiredMixin, DetailView):
    """
    In-browser Interactive Web Terminal and Target Console Interface.
    """
    model = Lab
    template_name = 'labs/lab_terminal.html'
    context_object_name = 'lab'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = LabInstance.objects.filter(
            student=self.request.user,
            lab=self.object,
            status=LabInstanceStatus.RUNNING
        ).first()
        context['instance'] = instance
        return context


class LabGatewayView(LoginRequiredMixin, View):
    """
    Secure Reverse-Proxy Gateway & Interactive Web Security Training Workspace (/labs/i/<uuid:token>/).
    Enforces strict cross-student isolation: verifies token ownership so Student A cannot access Student B's instance.
    """
    def get(self, request, token):
        instance = get_object_or_404(LabInstance, uuid=token)

        # 1. Strict Cross-Student Access Verification
        if instance.student != request.user and not (request.user.is_staff or request.user.is_superuser):
            return HttpResponseForbidden(
                "403 Forbidden: Security Isolation Policy. You are not authorized to access another student's isolated lab environment."
            )

        lab = instance.lab
        provider = get_lab_provider(lab)

        # 2. Challenge and progress tracking
        challenges_data = []
        raw_challenges = getattr(provider, 'CHALLENGES', [])

        solved_flags = set(
            LabSubmission.objects.filter(
                lab=lab,
                student=request.user,
                is_correct=True
            ).values_list('flag_submitted', flat=True)
        )

        all_instance_flags = getattr(provider, 'get_all_flags_for_instance', lambda inst: {})(instance)

        for ch in raw_challenges:
            ch_id = ch['id']
            expected_flag = all_instance_flags.get(ch_id, '')
            is_solved = expected_flag in solved_flags

            challenges_data.append({
                'id': ch_id,
                'name': ch['name'],
                'category': ch.get('category', 'Web Security'),
                'difficulty': ch.get('difficulty', 'Beginner'),
                'points': ch.get('points', 50),
                'description': ch.get('description', ''),
                'owasp_category': ch.get('owasp_category', ''),
                'is_solved': is_solved,
                'expected_flag': expected_flag if request.user.is_staff else None,
            })

        now = timezone.now()
        rem_seconds = max(0, int((instance.expires_at - now).total_seconds())) if instance.expires_at else 0

        context = {
            'instance': instance,
            'lab': lab,
            'provider': provider,
            'challenges': challenges_data,
            'solved_count': sum(1 for c in challenges_data if c['is_solved']),
            'total_challenges': len(challenges_data),
            'time_remaining_seconds': rem_seconds,
            'is_expired': instance.is_expired,
            'is_running': instance.is_running,
            'gateway_token': str(token),
        }
        return render(request, 'labs/juice_shop_workspace.html', context)

    def post(self, request, token):
        instance = get_object_or_404(LabInstance, uuid=token)

        # 1. Strict Cross-Student Access Verification
        if instance.student != request.user and not (request.user.is_staff or request.user.is_superuser):
            return HttpResponseForbidden(
                "403 Forbidden: Security Violation. You are not authorized to submit flags to this lab instance."
            )

        if not instance.is_running or instance.is_expired:
            messages.error(request, "This lab instance is not running or has expired. Please restart or reset your lab.")
            return redirect('labs:lab-gateway', token=token)

        submitted_flag = request.POST.get('flag', '').strip()
        challenge_id = request.POST.get('challenge_id', '').strip()

        if not submitted_flag:
            messages.error(request, "Please enter a flag to submit.")
            return redirect('labs:lab-gateway', token=token)

        provider = get_lab_provider(instance.lab)
        is_valid = False
        challenge_info = None

        if hasattr(provider, 'verify_flag'):
            is_valid, challenge_info = provider.verify_flag(instance, submitted_flag, challenge_id or None)
        else:
            flag_obj = instance.lab.flags.filter(static_flag=submitted_flag).first()
            if flag_obj:
                is_valid = True
                challenge_info = {'id': 'flag', 'name': 'Lab Flag', 'points': flag_obj.points}

        if is_valid and challenge_info:
            pts = challenge_info.get('points', 50)
            already_solved = LabSubmission.objects.filter(
                lab=instance.lab,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=True
            ).exists()

            if already_solved:
                messages.info(request, f"You have already captured the flag for '{challenge_info['name']}'!")
            else:
                LabSubmission.objects.create(
                    lab=instance.lab,
                    student=request.user,
                    flag_submitted=submitted_flag,
                    is_correct=True,
                    points_awarded=pts
                )
                score, _ = CTFScore.objects.get_or_create(student=request.user)
                score.points += pts
                score.lab_points += pts
                score.labs_completed_count += 1
                score.save()

                messages.success(request, f"🎉 Flag Verified! You solved '{challenge_info['name']}' and earned +{pts} points!")

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'solved': True, 'points': pts, 'challenge': challenge_info['name']})
        else:
            LabSubmission.objects.create(
                lab=instance.lab,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=False,
                points_awarded=0
            )
            messages.error(request, "❌ Incorrect flag. Verify your vulnerability exploit against your assigned container.")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'solved': False, 'message': 'Incorrect flag.'})

        return redirect('labs:lab-gateway', token=token)


class LabAiHintView(LoginRequiredMixin, View):
    """
    Provides Socratic conceptual AI Tutor hints for students working on Web Application Labs.
    Does not leak direct flags; guides candidates on vulnerability theory, tooling, and methodology.
    """
    def get(self, request, token):
        instance = get_object_or_404(LabInstance, uuid=token)

        if instance.student != request.user and not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({"error": "Forbidden: Cross-student access violation."}, status=403)

        challenge_id = request.GET.get('challenge_id', '').strip()
        try:
            level = int(request.GET.get('level', 1))
        except (ValueError, TypeError):
            level = 1

        provider = get_lab_provider(instance.lab)
        if hasattr(provider, 'get_hint'):
            hint_data = provider.get_hint(challenge_id, level)
            return JsonResponse(hint_data)

        return JsonResponse({
            "challenge_id": challenge_id,
            "level": 1,
            "hint": "Analyze the HTTP traffic and application source assets in your browser DevTools.",
            "penalty_percent": 0
        })

    def post(self, request, token):
        return self.get(request, token)


class LinuxLabListView(ListView):
    """
    Dedicated view for Linux Guided Cyber Security Labs (/labs/linux/).
    Supports search, category filter, difficulty filter, and instance status.
    """
    model = Lab
    template_name = 'labs/linux_labs.html'
    context_object_name = 'labs'
    paginate_by = 12

    def get_queryset(self):
        qs = Lab.objects.filter(is_published=True, source_name="LearnToCloud").select_related('category', 'created_by').prefetch_related('objectives')
        q = self.request.GET.get('q', '').strip()
        category = self.request.GET.get('category', '').strip()
        difficulty = self.request.GET.get('difficulty', '').strip()

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(short_description__icontains=q) |
                Q(description__icontains=q) |
                Q(category__name__icontains=q)
            ).distinct()

        if category:
            qs = qs.filter(category__slug=category)

        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs.order_by('display_order', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = LabCategory.objects.filter(slug__startswith='linux-')
        context['difficulties'] = LabDifficulty.choices
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        context['total_linux_labs_count'] = Lab.objects.filter(is_published=True, source_name="LearnToCloud").count()

        if self.request.user.is_authenticated:
            context['active_instance'] = LabInstance.objects.filter(
                student=self.request.user,
                status__in=[LabInstanceStatus.RUNNING, LabInstanceStatus.CREATING]
            ).first()
            context['completed_lab_ids'] = set(
                LabSubmission.objects.filter(
                    student=self.request.user,
                    is_correct=True
                ).values_list('lab_id', flat=True)
            )
        else:
            context['active_instance'] = None
            context['completed_lab_ids'] = set()
        return context


class LinuxChallengeListView(ListView):
    """
    Dedicated CTF arena for Linux challenges (/ctf/linux/).
    Displays challenge cards, categories, difficulty, points, and solved status.
    """
    model = Challenge
    template_name = 'labs/linux_ctf.html'
    context_object_name = 'challenges'
    paginate_by = 16

    def get_queryset(self):
        qs = Challenge.objects.filter(is_active=True, category__slug__startswith='linux-').select_related('category')
        category = self.request.GET.get('category', '').strip()
        difficulty = self.request.GET.get('difficulty', '').strip()

        if category:
            qs = qs.filter(category__slug=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs.order_by('difficulty', 'points')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ChallengeCategory.objects.filter(slug__startswith='linux-')
        context['difficulties'] = LabDifficulty.choices
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        context['total_linux_challenges'] = Challenge.objects.filter(is_active=True, category__slug__startswith='linux-').count()

        if self.request.user.is_authenticated:
            solved_ids = set(
                ChallengeSubmission.objects.filter(
                    student=self.request.user,
                    is_correct=True
                ).values_list('challenge_id', flat=True)
            )
            context['solved_challenge_ids'] = solved_ids
            all_linux_ids = set(Challenge.objects.filter(is_active=True, category__slug__startswith='linux-').values_list('id', flat=True))
            context['user_solved_count'] = len(solved_ids.intersection(all_linux_ids))
        else:
            context['solved_challenge_ids'] = set()
            context['user_solved_count'] = 0
        return context


class LinuxChallengeDetailView(DetailView):
    """
    Individual Linux CTF challenge view with flag submission gateway (/ctf/linux/<slug>/).
    Flags are compared strictly server-side; never exposed in response.
    """
    model = Challenge
    template_name = 'labs/linux_challenge_detail.html'
    context_object_name = 'challenge'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Challenge.objects.filter(is_active=True).select_related('category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['is_solved'] = self.object.submissions.filter(
                student=self.request.user,
                is_correct=True
            ).exists()
        else:
            context['is_solved'] = False
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.user.is_authenticated:
            messages.error(request, "Authentication required to submit flags.")
            return redirect('linux-challenge-detail', slug=self.object.slug)

        submitted_flag = request.POST.get('flag', '').strip()
        if not submitted_flag:
            messages.error(request, "Please enter a flag to submit.")
            return redirect('linux-challenge-detail', slug=self.object.slug)

        already_solved = ChallengeSubmission.objects.filter(
            challenge=self.object,
            student=request.user,
            is_correct=True
        ).exists()

        if already_solved:
            messages.info(request, "You have already solved this challenge!")
            return redirect('linux-challenge-detail', slug=self.object.slug)

        if submitted_flag == self.object.flag.strip():
            pts = self.object.points
            ChallengeSubmission.objects.create(
                challenge=self.object,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=True,
                points_awarded=pts
            )
            self.object.solves_count += 1
            self.object.save(update_fields=['solves_count'])

            score, _ = CTFScore.objects.get_or_create(student=request.user)
            score.points += pts
            score.challenge_points += pts
            score.solves_count += 1
            score.save()

            messages.success(request, f"🏆 Congratulations! Flag verified! You earned +{pts} points.")
        else:
            ChallengeSubmission.objects.create(
                challenge=self.object,
                student=request.user,
                flag_submitted=submitted_flag,
                is_correct=False,
                points_awarded=0
            )
            messages.error(request, "❌ Incorrect flag. Try harder!")

        return redirect('linux-challenge-detail', slug=self.object.slug)


class HackerTestView(TemplateView):
    """
    Dedicated view for HackerTest.net external practice resource (/challenges/hackertest/).
    Displays platform information, attribution, learning paths, and safe external link.
    """
    template_name = 'labs/hackertest_resource.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resource = ExternalResource.objects.filter(slug='hackertest', is_active=True).first()
        context['resource'] = resource
        context['original_challenges'] = Challenge.objects.filter(
            category__slug='future-tech-security-challenges',
            is_active=True
        ).order_by('difficulty', 'points')
        return context

