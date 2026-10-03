from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.authtoken.models import Token

from apps.users.models import UserRole, ActiveMode, Notification, PushDevice, InstructorApplication, TeacherProfile
from apps.courses.models import Course, Module, Lesson, Subject, Quiz, Question, Choice, Enrollment, UserProgress
from apps.billing.models import SubscriptionPlan, UserSubscription
from apps.partner.models import Institution, PartnerStudent, PartnerMembership
from apps.certificates.models import Certificate
from apps.labs.models import LabTemplate, Lab, LabInstance, InstanceStatus

User = get_user_model()


class APITestBase(APITestCase):
    def setUp(self):
        # 1. Seed Disciplines
        Subject.ensure_default_subjects()
        self.subject = Subject.objects.first()

        # 2. Seed Subscription Plans
        SubscriptionPlan.ensure_default_plans()
        self.starter_plan = SubscriptionPlan.objects.get(plan_type='starter')
        self.std_plan = SubscriptionPlan.objects.get(plan_type='standard')
        self.prem_plan = SubscriptionPlan.objects.get(plan_type='premium')

        # 3. Create Users
        self.student = User.objects.create_user(
            username='api_student',
            email='api_student@mel.edu.mm',
            password='Password123!',
            first_name='Aung',
            last_name='Kyaw',
            role=UserRole.STUDENT,
            active_mode=ActiveMode.STUDENT,
        )
        self.student_token, _ = Token.objects.get_or_create(user=self.student)

        self.teacher = User.objects.create_user(
            username='api_teacher',
            email='api_teacher@mel.edu.mm',
            password='Password123!',
            first_name='Daw',
            last_name='Mya',
            role=UserRole.TEACHER,
            active_mode=ActiveMode.INSTRUCTOR,
        )
        self.teacher.add_role('instructor')
        self.teacher_token, _ = Token.objects.get_or_create(user=self.teacher)

        self.admin_user = User.objects.create_superuser(
            username='api_admin',
            email='api_admin@mel.edu.mm',
            password='Password123!',
            first_name='System',
            last_name='Admin',
            role=UserRole.ADMIN,
        )
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin_user)

        # 4. Partner Institution and Partner User
        self.institution = Institution.objects.create(
            name="Yangon Tech Institute",
            slug="yangon-tech-api",
            institution_type=Institution.InstitutionType.UNIVERSITY,
            email="partner@yangontech.edu.mm",
        )
        self.partner_user = User.objects.create_user(
            username='api_partner',
            email='api_partner@mel.edu.mm',
            password='Password123!',
            role=UserRole.PARTNER,
        )
        self.partner_user.add_role('partner')
        self.partner_token, _ = Token.objects.get_or_create(user=self.partner_user)
        PartnerMembership.objects.create(
            institution=self.institution,
            user=self.partner_user,
            role=PartnerMembership.Role.ADMIN,
            status=PartnerMembership.Status.ACTIVE,
        )

        # 5. Course with Module & Lessons
        self.free_course = Course.objects.create(
            title="Introduction to Computer Science",
            slug="intro-cs-api",
            subject=self.subject,
            owner=self.teacher,
            access_type=Course.AccessType.FREE,
            price=Decimal('0.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
            level=Course.Level.BEGINNER,
            duration_months=3,
        )
        self.module_free = Module.objects.create(
            course=self.free_course,
            title="Module 1: Foundations",
            order=1,
            code="MOD-01",
            summary="Foundations of Computer Science",
        )
        self.preview_lesson = Lesson.objects.create(
            module=self.module_free,
            title="Lesson 1: Course Overview",
            order=1,
            content_markdown="Welcome to the computer science journey!",
            estimated_minutes=15,
        )
        self.locked_lesson = Lesson.objects.create(
            module=self.module_free,
            title="Lesson 2: Binary Architecture",
            order=2,
            content_markdown="Confidential proprietary lecture notes on CPU registers.",
            estimated_minutes=45,
        )

        # 6. Paid Course
        self.paid_course = Course.objects.create(
            title="Advanced Cyber Defense",
            slug="adv-cyber-api",
            subject=self.subject,
            owner=self.teacher,
            access_type=Course.AccessType.PREMIUM,
            price=Decimal('50000.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
            level=Course.Level.ADVANCED,
            duration_months=6,
        )


class AuthenticationAPITests(APITestBase):
    def test_login_with_email(self):
        url = reverse('api-login')
        resp = self.client.post(url, {
            'identifier': 'api_student@mel.edu.mm',
            'password': 'Password123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('auth', resp.data)
        self.assertEqual(resp.data['auth']['token'], self.student_token.key)
        self.assertEqual(resp.data['auth']['username'], 'api_student')
        self.assertTrue(resp.data['auth']['account_id'].startswith('MEL-'))

    def test_login_with_mel_account_id(self):
        url = reverse('api-login')
        resp = self.client.post(url, {
            'identifier': self.student.account_id,
            'password': 'Password123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['auth']['token'], self.student_token.key)

    def test_login_with_username(self):
        url = reverse('api-login')
        resp = self.client.post(url, {
            'identifier': 'api_student',
            'password': 'Password123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_login_invalid_credentials(self):
        url = reverse('api-login')
        resp = self.client.post(url, {
            'identifier': 'api_student',
            'password': 'WrongPassword!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_creates_account_with_mel_id(self):
        url = reverse('api-register')
        resp = self.client.post(url, {
            'username': 'new_mobile_student',
            'email': 'new_mobile@mel.edu.mm',
            'password': 'ComplexPassword2026!',
            'first_name': 'Kyaw',
            'last_name': 'Zin',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', resp.data['auth'])
        self.assertTrue(resp.data['auth']['account_id'].startswith('MEL-'))
        self.assertEqual(resp.data['auth']['role'], 'student')

    def test_logout_revokes_token(self):
        url = reverse('api-logout')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Verify token deleted
        self.assertFalse(Token.objects.filter(user=self.student).exists())

    def test_push_device_registration(self):
        url = reverse('api-device-register')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.student_token.key}')
        resp = self.client.post(url, {
            'token': 'fcm_token_sample_android_123',
            'platform': 'android',
            'device_name': 'Pixel 8 Pro',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(PushDevice.objects.filter(token='fcm_token_sample_android_123', user=self.student).exists())


class UserProfileAndRBACAPITests(APITestBase):
    def test_get_current_user_profile(self):
        url = reverse('api-users-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['username'], 'api_student')
        self.assertEqual(resp.data['account_id'], self.student.account_id)
        self.assertIn('student', resp.data['roles'])
        self.assertIn('membership', resp.data)

    def test_update_profile(self):
        url = reverse('api-users-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.patch(url, {
            'first_name': 'Ko Aung',
            'phone_number': '+95912345678',
            'bio': 'Passionate about cyber security and Python.',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Ko Aung')
        self.assertEqual(self.student.phone_number, '+95912345678')

    def test_mode_switch_unauthorized_student_denied(self):
        url = reverse('api-users-switch-mode')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {'mode': 'instructor'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('mode', resp.data)

    def test_mode_switch_teacher_allowed(self):
        url = reverse('api-users-switch-mode')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.teacher_token.key}')
        # Switch to student mode
        resp = self.client.post(url, {'mode': 'student'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.active_mode, 'student')

        # Switch back to instructor mode
        resp = self.client.post(url, {'mode': 'instructor'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.active_mode, 'instructor')

    def test_change_password(self):
        url = reverse('api-users-change-password')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {
            'old_password': 'Password123!',
            'new_password': 'BrandNewPassword2026!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password('BrandNewPassword2026!'))


class CoursesAndCurriculumAPITests(APITestBase):
    def test_list_published_courses(self):
        url = reverse('api-courses-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 2)

    def test_filter_courses_by_access_type(self):
        url = reverse('api-courses-list')
        resp = self.client.get(url, {'access_type': 'free'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data['results']:
            self.assertEqual(item['access_type'], 'free')

    def test_course_detail_unauthenticated(self):
        url = reverse('api-courses-detail', kwargs={'slug': self.free_course.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], "Introduction to Computer Science")
        self.assertFalse(resp.data['is_enrolled'])

    def test_curriculum_endpoint(self):
        url = reverse('api-courses-curriculum', kwargs={'slug': self.free_course.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['modules']), 1)
        self.assertEqual(len(resp.data['modules'][0]['lessons']), 2)

    def test_lesson_detail_zero_trust_locked_for_unenrolled_student(self):
        url = reverse('api-courses-lesson-detail', kwargs={
            'slug': self.free_course.slug,
            'lesson_id': self.locked_lesson.id
        })
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['is_accessible'])
        self.assertIn("locked", resp.data['content'])

    def test_lesson_detail_accessible_for_preview(self):
        url = reverse('api-courses-lesson-detail', kwargs={
            'slug': self.free_course.slug,
            'lesson_id': self.preview_lesson.id
        })
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_accessible'])
        self.assertIn("computer science journey", resp.data['content'])

    def test_course_pricing_calculation_endpoint(self):
        url = reverse('api-courses-pricing', kwargs={'slug': self.paid_course.slug})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data['final_price']), Decimal('50000.00'))
        self.assertFalse(resp.data['is_free'])


class EnrollmentAPITests(APITestBase):
    def test_enroll_free_course_success(self):
        url = reverse('api-enrollments-enroll')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {'course_slug': self.free_course.slug})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=self.free_course).exists())

    def test_enroll_paid_course_without_payment_rejected(self):
        url = reverse('api-enrollments-enroll')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {'course_slug': self.paid_course.slug})
        self.assertEqual(resp.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertEqual(resp.data['error'], 'payment_required')

    def test_my_enrollments_list(self):
        Enrollment.objects.create(student=self.student, course=self.free_course, status=Enrollment.Status.ACTIVE)
        url = reverse('api-enrollments-my')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['course']['slug'], self.free_course.slug)


class LearningProgressAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.enrollment = Enrollment.objects.create(
            student=self.student, course=self.free_course, status=Enrollment.Status.ACTIVE
        )

    def test_course_progress_overview(self):
        url = reverse('api-progress-course', kwargs={'slug': self.free_course.slug})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total_lessons'], 2)
        self.assertEqual(resp.data['completed_lessons'], 0)
        self.assertEqual(resp.data['progress_percentage'], 0)

    def test_complete_lesson_advances_progress(self):
        url = reverse('api-progress-complete-lesson')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {'lesson_id': self.preview_lesson.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['progress_percentage'], 50)
        self.assertTrue(UserProgress.objects.filter(user=self.student, lesson=self.preview_lesson, is_completed=True).exists())

    def test_continue_learning_banner(self):
        url = reverse('api-progress-continue')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['has_active_course'])
        self.assertEqual(resp.data['course_slug'], self.free_course.slug)
        self.assertEqual(resp.data['next_lesson_slug'], self.preview_lesson.slug)


class AssessmentsAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        Enrollment.objects.create(student=self.student, course=self.free_course, status=Enrollment.Status.ACTIVE)
        self.quiz = Quiz.objects.create(
            course=self.free_course,
            title="Computer Architecture Quiz",
            quiz_type=Quiz.AssessmentType.QUIZ,
            time_limit_minutes=30,
            passing_percentage=70,
            status=Quiz.Status.PUBLISHED,
        )
        self.q1 = Question.objects.create(
            quiz=self.quiz,
            prompt="What does CPU stand for?",
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=10,
            order=1,
        )
        self.c1 = Choice.objects.create(question=self.q1, text="Central Processing Unit", is_correct=True)
        self.c2 = Choice.objects.create(question=self.q1, text="Computer Power Unit", is_correct=False)

    def test_assessment_start_sanitized_questions(self):
        url = reverse('api-assessments-start', kwargs={'pk': self.quiz.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['questions']), 1)
        # Verify correct answer is NOT leaked
        choices = resp.data['questions'][0]['choices']
        self.assertNotIn('is_correct', choices[0])

    def test_assessment_submit_and_auto_grading(self):
        url = reverse('api-assessments-submit', kwargs={'pk': self.quiz.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {
            'answers': {str(self.q1.id): str(self.c1.id)},
            'time_taken_seconds': 120,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data['score']), Decimal('100.00'))
        self.assertTrue(resp.data['passed'])


class CertificatesAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.cert = Certificate.objects.create(
            student=self.student,
            course=self.free_course,
            certificate_code="MEL-CERT-2026-TEST1234",
            student_name="Aung Kyaw",
            program_title="Introduction to Computer Science",
            grade="Distinction",
        )

    def test_my_certificates_list(self):
        url = reverse('api-certificates-my')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['certificate_code'], "MEL-CERT-2026-TEST1234")

    def test_public_certificate_verification(self):
        url = reverse('api-certificates-verify', kwargs={'code': "MEL-CERT-2026-TEST1234"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_valid'])
        self.assertEqual(resp.data['recipient_name'], "Aung Kyaw")


class MembershipAPITests(APITestBase):
    def test_list_subscription_plans(self):
        url = reverse('api-membership-plans')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 3)

    def test_subscribe_starter_instant_activation(self):
        url = reverse('api-membership-subscribe')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {
            'plan_type': 'starter',
            'billing_cycle': 'monthly',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserSubscription.objects.filter(user=self.student, plan__plan_type='starter', is_active=True).exists())


class InstructorAPITests(APITestBase):
    def test_instructor_stats_denied_for_regular_student(self):
        url = reverse('api-instructor-stats')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_stats_allowed_for_teacher(self):
        url = reverse('api-instructor-stats')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.teacher_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_courses', resp.data)

    def test_instructor_application_submission(self):
        url = reverse('api-instructor-apply')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url, {
            'department': 'Software Engineering',
            'title': 'Senior Developer',
            'qualifications': 'B.C.Sc, 8 years industry experience.',
            'teaching_experience': 'Mentored 20+ junior engineers.',
            'target_subjects': 'Python, Django, FastAPI',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(InstructorApplication.objects.filter(user=self.student, status='pending').exists())


class PartnerAPITests(APITestBase):
    def test_partner_portal_denied_for_student(self):
        url = reverse('api-partner-organization')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_partner_portal_allowed_for_partner(self):
        url = reverse('api-partner-organization')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.partner_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], "Yangon Tech Institute")

    def test_partner_invite_student_by_mel_id(self):
        url = reverse('api-partner-invite-student')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.partner_token.key}')
        resp = self.client.post(url, {
            'mel_account_id': self.student.account_id,
            'external_student_id': 'YTI-2026-001',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PartnerStudent.objects.filter(institution=self.institution, student=self.student).exists())


class NotificationsAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.notif = Notification.objects.create(
            user=self.student,
            title="Course Enrollment Confirmed",
            message="You have been enrolled in Introduction to Computer Science.",
            level=Notification.Level.SUCCESS,
        )

    def test_list_notifications_and_unread_count(self):
        url = reverse('api-notifications-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

        count_url = reverse('api-notifications-unread-count')
        resp_count = self.client.get(count_url)
        self.assertEqual(resp_count.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_count.data['unread_count'], 1)

    def test_mark_notification_as_read(self):
        url = reverse('api-notifications-mark-read', kwargs={'pk': self.notif.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)


class LabsAPITests(APITestBase):
    def setUp(self):
        super().setUp()
        self.template = LabTemplate.objects.create(
            name="Linux Fundamentals Template",
            slug="linux-fund-tmpl-api",
            category="linux",
            description="Basic Linux sandbox.",
        )
        self.lab = Lab.objects.create(
            template=self.template,
            title="Linux CLI Basics",
            slug="linux-cli-basics-api",
            difficulty="easy",
            points=50,
        )

    def test_list_labs(self):
        url = reverse('api-labs-list')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_start_and_stop_lab_instance(self):
        start_url = reverse('api-labs-start', kwargs={'slug': self.lab.slug})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.student_token.key}')
        resp_start = self.client.post(start_url)
        self.assertEqual(resp_start.status_code, status.HTTP_201_CREATED)
        instance_id = resp_start.data['instance']['id']

        stop_url = reverse('api-labs-stop', kwargs={'pk': instance_id})
        resp_stop = self.client.post(stop_url)
        self.assertEqual(resp_stop.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_stop.data['instance']['status'], InstanceStatus.STOPPED)
