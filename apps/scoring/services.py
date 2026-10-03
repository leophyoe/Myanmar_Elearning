from .models import Badge, UserBadge, BadgeCriteriaType
from apps.courses.models import UserProgress
from apps.ctf.models import SolvedChallenge

class BadgeAwardService:
    """
    Evaluates criteria and automatically awards badges to qualifying students.
    """

    @classmethod
    def evaluate_user_achievements(cls, user):
        profile = getattr(user, 'student_profile', None)
        if not profile:
            return

        points = profile.points
        labs_completed = UserProgress.objects.filter(user=user, lab__isnull=False, is_completed=True).count()
        challenges_solved = SolvedChallenge.objects.filter(user=user).count()

        from apps.courses.models import Enrollment
        from apps.projects.models import ProjectSubmission
        courses_completed = Enrollment.objects.filter(student=user, status=Enrollment.Status.COMPLETED).count()
        projects_completed = ProjectSubmission.objects.filter(
            student=user, status=ProjectSubmission.Status.COMPLETED
        ).count()

        # Check all badges
        unearned_badges = Badge.objects.exclude(awarded_users__user=user)

        for badge in unearned_badges:
            should_award = False

            if badge.criteria_type == BadgeCriteriaType.POINTS_THRESHOLD:
                if points >= badge.criteria_threshold:
                    should_award = True
            elif badge.criteria_type == BadgeCriteriaType.LABS_COMPLETED:
                if labs_completed >= badge.criteria_threshold:
                    should_award = True
            elif badge.criteria_type == BadgeCriteriaType.CHALLENGES_SOLVED:
                if challenges_solved >= badge.criteria_threshold:
                    should_award = True
            elif badge.criteria_type == BadgeCriteriaType.COURSES_COMPLETED:
                if courses_completed >= badge.criteria_threshold:
                    should_award = True
            elif badge.criteria_type == BadgeCriteriaType.PROJECTS_COMPLETED:
                if projects_completed >= badge.criteria_threshold:
                    should_award = True

            if should_award:
                UserBadge.objects.create(user=user, badge=badge)

