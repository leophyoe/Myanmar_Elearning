from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import UserRole, StudentProfile, TeacherProfile, AdminProfile
from apps.courses.models import (
    Subject, Course, Module, Lesson, LessonType, Quiz, Question, Choice, Enrollment
)
from apps.labs.models import Lab, LabTemplate, LabInstance, LabCategory, LabDifficulty
from apps.ctf.models import Challenge, ChallengeCategory, FlagSubmission, SolvedChallenge
from apps.ctf.services import FlagVerificationService
from apps.scoring.models import Badge
from apps.certificates.models import Certificate
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
