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

    def test_partner_affiliated_course_access(self):
        from apps.partner.models import Institution, PartnerStudent
        institution = Institution.objects.create(
            name='Partner University',
            slug='partner-uni',
            email='partner@uni.edu.mm'
        )
        partner_course = Course.objects.create(
            title='Enterprise Cloud Architecture',
            slug='enterprise-cloud',
            subject=self.py_subject,
            description='Enterprise cloud and systems course.',
            level=Course.Level.INTERMEDIATE,
            price=Decimal('50000'),
            owner=self.teacher,
            partner_institution=institution,
            is_published=True,
        )

        # Student enrolled, but without subscription or direct payment or partner affiliation
        Enrollment.objects.create(course=partner_course, student=self.student, status=Enrollment.Status.ACTIVE)
        self.assertFalse(can_access_course(self.student, partner_course))

        # Affiliate student with partner institution
        PartnerStudent.objects.create(
            institution=institution,
            student=self.student,
            status=PartnerStudent.Status.ACTIVE
        )
        self.assertTrue(can_access_course(self.student, partner_course))

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


class Phase2CourseAccessAndPublishingTests(TestCase):
    """
    Comprehensive verification of Phase 2 objectives:
    - Course ownership & status lifecycle (DRAFT -> PENDING_REVIEW -> APPROVED -> PUBLISHED / REJECTED)
    - Instructor permissions (create, edit own, blocked from other instructors' courses, submit for review)
    - Admin review workflow (approve, reject with notes, request changes, publish)
    - Visibility rules (published public vs draft private)
    - Membership access matrix (Free, Starter, Standard, Premium, Partner-Only)
    - Reusable CourseAccessService
    - Enrollment integration & source tracking
    """

    def setUp(self):
        self.client = Client()
        Subject.ensure_default_subjects()
        self.plans = SubscriptionPlan.ensure_default_plans()

        self.admin = User.objects.create_superuser(
            username='admin_user', email='admin@example.com', password='password123',
            role=UserRole.ADMIN
        )
        self.instructor_1 = User.objects.create_user(
            username='instructor_one', email='inst1@example.com', password='password123',
            role=UserRole.TEACHER
        )
        self.instructor_2 = User.objects.create_user(
            username='instructor_two', email='inst2@example.com', password='password123',
            role=UserRole.TEACHER
        )
        self.student = User.objects.create_user(
            username='regular_student', email='student@example.com', password='password123',
            role=UserRole.STUDENT
        )
        self.partner_user = User.objects.create_user(
            username='partner_admin', email='partner@example.com', password='password123',
            role=UserRole.PARTNER
        )

        from apps.partner.models import Institution, PartnerMembership
        self.institution = Institution.objects.create(
            name='Yangon Technological University',
            slug='ytu',
            contact_person=self.partner_user,
            is_verified=True,
        )
        PartnerMembership.objects.create(
            institution=self.institution,
            user=self.partner_user,
            role=PartnerMembership.Role.ADMIN,
            status=PartnerMembership.Status.ACTIVE,
        )

    def test_instructor_creates_course_saved_in_draft(self):
        """1. Instructor creates course — starts in DRAFT, non-official, unapproved."""
        self.client.force_login(self.instructor_1)
        post_data = {
            'title': 'Applied Cryptography',
            'slug': 'applied-cryptography',
            'subject': Subject.objects.first().id,
            'description': 'Modern applied cryptography course.',
            'level': Course.Level.INTERMEDIATE,
            'language': Course.Language.BURMESE,
            'duration_months': 4,
            'access_type': Course.AccessType.STANDARD,
            'membership_tier_required': Course.MembershipTierRequired.STANDARD,
            'price': 0,
            'billing_period': Course.BillingPeriod.ONE_TIME,
        }
        resp = self.client.post(reverse('course-create'), post_data)
        self.assertEqual(resp.status_code, 302)

        course = Course.objects.get(slug='applied-cryptography')
        self.assertEqual(course.owner, self.instructor_1)
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)
        self.assertFalse(course.is_official)
        self.assertEqual(course.owner_type, Course.OwnerType.INSTRUCTOR)

    def test_instructor_edits_own_course(self):
        """2. Instructor can edit their own draft course."""
        course = Course.objects.create(
            title='Web Development Basics',
            slug='web-dev-basics',
            owner=self.instructor_1,
            owner_type=Course.OwnerType.INSTRUCTOR,
            status=Course.Status.DRAFT,
            is_published=False,
            is_official=False,
            price=0,
        )
        self.client.force_login(self.instructor_1)
        resp = self.client.post(reverse('course-edit', kwargs={'slug': course.slug}), {
            'title': 'Web Development Masterclass',
            'slug': 'web-dev-basics',
            'description': 'Updated curriculum description.',
            'level': Course.Level.BEGINNER,
            'language': Course.Language.BURMESE,
            'duration_months': 3,
            'access_type': Course.AccessType.FREE,
            'membership_tier_required': Course.MembershipTierRequired.STARTER,
            'price': 0,
            'billing_period': Course.BillingPeriod.ONE_TIME,
        })
        self.assertEqual(resp.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.title, 'Web Development Masterclass')

    def test_instructor_cannot_edit_another_instructor_course(self):
        """3. Instructor cannot edit or access another instructor's course."""
        course = Course.objects.create(
            title='Instructor One Secret Course',
            slug='inst-1-secret',
            owner=self.instructor_1,
            owner_type=Course.OwnerType.INSTRUCTOR,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )
        self.client.force_login(self.instructor_2)
        # Attempting to load edit form returns 404 because queryset is filtered to owner
        resp = self.client.get(reverse('course-edit', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 404)

        resp = self.client.post(reverse('course-edit', kwargs={'slug': course.slug}), {
            'title': 'Hacked Title',
        })
        self.assertEqual(resp.status_code, 404)
        course.refresh_from_db()
        self.assertEqual(course.title, 'Instructor One Secret Course')

    def test_instructor_submits_course_for_review(self):
        """4. Instructor submits course: requires curriculum (module + lesson), moves to PENDING_REVIEW."""
        from apps.courses.services.access import can_submit_for_review

        course = Course.objects.create(
            title='Digital Forensics',
            slug='digital-forensics',
            owner=self.instructor_1,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )

        # 4a. Cannot submit without at least one module and lesson
        can_submit, reason = can_submit_for_review(self.instructor_1, course)
        self.assertFalse(can_submit)
        self.assertIn("module", reason.lower())

        module = Module.objects.create(course=course, code='DF-01', title='Evidence Handling', order=1)
        can_submit, reason = can_submit_for_review(self.instructor_1, course)
        self.assertFalse(can_submit)
        self.assertIn("lesson", reason.lower())

        Lesson.objects.create(module=module, order=1, title='Chain of Custody', content_markdown='Notes...')
        can_submit, reason = can_submit_for_review(self.instructor_1, course)
        self.assertTrue(can_submit)

        # 4b. Perform submit POST
        self.client.force_login(self.instructor_1)
        resp = self.client.post(reverse('course-submit-review', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PENDING_REVIEW)
        self.assertFalse(course.is_published)

    def test_admin_approves_course(self):
        """5. Admin approves and publishes course."""
        course = Course.objects.create(
            title='Malware Analysis',
            slug='malware-analysis',
            owner=self.instructor_1,
            status=Course.Status.PENDING_REVIEW,
            is_published=False,
            price=0,
        )
        module = Module.objects.create(course=course, code='MAL-01', title='PE Headers', order=1)
        Lesson.objects.create(module=module, order=1, title='Static Analysis', content_markdown='Body')

        self.client.force_login(self.admin)
        resp = self.client.post(reverse('course-review-action', kwargs={'slug': course.slug}), {
            'action': 'publish',
            'admin_review_notes': 'Curriculum looks well-structured and complete.',
        })
        self.assertEqual(resp.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.is_published)
        self.assertEqual(course.reviewed_by, self.admin)
        self.assertIsNotNone(course.reviewed_at)

    def test_admin_rejects_course_with_notes(self):
        """6. Admin rejects course with mandatory feedback notes."""
        course = Course.objects.create(
            title='Incomplete Course',
            slug='incomplete-course',
            owner=self.instructor_1,
            status=Course.Status.PENDING_REVIEW,
            is_published=False,
            price=0,
        )
        module = Module.objects.create(course=course, code='INC-01', title='Draft Module', order=1)
        Lesson.objects.create(module=module, order=1, title='Empty Lesson', content_markdown='...')

        self.client.force_login(self.admin)
        # Attempt reject without notes should fail validation
        resp = self.client.post(reverse('course-review-action', kwargs={'slug': course.slug}), {
            'action': 'reject',
            'admin_review_notes': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp.context['form'], 'admin_review_notes', 'Review notes are required when rejecting or requesting changes.')

        # Submit reject with notes
        resp = self.client.post(reverse('course-review-action', kwargs={'slug': course.slug}), {
            'action': 'reject',
            'admin_review_notes': 'Please add practical exercises and expand lecture contents.',
        })
        self.assertEqual(resp.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.REJECTED)
        self.assertFalse(course.is_published)
        self.assertEqual(course.admin_review_notes, 'Please add practical exercises and expand lecture contents.')

    def test_published_course_is_visible(self):
        """7. Published course is visible in catalog and detail page."""
        course = Course.objects.create(
            title='Public Network Security',
            slug='public-netsec',
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        # Anonymous client can view
        resp = self.client.get(reverse('course-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Public Network Security')

        resp = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Public Network Security')

    def test_draft_course_is_not_publicly_visible(self):
        """8. Draft course is not publicly visible to regular users or anonymous."""
        course = Course.objects.create(
            title='Top Secret Draft',
            slug='top-secret-draft',
            owner=self.instructor_1,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )
        # Anonymous: catalog does not show it
        resp = self.client.get(reverse('course-list'))
        self.assertNotContains(resp, 'Top Secret Draft')

        # Anonymous detail view returns 404
        resp = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 404)

        # Another student detail view returns 404
        self.client.force_login(self.student)
        resp = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 404)

        # Owner CAN view preview
        self.client.force_login(self.instructor_1)
        resp = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 200)

        # Admin CAN view preview
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 200)

    def test_starter_access(self):
        """9. Starter access allows free courses for enrolled students."""
        from apps.courses.services.access import can_access_course, can_enroll_course

        course = Course.objects.create(
            title='Intro to IT',
            slug='intro-to-it',
            access_type=Course.AccessType.FREE,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        can_enroll, _ = can_enroll_course(self.student, course)
        self.assertTrue(can_enroll)

        # Before enrollment, cannot access contents
        self.assertFalse(can_access_course(self.student, course))

        # Enrolled student has access
        Enrollment.objects.create(course=course, student=self.student, status=Enrollment.Status.ACTIVE, source=Enrollment.Source.FREE)
        self.assertTrue(can_access_course(self.student, course))

    def test_standard_access(self):
        """10. Standard access: Requires Standard or Premium subscription."""
        from apps.courses.services.access import can_access_course, can_enroll_course

        course = Course.objects.create(
            title='Full Stack JavaScript',
            slug='full-stack-js',
            access_type=Course.AccessType.STANDARD,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=Decimal('15000'),
        )
        Enrollment.objects.create(course=course, student=self.student, status=Enrollment.Status.ACTIVE)

        # No subscription -> access denied
        self.assertFalse(can_access_course(self.student, course))

        # Add Standard subscription
        std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        UserSubscription.objects.create(user=self.student, plan=std_plan, billing_cycle='monthly', is_active=True)
        self.assertTrue(can_access_course(self.student, course))

    def test_premium_access(self):
        """11. Premium access: Blocked for Standard, allowed for Premium."""
        from apps.courses.services.access import can_access_course

        course = Course.objects.create(
            title='Kernel Exploitation',
            slug='kernel-exploitation',
            access_type=Course.AccessType.PREMIUM,
            is_premium=True,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=Decimal('60000'),
        )
        Enrollment.objects.create(course=course, student=self.student, status=Enrollment.Status.ACTIVE)

        # 11a. Standard user blocked from Premium course
        std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        sub = UserSubscription.objects.create(user=self.student, plan=std_plan, billing_cycle='monthly', is_active=True)
        self.assertFalse(can_access_course(self.student, course))

        # 11b. Upgrading to Premium subscription grants access
        sub.is_active = False
        sub.save()
        prem_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.PREMIUM)
        UserSubscription.objects.create(user=self.student, plan=prem_plan, billing_cycle='monthly', is_active=True)
        self.assertTrue(can_access_course(self.student, course))

    def test_partner_access(self):
        """12. Partner access: Students affiliated with partner organization can access partner course."""
        from apps.courses.services.access import can_access_course, can_enroll_course
        from apps.partner.models import PartnerStudent

        course = Course.objects.create(
            title='YTU Software Engineering',
            slug='ytu-se',
            access_type=Course.AccessType.PARTNER_ONLY,
            partner_institution=self.institution,
            owner_type=Course.OwnerType.PARTNER,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )

        # Unaffiliated student cannot enroll
        can_enroll, reason = can_enroll_course(self.student, course)
        self.assertFalse(can_enroll)
        self.assertIn("partner", reason.lower())

        # Affiliate student with partner institution
        PartnerStudent.objects.create(
            institution=self.institution,
            student=self.student,
            status=PartnerStudent.Status.ACTIVE
        )
        can_enroll, _ = can_enroll_course(self.student, course)
        self.assertTrue(can_enroll)

        # Enroll and access
        Enrollment.objects.create(
            course=course,
            student=self.student,
            status=Enrollment.Status.ACTIVE,
            source=Enrollment.Source.PARTNER,
            partner_institution=self.institution
        )
        self.assertTrue(can_access_course(self.student, course))

    def test_unauthorized_access_blocked(self):
        """13. Unauthorized access blocked for unauthenticated and ineligible users."""
        from apps.courses.services.access import can_access_course, can_view_course

        course = Course.objects.create(
            title='Restricted Architecture',
            slug='restricted-arch',
            access_type=Course.AccessType.PAID,
            price=Decimal('50000'),
            status=Course.Status.DRAFT,
            is_published=False,
        )
        # Anonymous cannot view draft
        self.assertFalse(can_view_course(None, course))

        # Anonymous cannot access content
        self.assertFalse(can_access_course(None, course))

        # Unenrolled student cannot access content
        self.assertFalse(can_access_course(self.student, course))

    def test_existing_enrollment_still_works(self):
        """14. Existing enrollment tracking, progress, and source still work reliably."""
        course = Course.objects.create(
            title='Computer Architecture',
            slug='comp-arch',
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        module = Module.objects.create(course=course, code='CA-01', title='ALU Design', order=1)
        lesson1 = Lesson.objects.create(module=module, order=1, title='Logic Gates', content_markdown='...')
        lesson2 = Lesson.objects.create(module=module, order=2, title='Adders', content_markdown='...')

        self.client.force_login(self.student)
        resp = self.client.post(reverse('enroll', kwargs={'slug': course.slug}))
        self.assertEqual(resp.status_code, 302)

        enrollment = Enrollment.objects.get(course=course, student=self.student)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertEqual(enrollment.source, Enrollment.Source.FREE)

        # Mark lesson 1 completed
        from apps.courses.models import UserProgress
        UserProgress.objects.create(
            user=self.student, course=course, module=module, lesson=lesson1, is_completed=True
        )
        from apps.courses.views import sync_enrollment_progress
        sync_enrollment_progress(self.student, course)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_pct, 50)
        self.assertEqual(enrollment.completed_lessons_count, 1)

    def test_existing_courses_still_work(self):
        """15. Official platform courses and existing curriculum structures remain intact."""
        official_course = Course.objects.create(
            title='Diploma in Cyber Security',
            slug='diploma-cyber-security',
            is_official=True,
            owner_type=Course.OwnerType.PLATFORM,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        self.assertTrue(official_course.is_official_platform_course)
        self.assertEqual(official_course.publisher_display_name, "Myanmar E-Learning")


class Phase3AssessmentAndCredentialTests(TestCase):
    """
    Phase 3: MEL Assessment, Exam, Progress, and Certificate Architecture Tests.
    Verifies multi-disciplinary assessment models, question types, attempt limits,
    comprehensive completion rules, and certificate generation.
    """
    def setUp(self):
        Subject.ensure_default_subjects()
        self.student = User.objects.create_user(
            username='phase3_student',
            email='p3_student@example.com',
            password='password123',
            role=UserRole.STUDENT,
        )
        self.teacher = User.objects.create_user(
            username='phase3_teacher',
            email='p3_teacher@example.com',
            password='password123',
            role=UserRole.TEACHER,
        )
        self.course = Course.objects.create(
            title='Data Science & Python Programming',
            slug='ds-python',
            subject=Subject.objects.get(slug='python-programming'),
            level=Course.Level.INTERMEDIATE,
            is_published=True,
            status=Course.Status.PUBLISHED,
            owner=self.teacher,
            certificate_eligible=True,
            price=0,
        )
        self.module = Module.objects.create(
            course=self.course,
            code='DS-101',
            title='Foundations of Data Analysis',
            order=1,
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module,
            order=1,
            title='NumPy Arrays',
            content_markdown='NumPy basics and matrix operations.',
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module,
            order=2,
            title='Pandas DataFrames',
            content_markdown='Data wrangling with Pandas.',
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=Enrollment.Status.ACTIVE,
        )

    def test_assessment_types_and_proxy_models(self):
        """1. Reusable Assessment model supports 7 assessment types across all categories."""
        from apps.courses.models import Assessment, AssessmentAttempt

        assessment = Assessment.objects.create(
            course=self.course,
            title='Midterm Data Science Exam',
            quiz_type=Quiz.AssessmentType.COURSE_EXAM,
            time_limit_minutes=60,
            passing_percentage=75,
            max_attempts=2,
            randomize_questions=True,
            randomize_choices=True,
            status=Quiz.Status.PUBLISHED,
            is_required=True,
        )
        self.assertEqual(assessment.quiz_type, Quiz.AssessmentType.COURSE_EXAM)
        self.assertTrue(assessment.is_exam)
        self.assertEqual(assessment.passing_percentage, 75)
        self.assertEqual(assessment.max_attempts, 2)
        self.assertTrue(assessment.is_required)

        # Proxies
        self.assertIsInstance(assessment, Assessment)
        self.assertIsInstance(assessment, Quiz)

    def test_all_question_types_and_grading_service(self):
        """2. Question types: single choice, multi-select, true/false, fill blank, short answer, coding."""
        from apps.courses.services.assessment import grade_assessment_attempt, evaluate_question_answer
        from django.http import QueryDict

        assessment = Quiz.objects.create(
            course=self.course,
            title='Comprehensive Evaluation',
            quiz_type=Quiz.AssessmentType.PRACTICE_EXAM,
            passing_percentage=70,
            status=Quiz.Status.PUBLISHED,
        )

        # Q1: Single choice (Multiple Choice)
        q1 = Question.objects.create(
            quiz=assessment,
            order=1,
            prompt='Which Python library is standard for arrays?',
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=10,
        )
        c1_wrong = Choice.objects.create(question=q1, text='Flask', is_correct=False)
        c1_correct = Choice.objects.create(question=q1, text='NumPy', is_correct=True)

        # Q2: Multiple Select
        q2 = Question.objects.create(
            quiz=assessment,
            order=2,
            prompt='Which are mutable Python data structures?',
            question_type=Question.QuestionType.MULTIPLE_SELECT,
            points=10,
        )
        c2_a = Choice.objects.create(question=q2, text='List', is_correct=True)
        c2_b = Choice.objects.create(question=q2, text='Dictionary', is_correct=True)
        c2_c = Choice.objects.create(question=q2, text='Tuple', is_correct=False)

        # Q3: True / False
        q3 = Question.objects.create(
            quiz=assessment,
            order=3,
            prompt='Python is an interpreted language.',
            question_type=Question.QuestionType.TRUE_FALSE,
            points=10,
        )
        c3_t = Choice.objects.create(question=q3, text='True', is_correct=True)
        c3_f = Choice.objects.create(question=q3, text='False', is_correct=False)

        # Q4: Fill in the Blank
        q4 = Question.objects.create(
            quiz=assessment,
            order=4,
            prompt='What keyword defines a function in Python?',
            question_type=Question.QuestionType.FILL_IN_BLANK,
            correct_text_answer='def',
            points=10,
        )

        # Q5: Short Answer
        q5 = Question.objects.create(
            quiz=assessment,
            order=5,
            prompt='Name the operator used for floor division.',
            question_type=Question.QuestionType.SHORT_ANSWER,
            correct_text_answer='//|floor division',
            points=10,
        )

        # Q6: Coding Problem
        q6 = Question.objects.create(
            quiz=assessment,
            order=6,
            prompt='Write a function to return square of x.',
            question_type=Question.QuestionType.CODING,
            points=10,
        )

        # Verify evaluate_question_answer individually
        corr1, pts1, _ = evaluate_question_answer(q1, c1_correct.id)
        self.assertTrue(corr1)
        self.assertEqual(pts1, 10)

        corr2, pts2, _ = evaluate_question_answer(q2, [c2_a.id, c2_b.id])
        self.assertTrue(corr2)
        self.assertEqual(pts2, 10)

        # Partial selection on multi-select fails
        corr2_partial, _, _ = evaluate_question_answer(q2, [c2_a.id])
        self.assertFalse(corr2_partial)

        corr3, pts3, _ = evaluate_question_answer(q3, c3_t.id)
        self.assertTrue(corr3)

        corr4, pts4, _ = evaluate_question_answer(q4, '  def  ')
        self.assertTrue(corr4)

        corr5, pts5, _ = evaluate_question_answer(q5, '//')
        self.assertTrue(corr5)

        corr6, pts6, _ = evaluate_question_answer(q6, 'def square(x): return x * x')
        self.assertTrue(corr6)

        # Test full attempt submission via QueryDict
        qd = QueryDict('', mutable=True)
        qd[f'question_{q1.id}'] = str(c1_correct.id)
        qd.setlist(f'question_{q2.id}', [str(c2_a.id), str(c2_b.id)])
        qd[f'question_{q3.id}'] = str(c3_t.id)
        qd[f'question_{q4.id}'] = 'def'
        qd[f'question_{q5.id}'] = '//'
        qd[f'question_{q6.id}'] = 'def square(x): return x ** 2'

        attempt, msg = grade_assessment_attempt(assessment, self.student, qd, time_taken_seconds=120)
        self.assertEqual(attempt.attempt_number, 1)
        self.assertEqual(attempt.score_percentage, 100)
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.points_earned, 60)
        self.assertEqual(attempt.time_taken_seconds, 120)
        self.assertIn(str(q1.id), attempt.answers_data)
        self.assertTrue(attempt.answers_data[str(q1.id)]['is_correct'])

    def test_attempt_limit_and_unauthorized_blocking(self):
        """3. Enforce attempt limits: unauthorized extra attempts are strictly rejected."""
        from apps.courses.services.assessment import (
            check_assessment_attempt_eligibility,
            grade_assessment_attempt,
        )
        from django.core.exceptions import PermissionDenied

        assessment = Quiz.objects.create(
            course=self.course,
            title='Strict Certification Quiz',
            quiz_type=Quiz.AssessmentType.COURSE_EXAM,
            passing_percentage=80,
            max_attempts=2,
            status=Quiz.Status.PUBLISHED,
        )
        q = Question.objects.create(
            quiz=assessment, order=1, prompt='Test Q', question_type=Question.QuestionType.FILL_IN_BLANK,
            correct_text_answer='yes', points=10
        )

        # 1st attempt
        can_attempt, _ = check_assessment_attempt_eligibility(self.student, assessment)
        self.assertTrue(can_attempt)
        grade_assessment_attempt(assessment, self.student, {f'question_{q.id}': 'yes'})

        # 2nd attempt
        can_attempt, _ = check_assessment_attempt_eligibility(self.student, assessment)
        self.assertTrue(can_attempt)
        grade_assessment_attempt(assessment, self.student, {f'question_{q.id}': 'yes'})

        # 3rd attempt: blocked
        can_attempt, reason = check_assessment_attempt_eligibility(self.student, assessment)
        self.assertFalse(can_attempt)
        self.assertIn("Maximum attempt limit (2) reached", reason)

        with self.assertRaises(PermissionDenied):
            grade_assessment_attempt(assessment, self.student, {f'question_{q.id}': 'yes'})

    def test_course_completion_requires_all_prerequisites(self):
        """4. Opening/completing lessons alone does NOT complete course if quizzes/assignments are required."""
        from apps.courses.models import UserProgress, Assignment, AssignmentSubmission
        from apps.courses.services.completion import evaluate_course_completion, sync_course_completion

        # Add a required quiz to the course
        required_quiz = Quiz.objects.create(
            course=self.course,
            title='Core Competency Checkpoint',
            quiz_type=Quiz.AssessmentType.QUIZ,
            passing_percentage=75,
            is_required=True,
            status=Quiz.Status.PUBLISHED,
        )
        q = Question.objects.create(
            quiz=required_quiz, order=1, prompt='Pass code', question_type=Question.QuestionType.FILL_IN_BLANK,
            correct_text_answer='pass', points=10
        )

        # Add an assignment
        assignment = Assignment.objects.create(
            module=self.module,
            title='Pandas EDA Project',
            max_score=100,
        )

        # Student completes both lessons
        UserProgress.objects.create(
            user=self.student, course=self.course, module=self.module, lesson=self.lesson1, is_completed=True
        )
        UserProgress.objects.create(
            user=self.student, course=self.course, module=self.module, lesson=self.lesson2, is_completed=True
        )

        # Evaluate completion: lessons done, but quiz and assignment pending
        eval_result = evaluate_course_completion(self.student, self.course)
        self.assertFalse(eval_result['is_complete'])
        self.assertEqual(len(eval_result['pending_requirements']), 2)

        # Sync enrollment: status remains ACTIVE, not COMPLETED
        sync_course_completion(self.student, self.course)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, Enrollment.Status.ACTIVE)
        self.assertIsNone(self.enrollment.completed_at)

        # Now student submits assignment
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            submission_text='EDA analysis report completed.',
        )

        # Still incomplete because quiz not passed
        eval_result2 = evaluate_course_completion(self.student, self.course)
        self.assertFalse(eval_result2['is_complete'])
        self.assertEqual(len(eval_result2['pending_requirements']), 1)

        # Now student passes the required quiz
        from apps.courses.services.assessment import grade_assessment_attempt
        grade_assessment_attempt(required_quiz, self.student, {f'question_{q.id}': 'pass'})

        # Now evaluation should be complete!
        eval_result3 = evaluate_course_completion(self.student, self.course)
        self.assertTrue(eval_result3['is_complete'])
        self.assertEqual(len(eval_result3['pending_requirements']), 0)

        # Sync marks enrollment COMPLETED and generates certificate
        sync_course_completion(self.student, self.course)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, Enrollment.Status.COMPLETED)
        self.assertIsNotNone(self.enrollment.completed_at)

        # Verify Certificate generated
        from apps.certificates.models import Certificate
        cert = Certificate.objects.filter(student=self.student, course=self.course).first()
        self.assertIsNotNone(cert)
        self.assertEqual(cert.program_title, self.course.title)
        self.assertEqual(cert.student_name, self.student.username)

    def test_assessment_ui_views_and_http_access(self):
        """5. AssessmentDetailView and AssessmentSubmitView endpoints render and process submissions."""
        assessment = Quiz.objects.create(
            course=self.course,
            title='Live Interactive Assessment',
            quiz_type=Quiz.AssessmentType.PRACTICE_EXAM,
            passing_percentage=60,
            status=Quiz.Status.PUBLISHED,
        )
        q = Question.objects.create(
            quiz=assessment,
            order=1,
            prompt='What is 2 + 2 in Python?',
            question_type=Question.QuestionType.FILL_IN_BLANK,
            correct_text_answer='4',
            points=10,
        )

        # Authenticate student
        self.client.force_login(self.student)

        # GET detail view
        detail_url = reverse('assessment-detail', kwargs={'slug': self.course.slug, 'assessment_id': assessment.id})
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Live Interactive Assessment')
        self.assertContains(resp, 'What is 2 + 2 in Python?')

        # POST submission
        submit_url = reverse('assessment-submit', kwargs={'slug': self.course.slug, 'assessment_id': assessment.id})
        submit_resp = self.client.post(submit_url, {
            f'question_{q.id}': '4',
            'time_taken_seconds': '45',
        })
        self.assertEqual(submit_resp.status_code, 302)

        # Verify attempt recorded in database
        attempt = assessment.attempts.filter(student=self.student).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.score_percentage, 100)
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.time_taken_seconds, 45)

        # Unenrolled student blocked
        unenrolled_user = User.objects.create_user(
            username='stranger', email='stranger@example.com', password='password123', role=UserRole.STUDENT
        )
        self.client.force_login(unenrolled_user)
        blocked_resp = self.client.get(detail_url)
        self.assertEqual(blocked_resp.status_code, 302)
        self.assertIn(f'/courses/{self.course.slug}/', blocked_resp.url)


