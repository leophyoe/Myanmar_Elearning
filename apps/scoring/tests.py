from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Enrollment
from apps.projects.models import FinalProject, ProjectSubmission
from .models import Badge, UserBadge, BadgeCriteriaType
from .services import BadgeAwardService

User = get_user_model()


class ScoringAndBadgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='badge_student', email='badge@mel.edu.mm', password='password123'
        )
        self.profile = self.user.student_profile
        self.profile.points = 150
        self.profile.save()

        self.points_badge = Badge.objects.create(
            name="Centurion",
            slug="centurion",
            description="Reached 100 points.",
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_threshold=100,
        )
        self.course_badge = Badge.objects.create(
            name="Graduate Explorer",
            slug="graduate-explorer",
            description="Completed 1 course.",
            criteria_type=BadgeCriteriaType.COURSES_COMPLETED,
            criteria_threshold=1,
        )
        self.project_badge = Badge.objects.create(
            name="Capstone Master",
            slug="capstone-master",
            description="Completed capstone project.",
            criteria_type=BadgeCriteriaType.PROJECTS_COMPLETED,
            criteria_threshold=1,
        )

    def test_points_badge_awarded(self):
        BadgeAwardService.evaluate_user_achievements(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.points_badge).exists())
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge=self.course_badge).exists())

    def test_course_completion_badge_awarded(self):
        course = Course.objects.create(title="Python Core", slug="python-core", duration_months=2)
        Enrollment.objects.create(
            student=self.user,
            course=course,
            status=Enrollment.Status.COMPLETED,
            progress_pct=100,
        )
        BadgeAwardService.evaluate_user_achievements(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.course_badge).exists())

    def test_project_completion_badge_awarded(self):
        proj = FinalProject.objects.create(title="Capstone Alpha", slug="capstone-alpha", description="Desc")
        ProjectSubmission.objects.create(
            project=proj,
            student=self.user,
            status=ProjectSubmission.Status.COMPLETED,
            proposal_text="Completed capstone proposal.",
        )
        BadgeAwardService.evaluate_user_achievements(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.project_badge).exists())
