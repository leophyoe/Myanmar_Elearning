"""
Integration test suite for THUTA Phase P1.3 Achievement Pipeline:
- Certificate generation on course completion & idempotency
- Public certificate verification (valid, revoked, invalid lookup)
- Badge award criteria and automatic triggers
- Public portfolio rendering with credentials, badges, projects & privacy controls
"""
import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.users.models import User, UserRole, StudentProfile
from apps.courses.models import (
    Course, Module, Lesson, LessonType, Enrollment, UserProgress
)
from apps.courses.services.completion import sync_course_completion
from apps.certificates.models import Certificate
from apps.certificates.services import issue_certificate_for_enrollment
from apps.scoring.models import Badge, UserBadge, BadgeCriteriaType
from apps.scoring.services import BadgeAwardService
from apps.portfolio.models import PortfolioProject, Skill


class AchievementPipelineP13Tests(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.teacher = User.objects.create_user(
            username='p13_teacher',
            email='teacher@thuta.edu.mm',
            password='TestPassword123!',
            role=UserRole.TEACHER,
        )

        self.student = User.objects.create_user(
            username='p13_student',
            first_name='Aung',
            last_name='Kyaw',
            email='student@thuta.edu.mm',
            password='TestPassword123!',
            role=UserRole.STUDENT,
        )
        self.student_profile = self.student.student_profile
        self.student_profile.points = 100
        self.student_profile.save()

        # Course
        self.course = Course.objects.create(
            title='Practical Network Defense',
            slug='practical-network-defense',
            owner=self.teacher,
            access_type=Course.AccessType.FREE,
            is_published=True,
            certificate_eligible=True,
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Core Networking Defense',
            order=1,
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module,
            title='Firewall Configurations',
            order=1,
            lesson_type=LessonType.TEXT,
        )

        # Enrollment
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=Enrollment.Status.ACTIVE,
        )

    # -------------------------------------------------------------------------
    # 1. CERTIFICATE GENERATION & IDEMPOTENCY
    # -------------------------------------------------------------------------
    def test_01_course_completion_issues_certificate(self):
        """Reaching 100% course completion automatically issues a valid certificate."""
        # Mark lesson completed
        UserProgress.objects.create(
            user=self.student,
            course=self.course,
            module=self.module,
            lesson=self.lesson1,
            is_completed=True,
            completed_at=timezone.now(),
        )

        # Sync course completion
        enrollment = sync_course_completion(self.student, self.course)
        self.assertEqual(enrollment.status, Enrollment.Status.COMPLETED)
        self.assertEqual(enrollment.progress_pct, 100)

        # Check Certificate generated
        cert = Certificate.objects.filter(student=self.student, course=self.course).first()
        self.assertIsNotNone(cert)
        self.assertEqual(cert.student_name, 'Aung Kyaw')
        self.assertEqual(cert.program_title, 'Practical Network Defense')
        self.assertFalse(cert.is_revoked)
        self.assertTrue(cert.certificate_code.startswith('MEL-CERT-2026-'))

        # Test Idempotency
        second_cert = issue_certificate_for_enrollment(enrollment)
        self.assertEqual(cert.id, second_cert.id)
        self.assertEqual(Certificate.objects.filter(student=self.student, course=self.course).count(), 1)

    # -------------------------------------------------------------------------
    # 2. CERTIFICATE VERIFICATION & LOOKUP SECURITY
    # -------------------------------------------------------------------------
    def test_02_public_certificate_verification_valid_and_revoked(self):
        """Public verification correctly displays valid records and reflects revocation."""
        cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            student_name='Aung Kyaw',
            program_title='Practical Network Defense',
            certificate_code='MEL-CERT-2026-TEST01',
            grade='Distinction',
        )

        # 1. Valid certificate verification
        verify_url = reverse('certificate-verify', kwargs={'cert_id': cert.id})
        resp = self.client.get(verify_url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'OFFICIALLY VERIFIED CREDENTIAL')
        self.assertContains(resp, 'Aung Kyaw')
        self.assertContains(resp, 'Practical Network Defense')
        self.assertContains(resp, 'MEL-CERT-2026-TEST01')
        self.assertContains(resp, 'Distinction')
        # Private information must NOT be present
        self.assertNotContains(resp, self.student.email)

        # 2. Revoked certificate
        cert.revoke(reason='Integrity violation')
        resp_revoked = self.client.get(verify_url, HTTP_HOST='localhost')
        self.assertEqual(resp_revoked.status_code, 200)
        self.assertContains(resp_revoked, 'Credential revoked')
        self.assertContains(resp_revoked, 'REVOKED')

        # 3. QR code endpoint
        qr_url = reverse('certificate-qr', kwargs={'cert_id': cert.id})
        qr_resp = self.client.get(qr_url, HTTP_HOST='localhost')
        self.assertEqual(qr_resp.status_code, 200)
        self.assertEqual(qr_resp['Content-Type'], 'image/png')

    def test_03_certificate_lookup_page_and_invalid_serial(self):
        """Public lookup correctly routes valid codes and safely handles unknown codes."""
        cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            student_name='Aung Kyaw',
            program_title='Practical Network Defense',
            certificate_code='MEL-CERT-2026-FIND01',
        )

        lookup_url = reverse('certificate-lookup')

        # Valid lookup redirects to verification
        resp_valid = self.client.get(f'{lookup_url}?code=MEL-CERT-2026-FIND01', HTTP_HOST='localhost')
        self.assertRedirects(resp_valid, reverse('certificate-verify', kwargs={'cert_id': cert.id}))

        # Invalid lookup shows friendly error without leaking data
        resp_invalid = self.client.get(f'{lookup_url}?code=UNKNOWN-SERIAL-999', HTTP_HOST='localhost')
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertContains(resp_invalid, 'No certificate matches')
        self.assertContains(resp_invalid, 'UNKNOWN-SERIAL-999')

    # -------------------------------------------------------------------------
    # 3. BADGE AWARD CRITERIA & TRIGGERS
    # -------------------------------------------------------------------------
    def test_04_badge_awarded_on_course_completion_and_points(self):
        """Badges are automatically awarded when criteria thresholds are met."""
        # Course completion badge
        course_badge = Badge.objects.create(
            name='First Step Scholar',
            slug='first-step-scholar',
            description='Completed first course on THUTA.',
            criteria_type=BadgeCriteriaType.COURSES_COMPLETED,
            criteria_threshold=1,
        )

        # Points badge
        points_badge = Badge.objects.create(
            name='Centurion',
            slug='centurion',
            description='Earned 100 platform points.',
            criteria_type=BadgeCriteriaType.POINTS_THRESHOLD,
            criteria_threshold=100,
        )

        # Initial check
        BadgeAwardService.evaluate_user_achievements(self.student)
        self.assertTrue(UserBadge.objects.filter(user=self.student, badge=points_badge).exists())
        self.assertFalse(UserBadge.objects.filter(user=self.student, badge=course_badge).exists())

        # Complete course
        self.enrollment.status = Enrollment.Status.COMPLETED
        self.enrollment.save()

        BadgeAwardService.evaluate_user_achievements(self.student)
        self.assertTrue(UserBadge.objects.filter(user=self.student, badge=course_badge).exists())

    # -------------------------------------------------------------------------
    # 4. PORTFOLIO RENDERING & PRIVACY CONTROLS
    # -------------------------------------------------------------------------
    def test_05_portfolio_rendering_and_privacy_controls(self):
        """Portfolio renders public credentials and badges, while honoring unpublished privacy."""
        # Award badge
        badge = Badge.objects.create(
            name='Cyber Defender',
            slug='cyber-defender',
            description='Master of defensive architecture.',
            criteria_type=BadgeCriteriaType.COURSES_COMPLETED,
            criteria_threshold=1,
        )
        UserBadge.objects.create(user=self.student, badge=badge)

        # Valid certificate
        cert = Certificate.objects.create(
            student=self.student,
            course=self.course,
            student_name='Aung Kyaw',
            program_title='Practical Network Defense',
            certificate_code='MEL-CERT-2026-PORT01',
        )

        # Projects: one published, one draft/unpublished
        pub_proj = PortfolioProject.objects.create(
            owner=self.student,
            title='Public Network Intrusion Sandbox',
            category=PortfolioProject.Category.SECURITY,
            is_published=True,
        )
        draft_proj = PortfolioProject.objects.create(
            owner=self.student,
            title='Private Proprietary Exploit',
            category=PortfolioProject.Category.SECURITY,
            is_published=False,
        )

        # Public guest views student portfolio
        portfolio_url = reverse('portfolio-detail', kwargs={'username': self.student.username})
        resp = self.client.get(portfolio_url, HTTP_HOST='localhost')
        self.assertEqual(resp.status_code, 200)

        # Verify badges section (assertContains automatically checks HTML-escaped characters)
        self.assertContains(resp, 'Badges & Achievements')
        self.assertContains(resp, 'Cyber Defender')

        # Verify credential in list
        self.assertContains(resp, 'Practical Network Defense')
        self.assertContains(resp, 'MEL-CERT-2026-PORT01')

        # Verify published project is visible, draft project is hidden
        self.assertContains(resp, 'Public Network Intrusion Sandbox')
        self.assertNotContains(resp, 'Private Proprietary Exploit')

        # Owner views their own portfolio
        self.client.login(username='p13_student', password='TestPassword123!')
        owner_resp = self.client.get(portfolio_url, HTTP_HOST='localhost')
        self.assertEqual(owner_resp.status_code, 200)
        self.assertContains(owner_resp, 'Public Network Intrusion Sandbox')
        self.assertContains(owner_resp, 'Edit portfolio')
