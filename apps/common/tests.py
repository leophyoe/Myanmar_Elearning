from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.users.models import UserRole, StudentProfile, TeacherProfile, AdminProfile
from apps.courses.models import (
    Subject, Course, Module, Lesson, LessonType, Quiz, Question, Choice, Enrollment,
    Assignment, AssignmentSubmission, UserProgress, LiveSession,
)
from apps.labs.models import Lab, LabTemplate, LabInstance, LabCategory, LabDifficulty
from apps.ctf.models import Challenge, ChallengeCategory, FlagSubmission, SolvedChallenge
from apps.ctf.services import FlagVerificationService
from apps.scoring.models import Badge
from apps.certificates.models import Certificate
from apps.billing.models import Payment, active_payment_for
from apps.courses.views import can_access_course
from decimal import Decimal
from datetime import timedelta
import hashlib

User = get_user_model()

class Phase1SystemTests(TestCase):
    """
    Automated test verification suite for Phase 1:
    - User Model & RBAC Profile Generation
    - Course Hierarchy & 14-Module Curriculum
    - Lab Isolation & Dynamic Flag Generation
    - Constant-time CTF Flag Verification & Rate Limiting
    - Certificate Verification
    - System Health Check API
    """

    def setUp(self):
        self.client = Client()

        # 1. Create Student User
        self.student = User.objects.create_user(
            username="student_neo",
            email="neo@futuretech.edu",
            password="StrongCyberPass2026!",
            role=UserRole.STUDENT,
            first_name="Neo",
            last_name="Anderson"
        )

        # 2. Create Teacher User
        self.instructor = User.objects.create_user(
            username="prof_morpheus",
            email="morpheus@futuretech.edu",
            password="StrongCyberPass2026!",
            role=UserRole.TEACHER,
            first_name="Morpheus",
            last_name="Teacher"
        )

        # 3. Create Administrator User
        self.admin = User.objects.create_user(
            username="sys_admin",
            email="admin@futuretech.edu",
            password="StrongCyberPass2026!",
            role=UserRole.ADMIN,
            first_name="Ada",
            last_name="Administrator"
        )

    def test_01_user_and_rbac_profiles(self):
        """Verify Custom User model, three-role RBAC, and signal profile creation."""
        self.assertEqual(self.student.role, UserRole.STUDENT)
        self.assertTrue(self.student.is_student)
        self.assertFalse(self.student.is_teacher)
        self.assertFalse(self.student.is_admin)

        # Verify StudentProfile was auto-created by signals
        self.assertTrue(hasattr(self.student, 'student_profile'))
        self.assertTrue(self.student.student_profile.student_id.startswith("MEL-2026-"))

        # Verify TeacherProfile was auto-created for the teacher
        self.assertTrue(hasattr(self.instructor, 'teacher_profile'))
        self.assertTrue(self.instructor.is_teacher)
        self.assertFalse(self.instructor.is_admin)

        # Verify AdminProfile was auto-created for the administrator
        self.assertTrue(hasattr(self.admin, 'admin_profile'))
        self.assertTrue(self.admin.is_admin)
        self.assertTrue(self.admin.is_teacher)   # admin inherits teaching capability
        self.assertFalse(self.admin.is_student)

    def test_02_course_and_curriculum_integrity(self):
        """Verify Course, Module, Lesson, and Quiz relationships."""
        course = Course.objects.create(
            title="Diploma in Cyber Security",
            slug="diploma-cyber-sec",
            duration_months=10
        )
        module = Module.objects.create(
            course=course,
            order=1,
            code="MOD-01",
            title="Introduction to Cyber Security",
            summary="Foundations of defense",
            learning_objectives=["Understand CIA Triad"]
        )
        lesson = Lesson.objects.create(
            module=module,
            order=1,
            title="CIA Triad Fundamentals",
            content_markdown="# CIA Triad",
            estimated_minutes=45,
            has_quiz=True
        )
        quiz = Quiz.objects.create(
            lesson=lesson,
            title="Module 1 Quiz",
            passing_percentage=75
        )
        question = Question.objects.create(
            quiz=quiz,
            order=1,
            prompt="Which principle ensures information is not altered?",
            points=10
        )
        choice_correct = Choice.objects.create(question=question, text="Integrity", is_correct=True)
        choice_wrong = Choice.objects.create(question=question, text="Availability", is_correct=False)

        self.assertEqual(course.modules.count(), 1)
        self.assertEqual(module.lessons.count(), 1)
        self.assertEqual(lesson.quiz.questions.count(), 1)
        self.assertEqual(question.choices.filter(is_correct=True).first(), choice_correct)

    def test_03_lab_template_and_dynamic_flag_isolation(self):
        """Verify LabTemplate cgroup constraints and per-instance dynamic flag generation."""
        template = LabTemplate.objects.create(
            name="Template: Linux Permissions",
            slug="tmpl-linux-permissions",
            category=LabCategory.LINUX,
            cpu_limit="0.5",
            mem_limit="512m",
            pids_limit=100,
            read_only_root=True
        )
        lab = Lab.objects.create(
            template=template,
            title="Linux File Permissions Lab",
            slug="linux-file-permissions",
            difficulty=LabDifficulty.EASY,
            points=100
        )
        instance = LabInstance.objects.create(
            lab=lab,
            user=self.student
        )

        # Generate unique dynamic flag for this student
        flag = instance.generate_dynamic_flag()
        instance.save()

        self.assertTrue(flag.startswith("FTCR{linux-file-permissions_"))
        self.assertIsNotNone(instance.flag_hash)
        expected_hash = hashlib.sha256(flag.encode()).hexdigest()
        self.assertEqual(instance.flag_hash, expected_hash)

        # Ensure container limits are enforced in template
        self.assertEqual(template.cpu_limit, "0.5")
        self.assertEqual(template.mem_limit, "512m")
        self.assertEqual(template.pids_limit, 100)
        self.assertTrue(template.read_only_root)

    def test_04_ctf_flag_verification_and_rate_limiting(self):
        """Verify CTF flag validation, constant-time checks, and anti-bruteforce rate limiting."""
        challenge = Challenge.objects.create(
            title="SQLi Classic Bypass",
            slug="sqli-classic-bypass",
            category=ChallengeCategory.WEB,
            points=100,
            is_dynamic=False
        )
        challenge.set_static_flag("FTCR{sqli_bypass_flag_valid_123}")
        challenge.save()

        # 1. Test Incorrect Flag Submission
        res_fail = FlagVerificationService.verify_flag(
            user=self.student,
            challenge=challenge,
            submitted_flag_raw="FTCR{wrong_flag}",
            client_ip="127.0.0.1"
        )
        self.assertFalse(res_fail['success'])
        self.assertIn("Incorrect flag", res_fail['message'])

        # 2. Test Rate Limiting after 5 rapid failed attempts
        for _ in range(4):
            FlagVerificationService.verify_flag(
                user=self.student,
                challenge=challenge,
                submitted_flag_raw="FTCR{wrong_flag}",
                client_ip="127.0.0.1"
            )
        res_throttled = FlagVerificationService.verify_flag(
            user=self.student,
            challenge=challenge,
            submitted_flag_raw="FTCR{sqli_bypass_flag_valid_123}",
            client_ip="127.0.0.1"
        )
        self.assertTrue(res_throttled.get('rate_limited', False))

        # Clear submissions to test successful flag acceptance
        FlagSubmission.objects.all().delete()
        res_success = FlagVerificationService.verify_flag(
            user=self.student,
            challenge=challenge,
            submitted_flag_raw="FTCR{sqli_bypass_flag_valid_123}",
            client_ip="127.0.0.1"
        )
        self.assertTrue(res_success['success'])
        self.assertEqual(res_success['points'], 100)
        self.assertTrue(SolvedChallenge.objects.filter(user=self.student, challenge=challenge).exists())

        # Verify StudentProfile points updated
        self.student.student_profile.refresh_from_db()
        self.assertEqual(self.student.student_profile.points, 100)

    def test_05_certificate_issuance_and_public_verification(self):
        """Verify Certificate generation and public verification endpoint."""
        course = Course.objects.create(
            title="Diploma in Cyber Security",
            slug="cert-diploma-test"
        )
        cert = Certificate.objects.create(
            student=self.student,
            course=course,
            certificate_code=Certificate.generate_code(),
            student_name=self.student.get_full_name(),
            program_title="Diploma in Cyber Security",
            grade="Distinction"
        )

        self.assertTrue(cert.certificate_code.startswith("MEL-CERT-2026-"))

        # Access public verification URL
        response = self.client.get(reverse('certificate-verify', kwargs={'cert_id': cert.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cert.student_name)
        self.assertContains(response, cert.certificate_code)
        # Verify private email is NOT exposed on public verification
        self.assertNotContains(response, self.student.email)

    def test_06_system_health_check_endpoint(self):
        """Verify that /api/health/ returns HTTP 200/207 and JSON diagnostics."""
        response = self.client.get(reverse('api-health'))
        self.assertIn(response.status_code, [200, 207])
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('components', data)
        self.assertIn('database', data['components'])
        self.assertEqual(data['components']['database']['status'], 'connected')



class RoleBasedAccessTests(TestCase):
    """
    Phase 1 RBAC suite: three roles, three dashboards, role-aware redirects.
    """

    def setUp(self):
        self.client = Client()
        self.credentials = {'password': 'StrongCyberPass2026!'}

        self.student = User.objects.create_user(
            username='rbac_student', email='s@mel.edu.mm',
            role=UserRole.STUDENT, **self.credentials
        )
        self.teacher = User.objects.create_user(
            username='rbac_teacher', email='t@mel.edu.mm',
            role=UserRole.TEACHER, **self.credentials
        )
        self.admin = User.objects.create_user(
            username='rbac_admin', email='a@mel.edu.mm',
            role=UserRole.ADMIN, **self.credentials
        )

    def test_07_role_values_are_three(self):
        """The platform exposes exactly ADMIN / TEACHER / STUDENT."""
        self.assertEqual(
            [value for value, _ in UserRole.choices],
            ['admin', 'teacher', 'student']
        )

    def test_08_dashboard_routes_resolve(self):
        """All three dashboard routes are reversible, plus the legacy alias names."""
        self.assertEqual(reverse('dashboard'), '/auth/dashboard/')
        self.assertEqual(reverse('teacher-dashboard'), '/analytics/instructor/')
        self.assertEqual(reverse('admin-dashboard'), '/analytics/system/')
        for name in ('instructor-dashboard', 'system-telemetry'):
            self.assertTrue(reverse(name))

    def test_09_student_dashboard_is_role_restricted(self):
        # Student reaches their own cockpit
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

        # Teachers and admins are bounced to their own dashboards
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('teacher-dashboard').lstrip('/')))

        self.client.force_login(self.admin)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('admin-dashboard').lstrip('/')))

    def test_10_teacher_dashboard_access_matrix(self):
        url = reverse('teacher-dashboard')

        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_11_admin_dashboard_access_matrix(self):
        url = reverse('admin-dashboard')

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_12_anonymous_is_redirected_to_login(self):
        for name in ('dashboard', 'teacher-dashboard', 'admin-dashboard'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response.url)

    def test_13_login_redirects_to_role_dashboard(self):
        cases = [
            (self.student, 'dashboard'),
            (self.teacher, 'teacher-dashboard'),
            (self.admin, 'admin-dashboard'),
        ]
        for user, expected in cases:
            self.client.logout()
            response = self.client.post(reverse('login'), {
                'username': user.username,
                'password': 'StrongCyberPass2026!',
            })
            self.assertEqual(response.status_code, 302, f"no redirect for {user.username}")
            self.assertEqual(response.url, reverse(expected),
                             f"{user.username} landed on {response.url}")
        self.client.logout()

    def test_14_profile_page_renders_for_every_role(self):
        for user in (self.student, self.teacher, self.admin):
            self.client.force_login(user)
            response = self.client.get(reverse('profile'))
            self.assertEqual(response.status_code, 200, f"profile failed for {user.username}")
            self.assertContains(response, user.get_role_display())
        self.client.logout()


