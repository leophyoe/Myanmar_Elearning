import logging
from .models import Achievement, StudentAchievement

logger = logging.getLogger(__name__)


class AchievementEvaluationService:
    """
    Automated gamification engine. Awards achievement badges and points upon academic milestones.
    """

    @classmethod
    def evaluate_student(cls, student, event: str, context=None):
        context = context or {}
        awarded = []

        if event == "ENROLLMENT":
            cls._check_and_award(student, 'FIRST_STEP', awarded)

        elif event == "QUIZ_SUBMITTED":
            cls._check_and_award(student, 'QUIZ_EXPLORER', awarded)
            pct = context.get('percentage', 0)
            if pct >= 100:
                cls._check_and_award(student, 'PERFECT_SCORE', awarded)

        elif event == "ASSIGNMENT_SUBMITTED":
            cls._check_and_award(student, 'MISSION_SUBMITTED', awarded)

        elif event == "COURSE_COMPLETED":
            cls._check_and_award(student, 'COURSE_COMPLETER', awarded)

        elif event == "CERTIFICATE_ISSUED":
            cls._check_and_award(student, 'CERTIFIED_SPECIALIST', awarded)

        # Send notifications for freshly awarded achievements
        if awarded:
            from apps.notifications.services import NotificationService
            for ach in awarded:
                NotificationService.create_notification(
                    recipient=student,
                    title=f"🏆 Badge Unlocked: {ach.title}!",
                    message=f"You earned the '{ach.title}' badge (+{ach.points} XP): {ach.description}",
                    notification_type="SYSTEM"
                )

        return awarded

    @classmethod
    def _check_and_award(cls, student, badge_code: str, awarded_list: list):
        try:
            ach = Achievement.objects.filter(code=badge_code).first()
            if not ach:
                return
            if not StudentAchievement.objects.filter(student=student, achievement=ach).exists():
                StudentAchievement.objects.create(student=student, achievement=ach)
                awarded_list.append(ach)
        except Exception as e:
            logger.error(f"Error checking achievement {badge_code}: {e}")

