import hmac
import hashlib
from django.utils import timezone
from datetime import timedelta
from .models import Challenge, FlagSubmission, SolvedChallenge
from apps.labs.models import LabInstance

class FlagVerificationService:
    """
    Constant-time, rate-limited flag evaluation engine.
    Ensures correct flags are never leaked and brute-forcing is blocked.
    """

    RATE_LIMIT_WINDOW_SECONDS = 60
    MAX_ATTEMPTS_PER_WINDOW = 5

    @classmethod
    def verify_flag(cls, user, challenge, submitted_flag_raw, client_ip=None):
        clean_flag = submitted_flag_raw.strip()

        # 1. Check if user already solved this challenge
        if SolvedChallenge.objects.filter(user=user, challenge=challenge).exists():
            return {
                'success': False,
                'already_solved': True,
                'message': 'Challenge has already been completed.'
            }

        # 2. Rate-limiting check (Anti-bruteforce)
        recent_window = timezone.now() - timedelta(seconds=cls.RATE_LIMIT_WINDOW_SECONDS)
        recent_attempts_count = FlagSubmission.objects.filter(
            user=user,
            challenge=challenge,
            created_at__gte=recent_window
        ).count()

        if recent_attempts_count >= cls.MAX_ATTEMPTS_PER_WINDOW:
            return {
                'success': False,
                'rate_limited': True,
                'message': f"Rate limit exceeded. Maximum {cls.MAX_ATTEMPTS_PER_WINDOW} attempts per minute. Please wait."
            }

        # 3. Hash the submitted flag
        submitted_hash = hashlib.sha256(clean_flag.encode()).hexdigest()
        is_correct = False

        if challenge.is_dynamic and challenge.lab:
            # Check dynamic flag generated for student's active lab instance
            instance = LabInstance.objects.filter(
                lab=challenge.lab,
                user=user,
                status__in=['running', 'provisioning']
            ).first()

            if instance and instance.flag_hash:
                is_correct = hmac.compare_digest(submitted_hash, instance.flag_hash)
            elif instance and instance.dynamic_flag:
                is_correct = hmac.compare_digest(clean_flag, instance.dynamic_flag)
        else:
            # Check static flag hash
            if challenge.flag_hash:
                is_correct = hmac.compare_digest(submitted_hash, challenge.flag_hash)

        # 4. Record submission attempt audit log
        attempt_number = FlagSubmission.objects.filter(user=user, challenge=challenge).count() + 1
        FlagSubmission.objects.create(
            user=user,
            challenge=challenge,
            submitted_flag_clean=clean_flag[:64],  # Truncate to prevent payload abuse
            is_correct=is_correct,
            ip_address=client_ip,
            attempt_number=attempt_number
        )

        # 5. If correct, award points and record solve
        if is_correct:
            SolvedChallenge.objects.create(
                user=user,
                challenge=challenge,
                points_awarded=challenge.points
            )

            # Update student total points (only for students, admins/staff do not compete)
            if getattr(user, 'role', None) == 'student' and not user.is_staff and not user.is_superuser:
                profile = getattr(user, 'student_profile', None)
                if profile:
                    profile.points += challenge.points
                    profile.save(update_fields=['points'])

                # Check for badge unlock criteria
                from apps.scoring.services import BadgeAwardService
                BadgeAwardService.evaluate_user_achievements(user)

            return {
                'success': True,
                'points': challenge.points,
                'message': f"Flag Accepted! +{challenge.points} Points awarded."
            }

        return {
            'success': False,
            'message': "Incorrect flag. Verify your findings and try again."
        }

