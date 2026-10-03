from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import Group

from .models import User, UserRole, ActiveMode, StudentProfile
from .services import (
    generate_unique_account_id,
    create_user_account,
    authenticate_universal,
    switch_user_mode,
    ensure_default_groups,
)


class UserAccountModelTests(TestCase):
    def setUp(self):
        ensure_default_groups()

    def test_account_id_generation_format(self):
        account_id = generate_unique_account_id()
        self.assertTrue(account_id.startswith("MEL-"))
        self.assertEqual(len(account_id), 12)
        digits = account_id.split("-")[1]
        self.assertTrue(digits.isdigit())
        self.assertEqual(len(digits), 8)

    def test_create_user_account_creates_student_profile_and_id(self):
        user = create_user_account(
            username="student_leo",
            email="leo@example.com",
            password="StrongPassword123!",
            first_name="Leo",
            last_name="Learner",
            role=UserRole.STUDENT
        )
        self.assertIsNotNone(user.account_id)
        self.assertTrue(user.account_id.startswith("MEL-"))
        self.assertEqual(user.role, UserRole.STUDENT)
        self.assertEqual(user.active_mode, ActiveMode.STUDENT)
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_teacher)
        self.assertTrue(hasattr(user, 'student_profile'))
        self.assertTrue(user.student_profile.student_id.startswith("MEL-2026-"))
        self.assertTrue(user.groups.filter(name='Student').exists())

    def test_teacher_creation_assigns_instructor_group_and_mode(self):
        teacher = create_user_account(
            username="teacher_sarah",
            email="sarah@example.com",
            password="StrongPassword123!",
            first_name="Sarah",
            last_name="Instructor",
            role=UserRole.TEACHER
        )
        self.assertEqual(teacher.role, UserRole.TEACHER)
        self.assertEqual(teacher.active_mode, ActiveMode.INSTRUCTOR)
        self.assertTrue(teacher.is_teacher)
        self.assertTrue(teacher.is_active_instructor_mode)
        self.assertTrue(teacher.groups.filter(name='Instructor').exists())

    def test_dual_mode_switching(self):
        teacher = create_user_account(
            username="dual_mode_teacher",
            email="dual@example.com",
            password="StrongPassword123!",
            role=UserRole.TEACHER
        )
        self.assertEqual(teacher.active_mode, ActiveMode.INSTRUCTOR)

        # Switch to Student Mode
        switch_user_mode(teacher, ActiveMode.STUDENT)
        teacher.refresh_from_db()
        self.assertEqual(teacher.active_mode, ActiveMode.STUDENT)
        self.assertFalse(teacher.is_active_instructor_mode)
        self.assertTrue(teacher.is_teacher)  # Credentials remain intact

        # Switch back to Instructor Mode
        switch_user_mode(teacher, ActiveMode.INSTRUCTOR)
        teacher.refresh_from_db()
        self.assertEqual(teacher.active_mode, ActiveMode.INSTRUCTOR)
        self.assertTrue(teacher.is_active_instructor_mode)

    def test_student_cannot_switch_to_instructor_mode(self):
        student = create_user_account(
            username="regular_student",
            email="regular@example.com",
            password="StrongPassword123!",
            role=UserRole.STUDENT
        )
        with self.assertRaises(Exception):
            switch_user_mode(student, ActiveMode.INSTRUCTOR)


class UniversalAuthenticationTests(TestCase):
    def setUp(self):
        self.password = "Secur3Pass2026!"
        self.user = create_user_account(
            username="universal_user",
            email="universal@example.com",
            password=self.password,
            role=UserRole.STUDENT
        )

    def test_authenticate_by_account_id(self):
        auth_user = authenticate_universal(self.user.account_id, self.password)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user.id, self.user.id)

    def test_authenticate_by_email(self):
        auth_user = authenticate_universal(self.user.email, self.password)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user.id, self.user.id)

    def test_authenticate_by_username(self):
        auth_user = authenticate_universal(self.user.username, self.password)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user.id, self.user.id)

    def test_authenticate_invalid_credentials(self):
        self.assertIsNone(authenticate_universal(self.user.username, "WrongPass"))
        self.assertIsNone(authenticate_universal("MEL-99999999", self.password))


class UserModeSwitchingViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = create_user_account(
            username="view_teacher",
            email="vt@example.com",
            password="TeacherPass2026!",
            role=UserRole.TEACHER
        )

    def test_teacher_can_switch_mode_via_http_post(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('switch-user-mode'), {'mode': 'student'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.active_mode, ActiveMode.STUDENT)

        # Switch back
        response = self.client.post(reverse('switch-user-mode'), {'mode': 'instructor'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('teacher-dashboard'))

        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.active_mode, ActiveMode.INSTRUCTOR)


class UserRESTAPITests(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.password = "ApiTestPass123!"
        self.user = create_user_account(
            username="api_user",
            email="api@example.com",
            password=self.password,
            role=UserRole.STUDENT
        )

    def test_api_register_endpoint(self):
        data = {
            "username": "new_api_student",
            "email": "newapi@example.com",
            "password": "SecurePassword123!",
            "first_name": "API",
            "last_name": "Student"
        }
        response = self.api_client.post(reverse('api-auth-register'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("account_id", response.data["user"])
        self.assertTrue(response.data["user"]["account_id"].startswith("MEL-"))

    def test_api_login_by_account_id(self):
        data = {
            "identifier": self.user.account_id,
            "password": self.password
        }
        response = self.api_client.post(reverse('api-auth-login'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], self.user.username)

    def test_api_login_by_email(self):
        data = {
            "identifier": self.user.email,
            "password": self.password
        }
        response = self.api_client.post(reverse('api-auth-login'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["id"], str(self.user.id))

    def test_api_profile_authenticated(self):
        self.api_client.force_authenticate(user=self.user)
        response = self.api_client.get(reverse('api-auth-profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["account_id"], self.user.account_id)
        self.assertIn("student_profile", response.data)


class UnifiedProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "Secr3tP@ssword!"
        self.student = User.objects.create_user(
            username="unified_student",
            email="ustudent@example.com",
            password=self.password,
            role=UserRole.STUDENT,
            first_name="Mg",
            last_name="Aung",
        )
        self.teacher = User.objects.create_user(
            username="unified_teacher",
            email="uteacher@example.com",
            password=self.password,
            role=UserRole.TEACHER,
            first_name="Daw",
            last_name="Mya",
            is_active=True,
        )

    def test_student_can_view_and_update_unified_profile(self):
        self.client.login(username=self.student.username, password=self.password)
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.student.account_id)
        self.assertContains(resp, "Save Unified Profile")

        post_data = {
            'first_name': 'Mg Mg',
            'last_name': 'Aung',
            'phone_number': '09123456789',
            'bio': 'Passionate cyber and python learner.',
            'github_url': 'https://github.com/mgaung',
            'linkedin_url': 'https://linkedin.com/in/mgaung',
        }
        post_resp = self.client.post(reverse('profile'), post_data)
        self.assertEqual(post_resp.status_code, 302)

        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Mg Mg')
        self.assertEqual(self.student.phone_number, '09123456789')
        self.assertEqual(self.student.profile.bio, 'Passionate cyber and python learner.')
        self.assertEqual(self.student.student_profile.github_url, 'https://github.com/mgaung')

    def test_teacher_can_view_and_update_unified_profile(self):
        self.client.login(username=self.teacher.username, password=self.password)
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.teacher.account_id)
        self.assertContains(resp, "Academic Department")

        post_data = {
            'first_name': 'Daw Daw',
            'last_name': 'Mya',
            'phone_number': '09987654321',
            'bio': 'Senior computing lecturer with 10 years experience.',
            'department': 'Computer Science Department',
            'title': 'Senior Lecturer',
            'qualifications': 'M.Sc Computer Science',
        }
        post_resp = self.client.post(reverse('profile'), post_data)
        self.assertEqual(post_resp.status_code, 302)

        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, 'Daw Daw')
        self.assertEqual(self.teacher.teacher_profile.department, 'Computer Science Department')
        self.assertEqual(self.teacher.profile.title, 'Senior Lecturer')
        self.assertEqual(self.teacher.teacher_profile.qualifications, 'M.Sc Computer Science')


class TeacherImmediateSignInAndApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='sysadmin',
            email='admin@mel.edu.mm',
            password='AdminPass2026!'
        )

    def test_teacher_applicant_account_active_immediately_and_can_sign_in(self):
        # 1. Self-register as Teacher
        post_data = {
            'username': 'teacher_applicant_kyaw',
            'email': 'kyaw@mel.edu.mm',
            'first_name': 'Kyaw',
            'last_name': 'Kyaw',
            'role': 'teacher',
            'department': 'Data Science & AI',
            'title': 'Assistant Lecturer',
            'password1': 'TeacherPass2026!',
            'password2': 'TeacherPass2026!',
        }
        resp = self.client.post(reverse('register'), post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # 2. Check user is active and can sign in
        user = User.objects.get(username='teacher_applicant_kyaw')
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, UserRole.TEACHER)
        self.assertEqual(user.active_mode, ActiveMode.STUDENT)
        self.assertFalse(user.teacher_profile.is_verified)
        self.assertEqual(user.teacher_profile.department, 'Data Science & AI')

        # 3. Applicant can sign in immediately
        self.client.logout()
        login_success = self.client.login(username='teacher_applicant_kyaw', password='TeacherPass2026!')
        self.assertTrue(login_success)

        # 4. Admin approves instructor privileges via console
        self.client.logout()
        self.client.login(username='sysadmin', password='AdminPass2026!')
        approve_resp = self.client.post(reverse('console-user-approve-instructor', kwargs={'user_id': user.pk}))
        self.assertEqual(approve_resp.status_code, 302)

        user.refresh_from_db()
        self.assertTrue(user.teacher_profile.is_verified)
        self.assertTrue(user.groups.filter(name='Instructor').exists())

        # 5. Teacher can now switch to Instructor Mode
        self.client.logout()
        self.client.login(username='teacher_applicant_kyaw', password='TeacherPass2026!')
        switch_resp = self.client.post(reverse('switch-user-mode'), {'mode': 'instructor'})
        self.assertEqual(switch_resp.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.active_mode, ActiveMode.INSTRUCTOR)
        self.assertTrue(user.is_active_instructor_mode)

    def test_unverified_teacher_cannot_switch_to_instructor_mode_before_admin_approval(self):
        user = User.objects.create_user(
            username='unverified_teacher',
            email='unverified@mel.edu.mm',
            password='TestPass2026!',
            role=UserRole.TEACHER,
        )
        user.active_mode = ActiveMode.STUDENT
        user.save(update_fields=['active_mode'])
        user.teacher_profile.is_verified = False
        user.teacher_profile.save(update_fields=['is_verified'])

        self.client.login(username='unverified_teacher', password='TestPass2026!')
        switch_resp = self.client.post(reverse('switch-user-mode'), {'mode': 'instructor'}, follow=True)
        user.refresh_from_db()
        self.assertEqual(user.active_mode, ActiveMode.STUDENT)
        self.assertContains(switch_resp, "Instructor privileges must be verified")

    def test_admin_can_edit_user_instructor_rank_and_verification(self):
        student = User.objects.create_user(
            username='student_to_promote',
            email='promote_me@mel.edu.mm',
            password='TestPass2026!',
            role=UserRole.STUDENT,
        )
        self.client.login(username='sysadmin', password='AdminPass2026!')

        # Admin edits student into a Professional Instructor
        post_data = {
            'username': 'student_to_promote',
            'first_name': 'Ko',
            'last_name': 'Zaw',
            'email': 'promote_me@mel.edu.mm',
            'role': UserRole.TEACHER,
            'is_active': True,
            'is_verified_instructor': True,
            'instructor_level': 'professional',
            'department': 'Cyber Security & Forensics',
            'title': 'Senior Cyber Instructor',
            'qualifications': 'OSCP, CISSP, M.Sc InfoSec',
        }
        resp = self.client.post(reverse('console-user-edit', kwargs={'user_id': student.pk}), post_data)
        self.assertEqual(resp.status_code, 302)

        student.refresh_from_db()
        self.assertEqual(student.role, UserRole.TEACHER)
        self.assertTrue(student.teacher_profile.is_verified)
        self.assertEqual(student.teacher_profile.level, 'professional')
        self.assertEqual(student.teacher_profile.department, 'Cyber Security & Forensics')
        self.assertEqual(student.teacher_profile.title, 'Senior Cyber Instructor')
        self.assertTrue(student.groups.filter(name='Instructor').exists())

    def test_registration_pages_display_instant_sign_in_notice(self):
        resp_reg = self.client.get(reverse('register'))
        self.assertEqual(resp_reg.status_code, 200)
        self.assertContains(resp_reg, 'Instant Sign-in Enabled')
        self.assertNotContains(resp_reg, 'You will not be able to sign in until then')

        resp_pending = self.client.get(reverse('register-pending'))
        self.assertEqual(resp_pending.status_code, 200)
        self.assertContains(resp_pending, 'Instant Sign-In Enabled')
        self.assertNotContains(resp_pending, 'sign-in is disabled')

    def test_student_can_submit_instructor_application_and_admin_approves(self):
        from .models import InstructorApplication
        student = User.objects.create_user(
            username='aspiring_teacher',
            email='teacher_app@mel.edu.mm',
            password='TestPass2026!',
            role=UserRole.STUDENT,
        )
        self.client.login(username='aspiring_teacher', password='TestPass2026!')

        # Student accesses application page
        resp = self.client.get(reverse('apply-instructor'))
        self.assertEqual(resp.status_code, 200)

        # Student submits application
        resp = self.client.post(reverse('apply-instructor'), {
            'department': 'School of Computing',
            'title': 'AI Lecturer',
            'target_subjects': 'Python Programming, AI & ML',
            'qualifications': 'M.Sc Artificial Intelligence',
            'teaching_experience': '3 years university lecturing',
        })
        self.assertEqual(resp.status_code, 302)

        app = InstructorApplication.objects.filter(user=student).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, InstructorApplication.Status.PENDING)
        self.assertEqual(app.department, 'School of Computing')

        # Admin approves application via console user approval view
        self.client.login(username='sysadmin', password='AdminPass2026!')
        approve_resp = self.client.post(reverse('console-user-approve-instructor', kwargs={'user_id': student.pk}))
        self.assertEqual(approve_resp.status_code, 302)

        student.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(student.role, UserRole.TEACHER)
        self.assertTrue(student.teacher_profile.is_verified)
        self.assertEqual(app.status, InstructorApplication.Status.APPROVED)
        self.assertEqual(app.reviewed_by.username, 'sysadmin')


class MultiRoleArchitectureTests(TestCase):
    def setUp(self):
        ensure_default_groups()
        self.user = User.objects.create_user(
            username='multirole_user',
            email='multirole@mel.edu.mm',
            password='TestPassword2026!',
            role=UserRole.STUDENT,
        )

    def test_single_account_multiple_roles(self):
        # Starts as student
        self.assertTrue(self.user.has_role('student'))
        self.assertFalse(self.user.has_role('instructor'))
        self.assertFalse(self.user.has_role('partner'))
        self.assertIn(UserRole.STUDENT, self.user.roles)

        # Assign instructor role
        self.user.add_role('instructor')
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_role('instructor'))
        self.assertTrue(self.user.is_teacher)
        self.assertTrue(hasattr(self.user, 'teacher_profile'))
        self.assertTrue(self.user.groups.filter(name='Instructor').exists())

        # Assign partner role
        self.user.add_role('partner')
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_role('partner'))
        self.assertTrue(self.user.is_partner)
        self.assertTrue(self.user.groups.filter(name='Partner').exists())

        # Roles property returns all active roles
        active_roles = self.user.roles
        self.assertIn(UserRole.STUDENT, active_roles)
        self.assertIn(UserRole.TEACHER, active_roles)
        self.assertIn(UserRole.PARTNER, active_roles)

        # Remove partner role
        self.user.remove_role('partner')
        self.assertFalse(self.user.has_role('partner'))
        self.assertTrue(self.user.has_role('instructor'))
        self.assertTrue(self.user.has_role('student'))

    def test_teacher_profile_extended_fields(self):
        self.user.add_role('instructor')
        tp = self.user.teacher_profile
        tp.bio = "Senior Security Researcher & Cloud Architect"
        tp.website = "https://leotech.edu.mm"
        tp.github_url = "https://github.com/leophyoe"
        tp.linkedin_url = "https://linkedin.com/in/leophyoe"
        tp.save()

        tp.refresh_from_db()
        self.assertEqual(tp.bio, "Senior Security Researcher & Cloud Architect")
        self.assertEqual(tp.website, "https://leotech.edu.mm")
        self.assertEqual(tp.github_url, "https://github.com/leophyoe")



