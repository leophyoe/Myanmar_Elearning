from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.users.models import UserRole
from apps.billing.models import SubscriptionPlan, UserSubscription
from .models import Subject, Course, Module, Lesson, Enrollment, Quiz, Question, Choice, QuizAttempt
from .views import can_access_course

User = get_user_model()


class MultiDisciplinaryCoursesTests(TestCase):
    def setUp(self):
        self.subjects = Subject.ensure_default_subjects()
        self.plans = SubscriptionPlan.ensure_default_plans()

        self.student = User.objects.create_user(
            username='learner', email='learner@example.com', password='password123',
            role=UserRole.STUDENT
        )
        self.teacher = User.objects.create_user(
            username='instructor', email='instructor@example.com', password='password123',
            role=UserRole.TEACHER
        )

        self.py_subject = Subject.objects.get(slug='python-programming')

        self.std_course = Course.objects.create(
            title='Python Programming for Beginners',
            slug='python-beginners',
            subject=self.py_subject,
            description='Learn Python from scratch.',
            level=Course.Level.BEGINNER,
            is_premium=False,
            price=Decimal('10000'),
            owner=self.teacher,
            is_published=True,
        )

        self.prem_course = Course.objects.create(
            title='Advanced Cyber Security & Penetration Testing',
            slug='advanced-cybersec',
            subject=Subject.objects.get(slug='cyber-security'),
            description='Offensive security and exploit development.',
            level=Course.Level.ADVANCED,
            is_premium=True,
            price=Decimal('50000'),
            owner=self.teacher,
            is_published=True,
        )

    def test_default_subjects_seeded(self):
        self.assertEqual(len(self.subjects), 9)
        expected_slugs = {
            'python-programming', 'computer-science', 'ict', 'igcse-o-level',
            'ged', 'artificial-intelligence', 'cyber-security', 'engineering', 'non-it'
        }
        actual_slugs = set(Subject.objects.values_list('slug', flat=True))
        self.assertTrue(expected_slugs.issubset(actual_slugs))

    def test_course_level_and_premium_flags(self):
        self.assertEqual(self.std_course.level, Course.Level.BEGINNER)
        self.assertFalse(self.std_course.is_premium)
        self.assertEqual(self.prem_course.level, Course.Level.ADVANCED)
        self.assertTrue(self.prem_course.is_premium)

    def test_subscription_access_control(self):
        # 1. Without enrollment or subscription
        self.assertFalse(can_access_course(self.student, self.std_course))

        # 2. Enrolled, but on Standard course without subscription
        Enrollment.objects.create(course=self.std_course, student=self.student, status=Enrollment.Status.ACTIVE)
        self.assertFalse(can_access_course(self.student, self.std_course))

        # 3. Give student Standard subscription (5,000 MMK)
        std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        sub = UserSubscription.objects.create(
            user=self.student, plan=std_plan, billing_cycle='monthly', is_active=True
        )
        self.assertTrue(can_access_course(self.student, self.std_course))

        # Standard subscription should NOT give access to Premium course
        Enrollment.objects.create(course=self.prem_course, student=self.student, status=Enrollment.Status.ACTIVE)
        self.assertFalse(can_access_course(self.student, self.prem_course))

        # 4. Upgrade student to Premium subscription
        sub.is_active = False
        sub.save()
        prem_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.PREMIUM)
        UserSubscription.objects.create(
            user=self.student, plan=prem_plan, billing_cycle='monthly', is_active=True
        )
        self.assertTrue(can_access_course(self.student, self.prem_course))
        self.assertTrue(can_access_course(self.student, self.std_course))

    def test_course_list_filters(self):
        client = Client()
        # Filter by category
        res = client.get(reverse('course-list') + '?category=python-programming')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Python Programming for Beginners')
        self.assertNotContains(res, 'Advanced Cyber Security')

        # Filter by level
        res = client.get(reverse('course-list') + '?level=advanced')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Advanced Cyber Security')
        self.assertNotContains(res, 'Python Programming for Beginners')

    def test_course_list_renders_multi_disciplinary_subjects_and_badges(self):
        client = Client()
        res = client.get(reverse('course-list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Academic Programs')
        self.assertContains(res, 'Python Programming')
        self.assertContains(res, 'All Disciplines')

    def test_landing_page_exposes_multi_disciplinary_tracks(self):
        client = Client()
        res = client.get(reverse('landing-page'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Python Programming')
        self.assertContains(res, 'Artificial Intelligence')
        self.assertContains(res, 'Computer Science')
        self.assertContains(res, 'Cyber Security')

    def test_official_course_cannot_be_edited_by_teacher(self):
        admin = User.objects.create_user(
            username='official_admin', email='official_admin@mel.edu',
            password='AdminPassword2026!', role=UserRole.ADMIN
        )
        teacher = User.objects.create_user(
            username='regular_teacher', email='regular_teacher@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        official_course = Course.objects.create(
            title='Diploma in Cyber Security Official',
            slug='diploma-in-cyber-security-official',
            is_official=True,
            owner=admin,
        )
        self.client.force_login(teacher)
        res = self.client.get(reverse('course-edit', kwargs={'slug': official_course.slug}))
        self.assertEqual(res.status_code, 404)

    def test_teacher_sees_teaching_workspace_in_my_courses(self):
        teacher = User.objects.create_user(
            username='faculty_member', email='faculty@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        self.client.force_login(teacher)
        res = self.client.get(reverse('my-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_teacher_view'])
        self.assertContains(res, 'My Teaching Courses')
        self.assertContains(res, 'Faculty Workspace')

    def test_student_sees_learning_workspace_in_my_courses(self):
        student = User.objects.create_user(
            username='learning_student', email='student@mel.edu',
            password='StudentPassword2026!', role=UserRole.STUDENT
        )
        self.client.force_login(student)
        res = self.client.get(reverse('my-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['is_teacher_view'])
        self.assertContains(res, 'My Enrolled Courses')
        self.assertContains(res, 'Student Workspace')

    def test_navbar_distinguishes_teacher_and_student(self):
        teacher = User.objects.create_user(
            username='nav_teacher', email='nav_teacher@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        student = User.objects.create_user(
            username='nav_student', email='nav_student@mel.edu',
            password='StudentPassword2026!', role=UserRole.STUDENT
        )
        self.client.force_login(teacher)
        res_t = self.client.get(reverse('course-list'))
        self.assertContains(res_t, 'My Teaching')
        self.assertContains(res_t, 'Instructor Hub')
        self.assertNotContains(res_t, 'Content Studio')

        self.client.force_login(student)
        res_s = self.client.get(reverse('course-list'))
        self.assertContains(res_s, 'My Courses')
        self.assertNotContains(res_s, 'My Teaching')
        self.assertNotContains(res_s, 'Instructor Hub')
        self.assertNotContains(res_s, 'Content Studio')

    def test_teacher_does_not_see_platform_subjects_in_manage_home(self):
        teacher = User.objects.create_user(
            username='studio_teacher', email='studio_t@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        self.client.force_login(teacher)
        res = self.client.get(reverse('manage-home'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['subjects']), 0)
        # Verify subject edit links are NOT present
        self.assertNotContains(res, '/courses/manage/subjects/')
        self.assertNotContains(res, '+ Subject')

    def test_admin_sees_platform_subjects_in_manage_home(self):
        admin = User.objects.create_user(
            username='studio_admin', email='studio_a@mel.edu',
            password='AdminPassword2026!', role=UserRole.ADMIN
        )
        self.client.force_login(admin)
        res = self.client.get(reverse('manage-home'))
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.context['subjects']), 0)
        self.assertContains(res, '+ Subject')
        self.assertContains(res, '/courses/manage/subjects/')


class CourseAPITests(TestCase):
    def setUp(self):
        Subject.ensure_default_subjects()
        self.teacher = User.objects.create_user(
            username='api_teacher', email='teacher@example.com', password='password123',
            role=UserRole.TEACHER
        )
        self.py_subject = Subject.objects.get(slug='python-programming')
        self.course = Course.objects.create(
            title='Python Fundamentals',
            slug='python-fundamentals',
            subject=self.py_subject,
            description='Basics of Python.',
            level=Course.Level.BEGINNER,
            price=Decimal('0'),
            owner=self.teacher,
            is_published=True,
        )
        self.module = Module.objects.create(
            course=self.course, order=1, code='MOD-01', title='Getting Started',
            summary='Introduction to Python syntax'
        )
        self.lesson = Lesson.objects.create(
            module=self.module, order=1, title='Installing Python',
            content_markdown='Download python from python.org'
        )
        self.client = Client()

    def test_api_categories(self):
        res = self.client.get(reverse('api-categories'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertGreaterEqual(len(data), 9)

    def test_api_courses_list(self):
        res = self.client.get(reverse('api-courses'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['slug'], 'python-fundamentals')

    def test_api_course_detail(self):
        res = self.client.get(reverse('api-course-detail', kwargs={'slug': 'python-fundamentals'}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['slug'], 'python-fundamentals')
        self.assertEqual(len(data['modules']), 1)
        self.assertEqual(len(data['modules'][0]['lessons']), 1)


class OfficialCourseTeacherDecouplingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='platform_admin', email='admin@mel.edu',
            password='AdminPassword2026!', role=UserRole.ADMIN
        )
        self.teacher = User.objects.create_user(
            username='regular_teacher', email='teacher@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        self.student = User.objects.create_user(
            username='regular_student', email='student@mel.edu',
            password='StudentPassword2026!', role=UserRole.STUDENT
        )
        self.official_course = Course.objects.create(
            title='Diploma in Cyber Security Official',
            slug='diploma-in-cyber-security-official',
            is_official=True,
            owner=self.admin,
            is_published=True,
        )
        self.teacher_course = Course.objects.create(
            title='Python Fundamentals for Beginners',
            slug='python-fundamentals-beginners',
            is_official=False,
            owner=self.teacher,
            is_published=True,
        )

    def test_teacher_my_courses_does_not_list_official_courses(self):
        """Teacher visiting /courses/my/ only sees courses they authored, not platform official curricula."""
        self.client.force_login(self.teacher)
        res = self.client.get(reverse('my-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['is_teacher_view'])

        teaching_courses = res.context['teaching_courses']
        course_ids = [item['course'].id for item in teaching_courses]

        self.assertIn(self.teacher_course.id, course_ids)
        self.assertNotIn(self.official_course.id, course_ids)
        self.assertContains(res, 'Python Fundamentals for Beginners')
        self.assertNotContains(res, 'Diploma in Cyber Security Official')

    def test_teacher_with_no_courses_sees_empty_state_not_official_curricula(self):
        """A new teacher with 0 courses sees the empty state, never official platform courses."""
        new_teacher = User.objects.create_user(
            username='fresh_teacher', email='fresh@mel.edu',
            password='TeacherPassword2026!', role=UserRole.TEACHER
        )
        self.client.force_login(new_teacher)
        res = self.client.get(reverse('my-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['teaching_courses']), 0)
        self.assertContains(res, 'No Personal Teaching Courses Created Yet')
        self.assertNotContains(res, 'Diploma in Cyber Security Official')

    def test_teacher_cannot_manage_official_course_in_content_studio(self):
        """Official platform courses are excluded from regular teacher's Content Studio."""
        self.client.force_login(self.teacher)
        res = self.client.get(reverse('manage-home'))
        self.assertEqual(res.status_code, 200)
        course_ids = [c.id for c in res.context['courses']]
        self.assertIn(self.teacher_course.id, course_ids)
        self.assertNotIn(self.official_course.id, course_ids)
        self.assertNotContains(res, 'Diploma in Cyber Security Official')

    def test_admin_sees_official_courses_in_my_courses_and_content_studio(self):
        """Admins can view and manage official platform courses."""
        self.client.force_login(self.admin)
        res_studio = self.client.get(reverse('manage-home'))
        self.assertIn(self.official_course.id, [c.id for c in res_studio.context['courses']])

        res_my = self.client.get(reverse('my-courses'))
        self.assertIn(self.official_course.id, [item['course'].id for item in res_my.context['teaching_courses']])


class CourseLifecycleAndAssessmentTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='c_teacher', email='ct@mel.edu.mm',
            password='Password123!', role=UserRole.TEACHER
        )
        self.student = User.objects.create_user(
            username='c_student', email='cs@mel.edu.mm',
            password='Password123!', role=UserRole.STUDENT
        )
        self.subject = Subject.objects.create(slug='cs-sub', title='Computer Science')
        self.course = Course.objects.create(
            title='Foundations of Computing',
            slug='foundations-computing',
            subject=self.subject,
            owner=self.teacher,
            status=Course.Status.PUBLISHED,
            membership_tier_required=Course.MembershipTierRequired.STANDARD,
            certificate_fee=15000,
            price=0,
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1: Binary Systems',
            order=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1: Bits and Bytes',
            order=1
        )
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Binary Systems Quiz',
            quiz_type=Quiz.QuizType.QUIZ,
            passing_percentage=50,
        )
        self.q1 = Question.objects.create(quiz=self.quiz, prompt='What is 1 byte?', points=10)
        self.c1 = Choice.objects.create(question=self.q1, text='8 bits', is_correct=True)
        self.c2 = Choice.objects.create(question=self.q1, text='4 bits', is_correct=False)

    def test_course_status_and_tier_attributes(self):
        self.assertEqual(self.course.status, Course.Status.PUBLISHED)
        self.assertEqual(self.course.membership_tier_required, Course.MembershipTierRequired.STANDARD)
        self.assertEqual(self.course.certificate_fee, 15000)

        # Updating status to draft updates is_published
        self.course.status = Course.Status.DRAFT
        self.course.save()
        self.assertFalse(self.course.is_published)

    def test_enrollment_commencement_and_helpers(self):
        enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        self.assertIsNone(enrollment.started_at)
        self.assertEqual(enrollment.completed_lessons_count, 0)
        self.assertEqual(enrollment.completed_modules_count, 0)

        # Student accesses lesson, starting enrollment
        self.client.force_login(self.student)
        resp = self.client.get(reverse('lesson-detail', kwargs={'lesson_id': self.lesson.pk}))
        self.assertEqual(resp.status_code, 200)

        enrollment.refresh_from_db()
        self.assertIsNotNone(enrollment.started_at)

    def test_quiz_attempt_is_recorded(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.student)

        # Student submits quiz
        post_data = {f"question_{self.q1.id}": str(self.c1.id)}
        resp = self.client.post(reverse('quiz-submit', kwargs={'lesson_id': self.lesson.pk}), post_data)
        self.assertEqual(resp.status_code, 302)

        attempt = self.quiz.attempts.filter(student=self.student).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.score_percentage, 100)
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.attempt_number, 1)

