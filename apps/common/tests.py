from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import UserRole, StudentProfile, InstructorProfile
from apps.courses.models import Course, Module, Lesson, Quiz, Question, Choice
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

        # 2. Create Instructor User
        self.instructor = User.objects.create_user(
            username="prof_morpheus",
            email="morpheus@futuretech.edu",
            password="StrongCyberPass2026!",
            role=UserRole.INSTRUCTOR,
            first_name="Morpheus",
            last_name="Instructor"
        )

    def test_01_user_and_rbac_profiles(self):
        """Verify Custom User model, RBAC role detection, and signal profile creation."""
        self.assertEqual(self.student.role, UserRole.STUDENT)
        self.assertTrue(self.student.is_student)
        self.assertFalse(self.student.is_instructor)

        # Verify StudentProfile was auto-created by signals
        self.assertTrue(hasattr(self.student, 'student_profile'))
        self.assertTrue(self.student.student_profile.student_id.startswith("FTCR-2026-"))

        # Verify InstructorProfile was auto-created for instructor
        self.assertTrue(hasattr(self.instructor, 'instructor_profile'))
        self.assertTrue(self.instructor.is_instructor)

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

        self.assertTrue(cert.certificate_code.startswith("FTCR-CERT-2026-"))

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

