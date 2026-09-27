import os
from io import BytesIO
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import User, RoleChoices, StudentProfile, InstructorProfile, AdminProfile
from apps.courses.models import Course, CourseModule, Lesson, CourseCategory, CourseLevel, CourseStatus, LessonType, CourseResource
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress
from apps.progress.services import ProgressCalculationService
from apps.core.validators import validate_resource_file


class UserAuthTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.email = "student.test@futuretech.edu"
        self.password = "StrongPassword2026!"

    def test_user_registration_and_profile_signal(self):
        """Test user creation with email and verify automatic StudentProfile generation via signals."""
        user = User.objects.create_user(
            email=self.email,
            password=self.password,
            username="student_test",
            role=RoleChoices.STUDENT,
            first_name="Neo",
            last_name="Anderson"
        )
        self.assertEqual(user.email, self.email)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.role, RoleChoices.STUDENT)
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_instructor)

        # Signal should create StudentProfile
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())

    def test_email_login_success_and_failure(self):
        """Verify authentication operates on email as the username field."""
        user = User.objects.create_user(
            email=self.email,
            password=self.password,
            username="student_test"
        )

        # Successful login using email
        login_success = self.client.login(email=self.email, password=self.password)
        self.assertTrue(login_success)

        # Invalid password login
        self.client.logout()
        login_fail = self.client.login(email=self.email, password="WrongPassword123!")
        self.assertFalse(login_fail)

    def test_instructor_and_admin_profiles(self):
        """Test profile creation for instructors and administrators."""
        instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password=self.password,
            role=RoleChoices.INSTRUCTOR
        )
        self.assertTrue(InstructorProfile.objects.filter(user=instructor).exists())

        admin = User.objects.create_user(
            email="admin@futuretech.edu",
            password=self.password,
            role=RoleChoices.ACADEMY_ADMIN
        )
        self.assertTrue(AdminProfile.objects.filter(user=admin).exists())


class RBACPermissionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            password="Password123!",
            role=RoleChoices.STUDENT
        )
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password="Password123!",
            role=RoleChoices.INSTRUCTOR
        )
        self.admin = User.objects.create_user(
            email="admin@futuretech.edu",
            password="Password123!",
            role=RoleChoices.ACADEMY_ADMIN
        )

    def test_student_restricted_from_instructor_and_admin_panels(self):
        """Students must receive 403 Forbidden when attempting to access instructor or admin panels."""
        self.client.force_login(self.student)

        # Instructor dashboard
        res_instructor = self.client.get(reverse('instructor-dashboard'))
        self.assertEqual(res_instructor.status_code, 403)

        # Admin dashboard
        res_admin = self.client.get(reverse('academy-admin-dashboard'))
        self.assertEqual(res_admin.status_code, 403)

    def test_instructor_access_to_management(self):
        """Instructors can access the instructor dashboard and course creation wizard."""
        self.client.force_login(self.instructor)

        res_instructor = self.client.get(reverse('instructor-dashboard'))
        self.assertEqual(res_instructor.status_code, 200)

        res_create = self.client.get(reverse('instructor-course-step1'))
        self.assertEqual(res_create.status_code, 200)

        # Instructor cannot access academy admin panel
        res_admin = self.client.get(reverse('academy-admin-dashboard'))
        self.assertEqual(res_admin.status_code, 403)

    def test_admin_access_to_all_dashboards(self):
        """Academy admins have full access across student, instructor, and admin consoles."""
        self.client.force_login(self.admin)

        res_admin = self.client.get(reverse('academy-admin-dashboard'))
        self.assertEqual(res_admin.status_code, 200)

        res_instructor = self.client.get(reverse('instructor-dashboard'))
        self.assertEqual(res_instructor.status_code, 200)


class CourseManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password="Password123!",
            role=RoleChoices.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            password="Password123!",
            role=RoleChoices.STUDENT
        )

    def test_course_draft_and_publish_workflow(self):
        """Verify draft courses remain hidden from catalog until explicitly published."""
        course = Course.objects.create(
            title="Advanced Binary Exploitation",
            slug="advanced-binary-exploitation",
            short_description="Memory corruption and ROP chain exploitation.",
            description="Deep exploration of buffer overflows and DEP/ASLR bypasses.",
            created_by=self.instructor,
            status=CourseStatus.DRAFT
        )

        # DRAFT course does not appear in public list view
        res = self.client.get(reverse('course-list'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "Advanced Binary Exploitation")

        # Instructor toggles publish
        self.client.force_login(self.instructor)
        toggle_res = self.client.post(reverse('instructor-course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(toggle_res.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, CourseStatus.PUBLISHED)

        # Now course appears in public list view
        res = self.client.get(reverse('course-list'))
        self.assertContains(res, "Advanced Binary Exploitation")

    def test_module_and_lesson_hierarchy(self):
        """Verify ordering and hierarchy of modules and lessons within a course."""
        course = Course.objects.create(
            title="Linux Hardening",
            slug="linux-hardening",
            short_description="Security architecture of Linux kernels.",
            description="SELinux, AppArmor, auditd and PAM.",
            created_by=self.instructor,
            status=CourseStatus.PUBLISHED
        )

        mod1 = CourseModule.objects.create(
            course=course,
            title="Module 1: Kernel Hardening",
            slug="kernel-hardening",
            order=1
        )
        lesson1 = Lesson.objects.create(
            module=mod1,
            title="Sysctl Security Parameters",
            slug="sysctl-parameters",
            content="Configuring `/etc/sysctl.d/99-security.conf`",
            order=1
        )
        lesson2 = Lesson.objects.create(
            module=mod1,
            title="Kernel Module Blacklisting",
            slug="kernel-module-blacklisting",
            content="Disabling firewire, cramfs, and unused filesystems.",
            order=2
        )

        self.assertEqual(course.total_lessons_count, 2)
        self.assertEqual(mod1.lessons.count(), 2)


class EnrollmentAndProgressTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password="Password123!",
            role=RoleChoices.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            password="Password123!",
            role=RoleChoices.STUDENT
        )

        self.course = Course.objects.create(
            title="Network Defense Fundamentals",
            slug="network-defense-fundamentals",
            short_description="Firewalls, IDS/IPS, and packet filtering.",
            description="Mastering Wireshark, Snort, and iptables.",
            created_by=self.instructor,
            status=CourseStatus.PUBLISHED
        )

        self.module = CourseModule.objects.create(
            course=self.course,
            title="Packet Inspection",
            slug="packet-inspection",
            order=1
        )

        self.lesson1 = Lesson.objects.create(
            module=self.module,
            title="Wireshark Filtering",
            slug="wireshark-filtering",
            content="BPF syntax and display filters.",
            order=1,
            is_published=True
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module,
            title="Snort Rule Writing",
            slug="snort-rule-writing",
            content="Alert tcp any any -> any 80.",
            order=2,
            is_published=True
        )

    def test_student_enrollment_and_duplicate_prevention(self):
        """Students can enroll, and duplicate enrollment raises IntegrityError."""
        self.client.force_login(self.student)
        res = self.client.post(reverse('enroll-course', kwargs={'slug': self.course.slug}))
        self.assertEqual(res.status_code, 302)

        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)
        self.assertEqual(enrollment.progress_percentage, 0.0)

        # Duplicate enrollment constraint test
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(student=self.student, course=self.course)

    def test_lesson_completion_and_percentage_calculation(self):
        """
        Completing lessons must accurately calculate progress percentage:
        1 of 2 lessons = 50.0%
        2 of 2 lessons = 100.0% (auto-updating Enrollment status to COMPLETED)
        """
        enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        self.assertEqual(enrollment.progress_percentage, 0.0)

        # 1. Complete Lesson 1
        progress1 = LessonProgress.objects.create(student=self.student, lesson=self.lesson1)
        progress1.mark_completed()

        enrollment.refresh_from_db()
        self.assertEqual(float(enrollment.progress_percentage), 50.0)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)

        # 2. Complete Lesson 2 (Reaches 100%)
        progress2 = LessonProgress.objects.create(student=self.student, lesson=self.lesson2)
        progress2.mark_completed()

        enrollment.refresh_from_db()
        self.assertEqual(float(enrollment.progress_percentage), 100.0)
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)

        # 3. Untoggle / Mark Incomplete (Should drop back to 50%)
        self.client.force_login(self.student)
        toggle_res = self.client.post(reverse('toggle-lesson-complete', kwargs={'lesson_id': self.lesson2.id}))
        self.assertEqual(toggle_res.status_code, 302)

        enrollment.refresh_from_db()
        self.assertEqual(float(enrollment.progress_percentage), 50.0)
        self.assertEqual(enrollment.status, EnrollmentStatus.ACTIVE)

    def test_htmx_toggle_completion_button(self):
        """HTMX request to toggle completion returns the partial button HTML component."""
        self.client.force_login(self.student)
        Enrollment.objects.create(student=self.student, course=self.course)

        # HTMX header request
        res = self.client.post(
            reverse('toggle-lesson-complete', kwargs={'lesson_id': self.lesson1.id}),
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Completed")
        self.assertContains(res, "hx-post")


class SecurityFileValidationTestCase(TestCase):
    def test_valid_file_passes_validation(self):
        """Legitimate PDF or document files pass validation."""
        valid_pdf = SimpleUploadedFile("lab_guide.pdf", b"%PDF-1.4 simulated pdf data", content_type="application/pdf")
        validated = validate_resource_file(valid_pdf)
        self.assertEqual(validated.name, "lab_guide.pdf")

    def test_dangerous_executable_extensions_blocked(self):
        """Executables, shell scripts, python scripts and binaries must be rejected with ValidationError."""
        dangerous_files = [
            ("exploit.exe", b"MZ\x90\x00", "application/x-dosexec"),
            ("backdoor.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh"),
            ("payload.bat", b"@echo off", "application/x-bat"),
            ("script.py", b"import os; os.system('ls')", "text/x-python"),
            ("shell.php", b"<?php system($_GET['c']); ?>", "application/x-php"),
            ("malware.elf", b"\x7fELF", "application/x-executable"),
            ("powershell.ps1", b"Invoke-Expression", "text/plain"),
        ]

        for filename, content, mime in dangerous_files:
            with self.subTest(filename=filename):
                file_obj = SimpleUploadedFile(filename, content, content_type=mime)
                with self.assertRaises(ValidationError) as ctx:
                    validate_resource_file(file_obj)
                self.assertIn("prohibited", str(ctx.exception).lower())

    def test_oversized_file_blocked(self):
        """Files exceeding the 25MB threshold must be rejected."""
        large_bytes = b"0" * (26 * 1024 * 1024)
        file_obj = SimpleUploadedFile("large_archive.zip", large_bytes, content_type="application/zip")
        with self.assertRaises(ValidationError) as ctx:
            validate_resource_file(file_obj)
        self.assertIn("exceeds the maximum allowed limit", str(ctx.exception))


class APITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password="Password123!",
            role=RoleChoices.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            password="Password123!",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="API Security & OAuth",
            slug="api-security-oauth",
            short_description="Securing REST APIs and token exchange.",
            description="JWT attacks, IDOR, and rate limiting.",
            created_by=self.instructor,
            status=CourseStatus.PUBLISHED
        )

    def test_courses_api_list_and_detail(self):
        """API endpoints for public courses return correct structured JSON data."""
        res = self.client.get(reverse('api-course-list'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('results', data)
        self.assertTrue(any(c['slug'] == self.course.slug for c in data['results']))

        detail_res = self.client.get(reverse('api-course-detail', kwargs={'slug': self.course.slug}))
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data['title'], "API Security & OAuth")

    def test_enrollments_api_requires_auth(self):
        """Enrollments API requires authentication (returns 401 or 403 for anonymous)."""
        res = self.client.get(reverse('api-enrollment-list'))
        self.assertIn(res.status_code, [401, 403])

        # Authenticated student can view enrollments
        self.client.force_login(self.student)
        res_auth = self.client.get(reverse('api-enrollment-list'))
        self.assertEqual(res_auth.status_code, 200)

    def test_platform_stats_api(self):
        """Platform statistics endpoint returns counts."""
        res = self.client.get(reverse('api-platform-stats'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('published_courses', data)
        self.assertIn('total_students', data)
        self.assertEqual(data['phase'], "Phase 1: E-Learning Foundation")


class ViewIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu",
            password="StrongPassword123!",
            role=RoleChoices.INSTRUCTOR,
            username="instructor_lead"
        )
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            password="StrongPassword123!",
            role=RoleChoices.STUDENT,
            username="student_cadet"
        )
        self.category = CourseCategory.objects.create(
            name="Cloud Security",
            slug="cloud-security"
        )
        self.course = Course.objects.create(
            title="AWS & Kubernetes Security",
            slug="aws-k8s-security",
            short_description="Hardening EKS, IAM, and container runtime security.",
            description="Complete Kubernetes threat matrix and admission controller security.",
            level=CourseLevel.ADVANCED,
            duration="10 Weeks",
            is_free=True,
            status=CourseStatus.PUBLISHED,
            created_by=self.instructor
        )
        self.course.categories.add(self.category)

        self.module = CourseModule.objects.create(
            course=self.course,
            title="Pod Security Standards",
            slug="pod-security-standards",
            order=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Implementing Kyverno Policies",
            slug="kyverno-policies",
            content="Writing declarative admission policies in YAML.",
            order=1,
            is_published=True
        )

    def test_registration_view(self):
        """Student can register via registration page."""
        res = self.client.get(reverse('register'))
        self.assertEqual(res.status_code, 200)

        post_data = {
            'email': 'newstudent@futuretech.edu',
            'username': 'newstudent',
            'first_name': 'Grace',
            'last_name': 'Hopper',
            'password': 'StrongPassword2026!',
            'password_confirm': 'StrongPassword2026!'
        }
        post_res = self.client.post(reverse('register'), post_data)
        self.assertEqual(post_res.status_code, 302)
        self.assertTrue(User.objects.filter(email='newstudent@futuretech.edu').exists())

    def test_course_list_filters(self):
        """Course catalog correctly filters by query, category, level, and price."""
        # Query match
        res_q = self.client.get(reverse('course-list') + '?q=Kubernetes')
        self.assertContains(res_q, "Kubernetes Security")

        # Category match
        res_cat = self.client.get(reverse('course-list') + '?category=cloud-security')
        self.assertContains(res_cat, "Kubernetes Security")

        # Level match
        res_lvl = self.client.get(reverse('course-list') + '?level=ADVANCED')
        self.assertContains(res_lvl, "Kubernetes Security")

        # Price match (free)
        res_free = self.client.get(reverse('course-list') + '?price=free')
        self.assertContains(res_free, "Kubernetes Security")

        # Non-matching query
        res_none = self.client.get(reverse('course-list') + '?q=QuantumComputing')
        self.assertNotContains(res_none, "Kubernetes Security")
        self.assertContains(res_none, "No courses match your query")


    def test_lesson_learn_view_access(self):
        """Non-enrolled student cannot access lesson, enrolled student can."""
        self.client.force_login(self.student)

        # Before enrollment: 404 (or restricted)
        res_before = self.client.get(
            reverse('lesson-learn', kwargs={'course_slug': self.course.slug, 'lesson_slug': self.lesson.slug})
        )
        self.assertEqual(res_before.status_code, 404)

        # Enroll student
        Enrollment.objects.create(student=self.student, course=self.course)

        # After enrollment: 200 OK
        res_after = self.client.get(
            reverse('lesson-learn', kwargs={'course_slug': self.course.slug, 'lesson_slug': self.lesson.slug})
        )
        self.assertEqual(res_after.status_code, 200)
        self.assertContains(res_after, "Implementing Kyverno Policies")

    def test_instructor_course_wizard_step_flow(self):
        """Verify instructor 5-step course creation wizard workflow."""
        self.client.force_login(self.instructor)

        # Step 1: Create Course
        step1_data = {
            'title': 'DevSecOps & CI/CD Security',
            'slug': 'devsecops-cicd-security',
            'short_description': 'SAST, DAST, and container scanning in GitLab CI.',
            'description': 'Securing pipelines with Trivy, Semgrep, and Sigstore.',
            'level': 'INTERMEDIATE',
            'duration': '8 Weeks',
            'language': 'English',
            'price': '0.00',
            'is_free': True
        }
        res_step1 = self.client.post(reverse('instructor-course-step1'), step1_data)
        self.assertEqual(res_step1.status_code, 302)

        new_course = Course.objects.get(slug='devsecops-cicd-security')
        self.assertEqual(new_course.status, CourseStatus.DRAFT)

        # Step 2: Add Module
        step2_data = {
            'title': 'Pipeline Scanning',
            'slug': 'pipeline-scanning',
            'order': 1,
            'estimated_hours': 12,
            'description': 'Static analysis and secrets detection.'
        }
        res_step2 = self.client.post(
            reverse('instructor-course-step2', kwargs={'slug': new_course.slug}),
            step2_data
        )
        self.assertEqual(res_step2.status_code, 302)
        new_module = CourseModule.objects.get(course=new_course, slug='pipeline-scanning')
        self.assertEqual(new_module.order, 1)

        # Step 3: Add Lesson
        step3_data = {
            'module_id': str(new_module.id),
            'title': 'Semgrep Rules',
            'slug': 'semgrep-rules',
            'lesson_type': 'ARTICLE',
            'content': 'Configuring Semgrep in GitHub Actions.',
            'order': 1,
            'estimated_minutes': 45,
            'is_published': True
        }
        res_step3 = self.client.post(
            reverse('instructor-course-step3', kwargs={'slug': new_course.slug}),
            step3_data
        )
        self.assertEqual(res_step3.status_code, 302)
        new_lesson = Lesson.objects.get(module=new_module, slug='semgrep-rules')
        self.assertEqual(new_lesson.title, 'Semgrep Rules')

        # Step 5: Review & Publish Toggle
        res_publish = self.client.post(
            reverse('instructor-course-publish', kwargs={'slug': new_course.slug})
        )
        self.assertEqual(res_publish.status_code, 302)
        new_course.refresh_from_db()
        self.assertEqual(new_course.status, CourseStatus.PUBLISHED)