class CourseAuthoringAndEnrollmentTests(TestCase):
    """
    Phase 2: Subject/Module/Lesson authoring, enrolment gating and media uploads.
    """

    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(
            title="Networking", slug="networking", kind=Subject.Kind.GENERAL
        )
        self.course = Course.objects.create(
            title="Networking Fundamentals", slug="networking-fundamentals",
            subject=self.subject, description="IP, DNS, routing."
        )
        self.module = Module.objects.create(
            course=self.course, order=1, code="NET-01",
            title="OSI Model", summary="Seven layers.",
            learning_objectives=["Map the OSI layers"]
        )
        self.lesson = Lesson.objects.create(
            module=self.module, order=1, title="Layer 1-3 overview",
            content_markdown="# Hello", lesson_type=LessonType.TEXT,
        )

        self.student = User.objects.create_user(
            username='p2_student', email='p2s@mel.edu.mm',
            role=UserRole.STUDENT, password='StrongCyberPass2026!'
        )
        self.teacher = User.objects.create_user(
            username='p2_teacher', email='p2t@mel.edu.mm',
            role=UserRole.TEACHER, password='StrongCyberPass2026!'
        )
        self.admin = User.objects.create_user(
            username='p2_admin', email='p2a@mel.edu.mm',
            role=UserRole.ADMIN, password='StrongCyberPass2026!'
        )

    def test_15_lesson_requires_active_enrollment(self):
        url = reverse('lesson-detail', kwargs={'lesson_id': self.lesson.id})

        self.client.force_login(self.student)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('course-detail', kwargs={'slug': self.course.slug}), response.url)

        # Enrol, then the lesson opens
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_16_enrollment_is_created_and_listed(self):
        self.client.force_login(self.student)
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))

        enrollment = Enrollment.objects.get(course=self.course, student=self.student)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertEqual(enrollment.progress_pct, 0)

        response = self.client.get(reverse('my-courses'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)

        # Re-enrolling does not duplicate
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        self.assertEqual(
            Enrollment.objects.filter(course=self.course, student=self.student).count(), 1
        )

    def test_17_content_studio_is_role_restricted(self):
        url = reverse('manage-home')

        for user, expected in ((self.teacher, 200), (self.admin, 200), (self.student, 403)):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(url).status_code, expected,
                f"{user.username} got unexpected status"
            )

    def test_18_teacher_can_publish_a_typed_lesson(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('lesson-create'), {
            'module': self.module.id,
            'order': 2,
            'title': 'Video: Subnetting',
            'lesson_type': LessonType.VIDEO,
            'content_markdown': 'Watch and learn.',
            'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'estimated_minutes': 20,
            'has_lab': '',
            'has_quiz': '',
        })
        self.assertEqual(response.status_code, 302)

        lesson = Lesson.objects.get(title='Video: Subnetting')
        self.assertEqual(lesson.lesson_type, LessonType.VIDEO)
        self.assertTrue(lesson.has_video)
        self.assertEqual(lesson.module, self.module)

    def test_19_student_cannot_use_content_studio(self):
        self.client.force_login(self.student)
        for name, kwargs in (
            ('manage-home', {}),
            ('subject-create', {}),
            ('course-create', {}),
            ('module-create', {}),
            ('lesson-create', {}),
        ):
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, 403, f"{name} must be teacher-only")

    def test_20_module_detail_template_renders(self):
        """course_list links to module-detail - the template used to be missing."""
        self.client.force_login(self.student)
        response = self.client.get(reverse('module-detail', kwargs={'module_id': self.module.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.module.title)

    def test_21_pdf_lesson_renders_document_link(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                self.lesson.lesson_type = LessonType.PDF
                self.lesson.document_file.save(
                    'handout.pdf',
                    SimpleUploadedFile('handout.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
                )
                self.lesson.save()

                self.client.force_login(self.student)
                self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
                response = self.client.get(reverse('lesson-detail', kwargs={'lesson_id': self.lesson.id}))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'handout.pdf')
                self.assertTrue(os.path.exists(self.lesson.document_file.path))

    def test_22_oversized_video_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.courses.forms import LessonForm

        big = SimpleUploadedFile('huge.mp4', b'x', content_type='video/mp4')
        big.size = (LessonForm.MAX_VIDEO_MB + 1) * 1024 * 1024
        form = LessonForm(data={
            'module': self.module.id, 'order': 9, 'title': 'Too big',
            'lesson_type': LessonType.VIDEO, 'content_markdown': 'x',
            'estimated_minutes': 5,
        }, files={'video_file': big})
        self.assertFalse(form.is_valid())
        self.assertIn('video_file', form.errors)

    def test_23_all_authoring_forms_render(self):
        """Every Content Studio GET route must render for a teacher."""
        self.client.force_login(self.teacher)
        routes = [
            ('subject-create', {}),
            ('subject-edit', {'subject_id': self.subject.id}),
            ('course-create', {}),
            ('course-edit', {'slug': self.course.slug}),
            ('module-create', {}),
            ('module-edit', {'module_id': self.module.id}),
            ('lesson-create', {}),
            ('lesson-edit', {'lesson_id': self.lesson.id}),
            ('lesson-delete', {'lesson_id': self.lesson.id}),
            ('manage-home', {}),
        ]
        for name, kwargs in routes:
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, 200, f"{name} failed to render")


class AssessmentAndGradingTests(TestCase):
    """Phase 3: quiz building, assignment hand-ins and the grading queue."""

    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(title='Operations', slug='operations', kind=Subject.Kind.GENERAL)
        self.course = Course.objects.create(
            title='Ops Basics', slug='ops-basics', subject=self.subject, description='Run things.'
        )
        self.module = Module.objects.create(
            course=self.course, order=1, code='OPS-01', title='First steps',
            summary='Getting started.', learning_objectives=['Ship safely']
        )
        self.lesson = Lesson.objects.create(
            module=self.module, order=1, title='Intro to Ops',
            content_markdown='Read this.', lesson_type=LessonType.TEXT,
        )
        self.assignment_lesson = Lesson.objects.create(
            module=self.module, order=2, title='Write the report',
            content_markdown='Deliver a report.', lesson_type=LessonType.ASSIGNMENT,
        )
        self.assignment = Assignment.objects.create(
            module=self.module, title='Incident report',
            description='Document the incident end to end.', max_score=100,
        )

        self.student = User.objects.create_user(
            username='a3_student', email='a3s@mel.edu.mm',
            role=UserRole.STUDENT, password='StrongCyberPass2026!'
        )
        self.teacher = User.objects.create_user(
            username='a3_teacher', email='a3t@mel.edu.mm',
            role=UserRole.TEACHER, password='StrongCyberPass2026!'
        )
        self.admin = User.objects.create_user(
            username='a3_admin', email='a3a@mel.edu.mm',
            role=UserRole.ADMIN, password='StrongCyberPass2026!'
        )

    # -- helpers -------------------------------------------------------
    def quiz_payload(self, **overrides):
        """Build a quiz-builder POST for a single new question."""
        from apps.courses.forms import QuestionFormSet

        quiz, _ = Quiz.objects.get_or_create(
            lesson=self.lesson, defaults={'title': 'Checkpoint'}
        )
        prefix = QuestionFormSet(instance=quiz).prefix
        data = {
            'title': 'Checkpoint',
            'passing_percentage': '50',
            'max_attempts': '3',
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-order': '1',
            f'{prefix}-0-prompt': 'What is 2 + 2?',
            f'{prefix}-0-points': '10',
            f'{prefix}-0-explanation': 'Basic arithmetic.',
            f'{prefix}-0-choice_1': '3',
            f'{prefix}-0-choice_2': '4',
            f'{prefix}-0-choice_3': '',
            f'{prefix}-0-choice_4': '',
            f'{prefix}-0-correct_choice': '2',
        }
        for key, value in overrides.items():
            data[key if key.startswith(prefix) else f'{prefix}-0-{key}'] = value
        return data

    # -- quiz authoring ------------------------------------------------
    def test_24_teacher_builds_a_quiz(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id}),
            self.quiz_payload(),
        )
        self.assertEqual(response.status_code, 302)

        quiz = Quiz.objects.get(lesson=self.lesson)
        self.assertEqual(quiz.questions.count(), 1)

        question = quiz.questions.first()
        self.assertEqual(question.prompt, 'What is 2 + 2?')
        self.assertEqual(question.choices.count(), 2)
        correct = list(question.choices.filter(is_correct=True))
        self.assertEqual(len(correct), 1)
        self.assertEqual(correct[0].text, '4')

        self.lesson.refresh_from_db()
        self.assertTrue(self.lesson.has_quiz)

    def test_25_quiz_requires_a_correct_answer(self):
        self.client.force_login(self.teacher)
        payload = self.quiz_payload(choice_1='', choice_2='4', correct_choice='1')
        response = self.client.post(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id}), payload
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.exists())

    def test_26_quiz_builder_is_teacher_only(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_27_quiz_builder_renders_existing_choices(self):
        self.client.force_login(self.teacher)
        self.client.post(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id}), self.quiz_payload()
        )
        response = self.client.get(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What is 2 + 2?')
        # The saved option text must come back into the form
        self.assertContains(response, 'value="4"')

    # -- assignments ---------------------------------------------------
    def test_28_assignment_requires_enrolment(self):
        url = reverse('assignment-detail', kwargs={'assignment_id': self.assignment.id})
        self.client.force_login(self.student)
        self.assertIn(reverse('course-detail', kwargs={'slug': self.course.slug}),
                      self.client.get(url).url)

        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_29_student_hand_in_is_upserted(self):
        self.client.force_login(self.student)
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        url = reverse('assignment-submit', kwargs={'assignment_id': self.assignment.id})

        self.client.post(url, {'submission_text': 'First draft'})
        self.assertEqual(AssignmentSubmission.objects.count(), 1)

        self.client.post(url, {'submission_text': 'Revised draft'})
        submission = AssignmentSubmission.objects.get()
        self.assertEqual(submission.submission_text, 'Revised draft')
        self.assertEqual(submission.student, self.student)

    def test_30_empty_hand_in_is_rejected(self):
        self.client.force_login(self.student)
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        response = self.client.post(
            reverse('assignment-submit', kwargs={'assignment_id': self.assignment.id}),
            {'submission_text': '   '},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AssignmentSubmission.objects.exists())

    def test_31_grading_awards_score_and_completes_the_lesson(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, submission_text='Done'
        )
        url = reverse('submission-grade', kwargs={'submission_id': submission.id})

        self.client.force_login(self.teacher)
        response = self.client.post(url, {'score': 80, 'feedback': 'Solid work.'})
        self.assertEqual(response.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.score, 80)
        self.assertEqual(submission.feedback, 'Solid work.')
        self.assertEqual(submission.graded_by, self.teacher)
        self.assertIsNotNone(submission.graded_at)

        progress = UserProgress.objects.get(
            user=self.student, lesson=self.assignment_lesson
        )
        self.assertTrue(progress.is_completed)

    def test_32_failing_grade_leaves_progress_untouched(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, submission_text='meh'
        )
        self.client.force_login(self.teacher)
        self.client.post(
            reverse('submission-grade', kwargs={'submission_id': submission.id}),
            {'score': 10, 'feedback': 'Too thin.'},
        )
        submission.refresh_from_db()
        self.assertEqual(submission.score, 10)
        self.assertFalse(
            UserProgress.objects.filter(user=self.student, is_completed=True).exists()
        )

    def test_33_score_above_max_is_rejected(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment, student=self.student, submission_text='x'
        )
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('submission-grade', kwargs={'submission_id': submission.id}),
            {'score': 500, 'feedback': 'nope'},
        )
        self.assertEqual(response.status_code, 200)
        submission.refresh_from_db()
        self.assertIsNone(submission.score)

    # -- access control ------------------------------------------------
    def test_34_grading_queue_is_role_restricted(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('submission-list')).status_code, 403)

        for user in (self.teacher, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('submission-list')).status_code, 200)

    def test_35_assignment_create_is_teacher_only(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('assignment-create')).status_code, 403)

    def test_36_student_sees_module_assignments_on_lesson(self):
        self.client.force_login(self.student)
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))
        response = self.client.get(
            reverse('lesson-detail', kwargs={'lesson_id': self.lesson.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incident report')

    def test_37_student_can_take_a_teacher_built_quiz(self):
        self.client.force_login(self.teacher)
        self.client.post(
            reverse('quiz-edit', kwargs={'lesson_id': self.lesson.id}), self.quiz_payload()
        )
        quiz = Quiz.objects.get(lesson=self.lesson)
        question = quiz.questions.get()
        correct = question.choices.get(is_correct=True)

        self.client.logout()
        self.client.force_login(self.student)
        self.client.post(reverse('enroll', kwargs={'slug': self.course.slug}))

        response = self.client.post(
            reverse('quiz-submit', kwargs={'lesson_id': self.lesson.id}),
            {f'question_{question.id}': correct.id},
        )
        self.assertEqual(response.status_code, 302)

        progress = UserProgress.objects.get(user=self.student, lesson=self.lesson)
        self.assertTrue(progress.is_completed)
        # Re-read: the view saved a separate StudentProfile instance.
        self.assertEqual(
            StudentProfile.objects.get(user=self.student).points, question.points
        )


class ProgressAndCertificateTests(TestCase):
    """Phase 4: lesson completion, automatic certificates and reports."""

    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(title='General Studies', slug='general-studies', kind=Subject.Kind.GENERAL)

        # Course completed through plain reading lessons
        self.course = Course.objects.create(
            title='Grad Course', slug='grad-course', subject=self.subject, description='Read and go.'
        )
        self.module = Module.objects.create(
            course=self.course, order=1, code='GC-01', title='Part one', summary='s',
            learning_objectives=['Learn'],
        )
        self.lesson_a = Lesson.objects.create(
            module=self.module, order=1, title='Chapter A', content_markdown='a',
            lesson_type=LessonType.TEXT,
        )
        self.lesson_b = Lesson.objects.create(
            module=self.module, order=2, title='Chapter B', content_markdown='b',
            lesson_type=LessonType.TEXT,
        )

        # Course gated behind a quiz
        self.quiz_course = Course.objects.create(
            title='Quiz Course', slug='quiz-course', subject=self.subject, description='q'
        )
        self.quiz_module = Module.objects.create(
            course=self.quiz_course, order=1, code='QC-01', title='Part one', summary='s',
            learning_objectives=['Learn'],
        )
        self.quiz_lesson = Lesson.objects.create(
            module=self.quiz_module, order=1, title='Quiz lesson', content_markdown='q',
            lesson_type=LessonType.QUIZ, has_quiz=True,
        )
        self.quiz = Quiz.objects.create(
            lesson=self.quiz_lesson, title='Check', passing_percentage=50, max_attempts=3
        )
        question = Question.objects.create(quiz=self.quiz, order=1, prompt='True or false?', points=10)
        Choice.objects.create(question=question, text='True', is_correct=True)
        Choice.objects.create(question=question, text='False', is_correct=False)

        # Course gated behind a graded assignment
        self.assign_course = Course.objects.create(
            title='Assign Course', slug='assign-course', subject=self.subject, description='a'
        )
        self.assign_module = Module.objects.create(
            course=self.assign_course, order=1, code='AC-01', title='Part one', summary='s',
            learning_objectives=['Deliver'],
        )
        self.assign_lesson = Lesson.objects.create(
            module=self.assign_module, order=1, title='Deliverable', content_markdown='do it',
            lesson_type=LessonType.ASSIGNMENT,
        )
        self.assignment = Assignment.objects.create(
            module=self.assign_module, title='Project', description='Build it.', max_score=100
        )

        self.student = User.objects.create_user(
            username='p4_student', email='p4s@mel.edu.mm',
            first_name='Su', last_name='Mya',
            role=UserRole.STUDENT, password='StrongCyberPass2026!'
        )
        self.teacher = User.objects.create_user(
            username='p4_teacher', email='p4t@mel.edu.mm',
            role=UserRole.TEACHER, password='StrongCyberPass2026!'
        )
        self.admin = User.objects.create_user(
            username='p4_admin', email='p4a@mel.edu.mm',
            role=UserRole.ADMIN, password='StrongCyberPass2026!'
        )

    def enroll(self, course):
        self.client.post(reverse('enroll', kwargs={'slug': course.slug}))
        return Enrollment.objects.get(course=course, student=self.student)

    def complete(self, lesson):
        return self.client.post(
            reverse('lesson-complete', kwargs={'lesson_id': lesson.id})
        )

    # -- lesson completion --------------------------------------------
    def test_38_marking_a_lesson_complete_tracks_progress(self):
        self.client.force_login(self.student)
        enrollment = self.enroll(self.course)

        self.complete(self.lesson_a)
        progress = UserProgress.objects.get(user=self.student, lesson=self.lesson_a)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_pct, 50)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)

    def test_39_completing_every_lesson_graduates_and_issues_a_certificate(self):
        from apps.certificates.models import Certificate

        self.client.force_login(self.student)
        enrollment = self.enroll(self.course)
        self.complete(self.lesson_a)
        self.complete(self.lesson_b)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_pct, 100)
        self.assertEqual(enrollment.status, Enrollment.Status.COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)

        certificate = Certificate.objects.get(student=self.student, course=self.course)
        self.assertEqual(certificate.program_title, 'Grad Course')
        self.assertEqual(certificate.student_name, 'Su Mya')
        self.assertEqual(certificate.grade, 'Pass')
        self.assertTrue(certificate.certificate_code.startswith('MEL-CERT-2026-'))

    def test_40_quiz_lesson_cannot_be_tick_off_manually(self):
        self.client.force_login(self.student)
        self.enroll(self.quiz_course)
        self.complete(self.quiz_lesson)

        progress = UserProgress.objects.filter(
            user=self.student, lesson=self.quiz_lesson, is_completed=True
        ).exists()
        self.assertFalse(progress)

    def test_41_assignment_lesson_waits_for_the_grade(self):
        self.client.force_login(self.student)
        self.enroll(self.assign_course)
        self.complete(self.assign_lesson)

        self.assertFalse(
            UserProgress.objects.filter(
                user=self.student, lesson=self.assign_lesson, is_completed=True
            ).exists()
        )

    def test_42_unenrolled_student_cannot_track_progress(self):
        self.client.force_login(self.student)
        response = self.complete(self.lesson_a)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserProgress.objects.filter(user=self.student).exists())

    def test_43_completion_toggles_back_off(self):
        self.client.force_login(self.student)
        self.enroll(self.course)
        self.complete(self.lesson_a)
        self.complete(self.lesson_a)

        self.assertFalse(
            UserProgress.objects.get(user=self.student, lesson=self.lesson_a).is_completed
        )

    # -- certificates ---------------------------------------------------
    def test_44_issuance_is_idempotent(self):
        from apps.certificates.models import Certificate
        from apps.certificates.services import issue_certificate_for_enrollment

        enrollment = Enrollment.objects.create(
            course=self.course, student=self.student, status=Enrollment.Status.ACTIVE
        )
        first = issue_certificate_for_enrollment(enrollment)
        second = issue_certificate_for_enrollment(enrollment)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Certificate.objects.filter(student=self.student).count(), 1)

    def test_45_certificate_code_collisions_do_not_fail(self):
        from apps.certificates.models import Certificate
        from apps.certificates.services import issue_certificate_for_enrollment

        other = User.objects.create_user(
            username='p4_other', email='p4o@mel.edu.mm',
            role=UserRole.STUDENT, password='StrongCyberPass2026!'
        )
        e1 = Enrollment.objects.create(course=self.course, student=self.student, status=Enrollment.Status.ACTIVE)
        e2 = Enrollment.objects.create(course=self.course, student=other, status=Enrollment.Status.ACTIVE)

        generated = Certificate.generate_code()
        from unittest import mock
        with mock.patch.object(Certificate, 'generate_code', side_effect=[generated, generated, 'MEL-CERT-2026-FINAL']):
            c1 = issue_certificate_for_enrollment(e1)
            c2 = issue_certificate_for_enrollment(e2)
        self.assertNotEqual(c1.certificate_code, c2.certificate_code)

    def test_46_grade_thresholds(self):
        from apps.certificates.services import compute_grade

        self.assertEqual(compute_grade(self.student, self.course), 'Pass')

        module = Module.objects.create(
            course=self.course, order=2, code='GC-02', title='Part two', summary='s',
            learning_objectives=['Grade'],
        )
        assignment = Assignment.objects.create(
            module=module, title='Report', description='Write it.', max_score=100
        )
        grade_cases = [(90, 'Distinction'), (75, 'Merit'), (60, 'Pass')]
        for score, expected in grade_cases:
            AssignmentSubmission.objects.create(
                assignment=assignment, student=self.student, submission_text='x',
                score=score, graded_by=self.teacher, graded_at=timezone.now(),
            )
            self.assertEqual(compute_grade(self.student, self.course), expected,
                             f'{score} pts should be {expected}')
            AssignmentSubmission.objects.all().delete()

    # -- reports ---------------------------------------------------------
    def test_47_reports_are_role_restricted(self):
        for name in ('report-courses', 'report-students'):
            self.client.force_login(self.student)
            self.assertEqual(
                self.client.get(reverse(name)).status_code, 403, f'{name} must block students'
            )
            for user in (self.teacher, self.admin):
                self.client.force_login(user)
                self.assertEqual(
                    self.client.get(reverse(name)).status_code, 200,
                    f'{name} must render for {user.username}'
                )

    def test_48_course_report_shows_enrolment_and_certificates(self):
        self.client.force_login(self.student)
        self.enroll(self.course)
        self.complete(self.lesson_a)
        self.complete(self.lesson_b)

        self.client.force_login(self.teacher)
        response = self.client.get(reverse('report-courses'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grad Course')
        self.assertContains(response, '100%')

    def test_49_student_report_shows_the_learner(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('report-students'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'p4s@mel.edu.mm')

    # -- student dashboard ------------------------------------------------
    def test_50_dashboard_counts_enrolled_lessons_and_lists_courses(self):
        self.client.force_login(self.student)
        self.enroll(self.course)
        self.complete(self.lesson_a)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grad Course')
        self.assertEqual(response.context['total_lessons'], 2)
        self.assertEqual(response.context['completed_lessons'], 1)
        self.assertEqual(response.context['progress_percentage'], 50)
        self.assertEqual(response.context['next_lesson'], self.lesson_b)

    def test_51_revoked_certificates_are_hidden_everywhere(self):
        from apps.certificates.models import Certificate
        self.client.force_login(self.student)
        enrollment = self.enroll(self.course)
        self.complete(self.lesson_a)
        self.complete(self.lesson_b)

        certificate = Certificate.objects.get(student=self.student)
        certificate.is_revoked = True
        certificate.save(update_fields=['is_revoked'])

        self.assertFalse(
            self.client.get(reverse('dashboard')).context['certificates'].exists()
        )
        self.assertFalse(
            self.client.get(reverse('certificate-list')).context['certificates'].exists()
        )


class PaymentAndCheckoutTests(TestCase):
    """Phase 5: paid courses, manual checkout, admin review and revenue share."""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='p5teacher', password='pw', email='p5t@mel.edu.mm',
            role=UserRole.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            username='p5other', password='pw', email='p5o@mel.edu.mm',
            role=UserRole.TEACHER,
        )
        self.student = User.objects.create_user(
            username='p5student', password='pw', email='p5s@mel.edu.mm',
            role=UserRole.STUDENT,
        )
        self.admin = User.objects.create_user(
            username='p5admin', password='pw', email='p5a@mel.edu.mm',
            role=UserRole.ADMIN,
        )

        self.free_course = Course.objects.create(
            title='Free Course', slug='free-course', description='free',
            owner=self.teacher, price=0,
        )
        self.paid_course = Course.objects.create(
            title='Paid Course', slug='paid-course', description='paid',
            owner=self.teacher, price=Decimal('5000.00'),
        )
        self.monthly_course = Course.objects.create(
            title='Monthly Course', slug='monthly-course', description='sub',
            owner=self.teacher, price=Decimal('2000.00'),
            billing_period=Course.BillingPeriod.MONTHLY,
        )
        self.module = Module.objects.create(
            course=self.paid_course, order=1, code='MOD-01',
            title='M1', summary='s',
        )
        self.lesson = Lesson.objects.create(
            module=self.module, order=1, title='L1', content_markdown='body',
            lesson_type=LessonType.TEXT, estimated_minutes=10,
        )

    def enroll(self, user, course):
        return Enrollment.objects.create(course=course, student=user)

    def submit_payment(self, course, reference='TXN-001'):
        return self.client.post(
            reverse('checkout', kwargs={'slug': course.slug}),
            {'method': 'kbz_pay', 'reference': reference, 'note': ''},
        )

    # -- discovery ---------------------------------------------------------
    def test_52_paid_course_detail_shows_price_and_buy_button(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('course-detail', kwargs={'slug': self.paid_course.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '5000.0')
        self.assertContains(response, reverse('checkout', kwargs={'slug': self.paid_course.slug}))

    def test_53_free_course_detail_shows_free_badge_and_no_checkout(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('course-detail', kwargs={'slug': self.free_course.slug}))
        self.assertContains(response, 'Free')
        self.assertNotContains(response, reverse('checkout', kwargs={'slug': self.free_course.slug}))

    # -- enrolment gate ----------------------------------------------------
    def test_54_enroll_on_paid_course_redirects_to_checkout(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('enroll', kwargs={'slug': self.paid_course.slug}))
        self.assertRedirects(
            response, reverse('checkout', kwargs={'slug': self.paid_course.slug}),
            fetch_redirect_response=False,
        )
        self.assertFalse(Enrollment.objects.filter(course=self.paid_course).exists())

    def test_55_enroll_on_free_course_still_works(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('enroll', kwargs={'slug': self.free_course.slug}))
        self.assertRedirects(
            response, reverse('course-detail', kwargs={'slug': self.free_course.slug}),
            fetch_redirect_response=False,
        )
        self.assertTrue(Enrollment.objects.filter(course=self.free_course).exists())

    def test_56_lesson_is_locked_until_the_payment_is_approved(self):
        self.client.force_login(self.student)
        self.enroll(self.student, self.paid_course)

        response = self.client.get(reverse('lesson-detail', kwargs={'lesson_id': self.lesson.id}))
        self.assertRedirects(
            response, reverse('course-detail', kwargs={'slug': self.paid_course.slug}),
            fetch_redirect_response=False,
        )
        self.assertFalse(can_access_course(self.student, self.paid_course))

    # -- checkout ----------------------------------------------------------
    def test_57_checkout_creates_a_pending_payment_with_the_split(self):
        self.client.force_login(self.student)
        response = self.submit_payment(self.paid_course)
        self.assertRedirects(
            response, reverse('course-detail', kwargs={'slug': self.paid_course.slug}),
            fetch_redirect_response=False,
        )

        payment = Payment.objects.get(course=self.paid_course)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, Decimal('5000.00'))
        self.assertEqual(payment.platform_fee, Decimal('1250.00'))
        self.assertEqual(payment.teacher_amount, Decimal('3750.00'))
        self.assertEqual(payment.reference, 'TXN-001')
        self.assertIsNone(active_payment_for(self.student, self.paid_course))
        self.assertFalse(Enrollment.objects.filter(course=self.paid_course).exists())

    def test_58_checkout_rejects_an_empty_submission(self):
        self.client.force_login(self.student)
        self.client.post(
            reverse('checkout', kwargs={'slug': self.paid_course.slug}),
            {'method': 'wave_pay', 'reference': '', 'note': ''},
        )
        self.assertFalse(Payment.objects.exists())

    def test_59_checkout_is_closed_while_a_payment_is_pending(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course, reference='FIRST')
        self.submit_payment(self.paid_course, reference='SECOND')
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Payment.objects.get().reference, 'FIRST')

    def test_60_checkout_redirects_away_for_staff_and_free_courses(self):
        self.client.force_login(self.teacher)
        self.assertRedirects(
            self.client.get(reverse('checkout', kwargs={'slug': self.paid_course.slug})),
            reverse('course-detail', kwargs={'slug': self.paid_course.slug}),
            fetch_redirect_response=False,
        )
        self.client.force_login(self.student)
        self.assertRedirects(
            self.client.get(reverse('checkout', kwargs={'slug': self.free_course.slug})),
            reverse('course-detail', kwargs={'slug': self.free_course.slug}),
            fetch_redirect_response=False,
        )
        self.assertFalse(Payment.objects.exists())

    # -- admin review queue ------------------------------------------------
    def test_61_review_queue_is_admin_only(self):
        for name in ('payment-list',):
            for role in (UserRole.STUDENT, UserRole.TEACHER):
                user = User.objects.create_user(
                    username=f'q-{role}', password='pw', role=role,
                    email=f'q-{role}@mel.edu.mm',
                )
                self.client.force_login(user)
                self.assertEqual(
                    self.client.get(reverse(name)).status_code, 403,
                    f'{role} must not reach {name}',
                )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('payment-list')).status_code, 200)

    def test_62_approving_a_payment_enrolls_the_student(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course)
        payment = Payment.objects.get()

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('payment-review', kwargs={'payment_id': payment.id}),
            {'action': 'approve'},
        )
        self.assertRedirects(
            response, reverse('payment-list'), fetch_redirect_response=False
        )

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.reviewed_by, self.admin)
        self.assertIsNotNone(payment.period_start)
        self.assertIsNone(payment.period_end)

        enrollment = Enrollment.objects.get(course=self.paid_course)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertTrue(can_access_course(self.student, self.paid_course))
        self.assertIsNotNone(active_payment_for(self.student, self.paid_course))

    def test_63_monthly_approvals_receive_an_expiry_date(self):
        self.client.force_login(self.student)
        self.submit_payment(self.monthly_course)
        payment = Payment.objects.get()

        self.client.force_login(self.admin)
        self.client.post(
            reverse('payment-review', kwargs={'payment_id': payment.id}),
            {'action': 'approve'},
        )
        payment.refresh_from_db()
        self.assertEqual(payment.billing_period, Course.BillingPeriod.MONTHLY)
        self.assertEqual(payment.period_end.month, payment.period_start.month + 1)

    def test_64_rejection_requires_a_reason_and_leaves_the_student_out(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course)
        payment = Payment.objects.get()

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('payment-review', kwargs={'payment_id': payment.id}),
            {'action': 'reject', 'rejection_reason': ''},
        )
        payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.PENDING)

        self.client.post(
            reverse('payment-review', kwargs={'payment_id': payment.id}),
            {'action': 'reject', 'rejection_reason': 'No such wallet record.'},
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REJECTED)
        self.assertEqual(payment.rejection_reason, 'No such wallet record.')
        self.assertFalse(Enrollment.objects.filter(course=self.paid_course).exists())
        self.assertFalse(can_access_course(self.student, self.paid_course))

    def test_65_already_reviewed_payments_are_locked(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course)
        payment = Payment.objects.get()
        payment.status = Payment.Status.APPROVED
        payment.save(update_fields=['status'])

        self.client.force_login(self.admin)
        self.client.post(
            reverse('payment-review', kwargs={'payment_id': payment.id}),
            {'action': 'reject', 'rejection_reason': 'nope'},
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertNotEqual(payment.rejection_reason, 'nope')

    # -- authoring ownership ----------------------------------------------
    def test_66_a_teacher_cannot_edit_another_teachers_course(self):
        self.client.force_login(self.other_teacher)
        response = self.client.get(
            reverse('course-edit', kwargs={'slug': self.paid_course.slug})
        )
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.teacher)
        self.assertEqual(
            self.client.get(
                reverse('course-edit', kwargs={'slug': self.paid_course.slug})
            ).status_code,
            200,
        )

        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse('course-edit', kwargs={'slug': self.paid_course.slug})
            ).status_code,
            200,
        )

    def test_67_a_new_course_is_owned_by_its_creator(self):
        self.client.force_login(self.other_teacher)
        self.client.post(reverse('course-create'), {
            'title': 'Brand New', 'slug': 'brand-new', 'description': 'd',
            'duration_months': 3, 'is_published': 'on',
            'price': '0', 'billing_period': 'one_time',
        })
        course = Course.objects.get(slug='brand-new')
        self.assertEqual(course.owner, self.other_teacher)
        self.assertTrue(course.is_free)

    # -- reporting ---------------------------------------------------------
    def test_68_earnings_report_shows_the_revenue_split(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course)
        self.client.force_login(self.admin)
        self.client.post(
            reverse('payment-review', kwargs={'payment_id': Payment.objects.get().id}),
            {'action': 'approve'},
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse('report-earnings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paid Course')
        self.assertContains(response, '1250')
        self.assertContains(response, '3750')
        self.assertEqual(response.context['totals']['sales'], 1)
        self.assertEqual(response.context['totals']['fee'], Decimal('1250.00'))
        self.assertEqual(response.context['totals']['earned'], Decimal('3750.00'))

        self.client.force_login(self.other_teacher)
        response = self.client.get(reverse('report-earnings'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['totals']['sales'], 0)

    def test_69_student_sees_their_own_payment_history(self):
        self.client.force_login(self.student)
        self.submit_payment(self.paid_course)

        response = self.client.get(reverse('payment-history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paid Course')
        self.assertEqual(len(response.context['payments']), 1)


class LiveSessionTests(TestCase):
    """Phase 5b: scheduled real-time classes (Zoom / Google Meet / Teams)."""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='p6teacher', password='pw', email='p6t@mel.edu.mm',
            role=UserRole.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            username='p6other', password='pw', email='p6o@mel.edu.mm',
            role=UserRole.TEACHER,
        )
        self.student = User.objects.create_user(
            username='p6student', password='pw', email='p6s@mel.edu.mm',
            role=UserRole.STUDENT,
        )
        self.admin = User.objects.create_user(
            username='p6admin', password='pw', email='p6a@mel.edu.mm',
            role=UserRole.ADMIN,
        )
        self.course = Course.objects.create(
            title='Live Course', slug='live-course', description='x',
            owner=self.teacher, price=0,
        )
        self.session = LiveSession.objects.create(
            course=self.course, title='Kickoff',
            provider=LiveSession.Provider.ZOOM,
            join_url='https://zoom.us/j/123456789',
            starts_at=timezone.now() + timedelta(hours=3),
            duration_minutes=45,
        )
        self.other_session = LiveSession.objects.create(
            course=self.course, title='Other teacher class',
            provider=LiveSession.Provider.TEAMS,
            join_url='https://teams.microsoft.com/l/meetup-join/secret',
            starts_at=timezone.now() + timedelta(hours=6),
            duration_minutes=60,
        )

    def session_data(self, **overrides):
        data = {
            'course': self.course.id,
            'title': 'Revision session',
            'provider': LiveSession.Provider.GOOGLE_MEET,
            'join_url': 'https://meet.google.com/abc-defg-hij',
            'starts_at': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 30,
            'notes': 'Bring your notes',
            'is_published': 'on',
        }
        data.update(overrides)
        return data

    # -- authoring ---------------------------------------------------------
    def test_70_teacher_schedules_a_live_session(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('live-session-create'), self.session_data()
        )
        self.assertRedirects(
            response, reverse('live-session-list'), fetch_redirect_response=False
        )
        created = LiveSession.objects.get(title='Revision session')
        self.assertEqual(created.course, self.course)
        self.assertEqual(created.provider, LiveSession.Provider.GOOGLE_MEET)

    def test_71_students_cannot_reach_the_live_session_studio(self):
        routes = (
            ('live-session-list', {}),
            ('live-session-create', {}),
            ('live-session-edit', {'session_id': self.session.id}),
            ('live-session-delete', {'session_id': self.session.id}),
        )
        for name, kwargs in routes:
            self.client.force_login(self.student)
            self.assertEqual(
                self.client.get(reverse(name, kwargs=kwargs)).status_code, 403,
                f'{name} must be teacher-only',
            )

    def test_72_a_teacher_cannot_manage_another_teachers_session(self):
        # The session lives on a course owned by self.teacher.
        for name in ('live-session-edit', 'live-session-delete'):
            self.client.force_login(self.other_teacher)
            self.assertEqual(
                self.client.get(
                    reverse(name, kwargs={'session_id': self.other_session.id})
                ).status_code,
                404,
            )
            self.client.force_login(self.teacher)
            self.assertEqual(
                self.client.get(
                    reverse(name, kwargs={'session_id': self.other_session.id})
                ).status_code,
                200,
            )
            self.client.force_login(self.admin)
            self.assertEqual(
                self.client.get(
                    reverse(name, kwargs={'session_id': self.other_session.id})
                ).status_code,
                200,
            )

    def test_73_teacher_cannot_schedule_on_a_course_they_do_not_own(self):
        foreign = Course.objects.create(
            title='Not mine', slug='not-mine', description='x',
            owner=self.other_teacher, price=0,
        )
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('live-session-create'), self.session_data(course=foreign.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LiveSession.objects.filter(course=foreign).exists())

    def test_74_a_session_cannot_be_scheduled_in_the_past(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('live-session-create'),
            self.session_data(
                starts_at=(timezone.now() - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schedule the session in the future.')
        self.assertFalse(LiveSession.objects.filter(title='Revision session').exists())

    # -- visibility for students ------------------------------------------
    def test_75_enrolled_student_sees_the_join_link(self):
        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('course-detail', kwargs={'slug': self.course.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://zoom.us/j/123456789')
        self.assertContains(response, 'Kickoff')
        self.assertEqual(len(response.context['live_sessions']), 2)

    def test_76_a_visitor_without_access_never_sees_the_join_link(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('course-detail', kwargs={'slug': self.course.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'https://zoom.us/j/123456789')
        self.assertEqual(response.context['live_sessions'], [])

        self.client.force_login(self.other_teacher)
        response = self.client.get(
            reverse('course-detail', kwargs={'slug': self.course.slug})
        )
        # Staff always have access
        self.assertContains(response, 'https://zoom.us/j/123456789')

    def test_77_unpublished_and_past_sessions_are_hidden(self):
        self.session.is_published = False
        self.session.save(update_fields=['is_published'])
        self.other_session.starts_at = timezone.now() - timedelta(minutes=5)
        self.other_session.save(update_fields=['starts_at'])

        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse('course-detail', kwargs={'slug': self.course.slug})
        )
        self.assertEqual(response.context['live_sessions'], [])
        self.assertNotContains(response, 'zoom.us')

    def test_78_paid_course_sessions_stay_hidden_without_a_payment(self):
        paid = Course.objects.create(
            title='Paid Live', slug='paid-live', description='x',
            owner=self.teacher, price=Decimal('1000.00'),
        )
        LiveSession.objects.create(
            course=paid, title='Paid only',
            join_url='https://zoom.us/j/999',
            starts_at=timezone.now() + timedelta(days=1),
        )
        Enrollment.objects.create(course=paid, student=self.student)

        self.client.force_login(self.student)
        response = self.client.get(
            reverse('course-detail', kwargs={'slug': paid.slug})
        )
        self.assertEqual(response.context['live_sessions'], [])
        self.assertNotContains(response, 'https://zoom.us/j/999')

    # -- student dashboard -------------------------------------------------
    def test_79_dashboard_lists_sessions_for_enrolled_courses_only(self):
        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['upcoming_live_sessions']), 2)
        self.assertContains(response, 'Kickoff')

        # Another course the student never joined must not leak in.
        elsewhere = Course.objects.create(
            title='Elsewhere', slug='elsewhere', description='x',
            owner=self.teacher, price=0,
        )
        LiveSession.objects.create(
            course=elsewhere, title='Secret class',
            join_url='https://zoom.us/j/000000',
            starts_at=timezone.now() + timedelta(days=2),
        )
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'https://zoom.us/j/000000')
        self.assertEqual(len(response.context['upcoming_live_sessions']), 2)

    # -- studio surface ----------------------------------------------------
    def test_80_content_studio_and_list_pages_render(self):
        self.client.force_login(self.teacher)
        for name in ('manage-home', 'live-session-list', 'live-session-create'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
        response = self.client.get(reverse('live-session-edit', kwargs={'session_id': self.session.id}))
        self.assertEqual(response.status_code, 200)
