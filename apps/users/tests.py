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
        self.assertTrue(user.student_profile.student_id.startswith("MEL-"))
        self.assertEqual(user.student_profile.student_id, user.account_id)
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
            'terms_accepted': True,
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


from decimal import Decimal
from apps.courses.models import Course, Subject, Enrollment
from apps.partner.models import Institution, PartnerStudent, PartnerApplication
from apps.billing.models import SubscriptionPlan, UserSubscription, Payment
from apps.billing.services import calculate_partner_revenue
from apps.courses.services.access import can_access_course, can_take_course_exam, can_claim_certificate


class MELAccountRedesignAcceptanceTests(TestCase):
    """
    Acceptance test suite strictly validating all 19 Acceptance Tests
    specified in the MEL Account Architecture Redesign.
    """
    def setUp(self):
        ensure_default_groups()
        self.client = Client()

        # Users
        self.student = User.objects.create_user(
            username='student_test',
            email='student@mel.edu.mm',
            password='Password123!',
            role=UserRole.STUDENT,
        )
        self.teacher = User.objects.create_user(
            username='teacher_test',
            email='teacher@mel.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        # Teacher starts verified for instructor tests where specified
        self.teacher.teacher_profile.is_verified = True
        self.teacher.teacher_profile.level = 'associate'
        self.teacher.teacher_profile.save()

        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@mel.edu.mm',
            password='Password123!',
            role=UserRole.ADMIN,
        )

        # Subject & Course
        self.subject = Subject.objects.create(title='Cyber Defense', slug='cyber-defense')
        self.course = Course.objects.create(
            title='Network Defense Fundamentals',
            slug='network-defense-fundamentals',
            subject=self.subject,
            owner=self.teacher,
            price=Decimal('50000.00'),
            currency='MMK',
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
            exam_required=True,
            exam_voucher_price=Decimal('10000.00'),
        )

    def test_01_anonymous_visitor_sees_public_landing_page(self):
        """TEST 1: Anonymous visitor: / -> Public MEL landing page."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'MYANMAR E-LEARNING')

    def test_02_student_redirected_to_student_dashboard(self):
        """TEST 2: Student login / accessing / -> Student Dashboard, NOT public landing page."""
        self.client.login(username='student_test', password='Password123!')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_03_teacher_redirected_to_teaching_dashboard(self):
        """TEST 3: Teacher login / accessing / -> Teaching Dashboard."""
        self.client.login(username='teacher_test', password='Password123!')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('teacher-dashboard'))

    def test_04_multirole_redirected_to_last_selected_mode(self):
        """TEST 4: Student + Teacher: -> last selected mode."""
        user = User.objects.create_user(
            username='dual_user',
            email='dual@mel.edu.mm',
            password='Password123!',
            role=UserRole.STUDENT,
        )
        user.add_role('instructor')
        user.teacher_profile.is_verified = True
        user.teacher_profile.save()

        # In student mode -> dashboard
        user.active_mode = ActiveMode.STUDENT
        user.save(update_fields=['active_mode'])
        self.client.login(username='dual_user', password='Password123!')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

        # Switch to instructor mode -> teacher dashboard
        user.active_mode = ActiveMode.INSTRUCTOR
        user.save(update_fields=['active_mode'])
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('teacher-dashboard'))

    def test_05_student_access_to_partner_denied(self):
        """TEST 5: Student attempts: /partner/ or /partner/dashboard/ -> denied."""
        self.client.login(username='student_test', password='Password123!')
        resp = self.client.get('/partner/')
        self.assertEqual(resp.status_code, 302)
        # Redirected safely away from partner portal
        self.assertNotEqual(resp.url, '/partner/')

    def test_06_teacher_applies_become_instructor(self):
        """TEST 6: Teacher applies: Become an Instructor -> application created."""
        student_applicant = User.objects.create_user(
            username='applicant_student',
            email='applicant@mel.edu.mm',
            password='Password123!',
            role=UserRole.STUDENT,
        )
        self.client.login(username='applicant_student', password='Password123!')
        resp = self.client.post(reverse('apply-instructor'), {
            'department': 'School of Computing',
            'title': 'Assistant Lecturer',
            'target_subjects': 'Python, Networking',
            'qualifications': 'B.C.Sc',
            'teaching_experience': '2 years tutoring',
            'terms_accepted': True,
        })
        self.assertEqual(resp.status_code, 302)
        from apps.users.models import InstructorApplication
        app = InstructorApplication.objects.filter(user=student_applicant).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, InstructorApplication.Status.PENDING)

    def test_07_teacher_without_approval_cannot_publish_official_course(self):
        """TEST 7: Teacher without approval: -> cannot publish official instructor course."""
        unverified_teacher = User.objects.create_user(
            username='unverified_teacher',
            email='unverified@mel.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        unverified_teacher.teacher_profile.is_verified = False
        unverified_teacher.teacher_profile.save()

        course = Course.objects.create(
            title='Draft Teacher Course',
            slug='draft-teacher-course',
            subject=self.subject,
            owner=unverified_teacher,
            status=Course.Status.DRAFT,
        )
        self.assertFalse(course.can_publish(unverified_teacher))

    def test_08_approved_associate_instructor_public_profile_allowed(self):
        """TEST 8: Approved Associate Instructor: -> public instructor profile allowed. Unverified -> 404."""
        # Verified instructor profile accessible
        resp = self.client.get(reverse('public-instructor-profile', kwargs={'username': self.teacher.username}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Associate Instructor')

        # Unverified teacher profile raises 404
        unverified = User.objects.create_user(
            username='secret_teacher',
            email='secret@mel.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        unverified.teacher_profile.is_verified = False
        unverified.teacher_profile.save()
        resp_unverified = self.client.get(reverse('public-instructor-profile', kwargs={'username': unverified.username}))
        self.assertEqual(resp_unverified.status_code, 404)

    def test_09_teacher_applies_for_partner(self):
        """TEST 9: Teacher applies for Partner: -> Partner application created."""
        self.client.login(username='teacher_test', password='Password123!')
        resp = self.client.post(reverse('partner-apply'), {
            'organization_name': 'Yangon IT Academy',
            'institution_type': 'training_center',
            'country': 'Myanmar',
            'city': 'Yangon',
            'contact_person_name': 'Prof. Teacher',
            'contact_email': 'contact@yita.edu.mm',
        })
        self.assertEqual(resp.status_code, 302)
        app = PartnerApplication.objects.filter(applicant=self.teacher).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.organization_name, 'Yangon IT Academy')
        self.assertEqual(app.status, PartnerApplication.Status.PENDING)

    def test_10_approved_partner_accesses_partner_portal(self):
        """TEST 10: Approved Partner: -> Partner Portal accessible."""
        app = PartnerApplication.objects.create(
            applicant=self.teacher,
            organization_name='Mandalay Tech Institute',
            contact_email='info@mti.edu.mm',
            status=PartnerApplication.Status.PENDING,
        )
        inst = app.approve(reviewed_by=self.admin)
        self.assertTrue(self.teacher.is_partner)

        self.client.login(username='teacher_test', password='Password123!')
        resp = self.client.get(reverse('partner-portal'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mandalay Tech Institute')

    def test_11_partner_adds_existing_mel_student(self):
        """TEST 11: Partner adds existing MEL student: -> invitation sent (status=pending)."""
        app = PartnerApplication.objects.create(
            applicant=self.teacher,
            organization_name='Apex College',
            contact_email='info@apex.edu.mm',
        )
        inst = app.approve(reviewed_by=self.admin)

        self.client.login(username='teacher_test', password='Password123!')
        resp = self.client.post(reverse('partner-invite-student'), {
            'institution_id': inst.id,
            'identifier': self.student.account_id,
            'class_group': 'Batch 2026-A',
            'invitation_note': 'Welcome to Apex College.',
        })
        self.assertEqual(resp.status_code, 302)

        p_student = PartnerStudent.objects.filter(institution=inst, student=self.student).first()
        self.assertIsNotNone(p_student)
        self.assertEqual(p_student.status, PartnerStudent.Status.PENDING)

    def test_12_student_accepts_partner_invitation(self):
        """TEST 12: Student accepts: -> student linked to Partner (status=active)."""
        app = PartnerApplication.objects.create(
            applicant=self.teacher,
            organization_name='Apex College',
            contact_email='info@apex.edu.mm',
        )
        inst = app.approve(reviewed_by=self.admin)
        invitation = PartnerStudent.objects.create(
            institution=inst,
            student=self.student,
            status=PartnerStudent.Status.PENDING,
        )

        self.client.login(username='student_test', password='Password123!')
        resp = self.client.post(reverse('partner-invitation-accept', kwargs={'pk': invitation.id}))
        self.assertEqual(resp.status_code, 302)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, PartnerStudent.Status.ACTIVE)
        self.assertIsNotNone(invitation.responded_at)

    def test_13_student_declines_partner_invitation(self):
        """TEST 13: Student declines: -> no active Partner relationship (status=declined)."""
        app = PartnerApplication.objects.create(
            applicant=self.teacher,
            organization_name='Apex College',
            contact_email='info@apex.edu.mm',
        )
        inst = app.approve(reviewed_by=self.admin)
        invitation = PartnerStudent.objects.create(
            institution=inst,
            student=self.student,
            status=PartnerStudent.Status.PENDING,
        )

        self.client.login(username='student_test', password='Password123!')
        resp = self.client.post(reverse('partner-invitation-decline', kwargs={'pk': invitation.id}))
        self.assertEqual(resp.status_code, 302)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, PartnerStudent.Status.DECLINED)

    def test_14_partner_student_buys_partner_course_partner_pricing(self):
        """TEST 14: Partner student buys/joins partner course: -> configured partner pricing applies."""
        inst = Institution.objects.create(
            name='National Tech University',
            slug='ntu',
            contact_person=self.teacher,
            is_verified=True,
        )
        partner_course = Course.objects.create(
            title='NTU Software Engineering',
            slug='ntu-software-engineering',
            subject=self.subject,
            owner=self.teacher,
            partner_institution=inst,
            price=Decimal('100000.00'),
            partner_price=Decimal('40000.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )

        # Before active affiliation: standard list price applies
        price_info = partner_course.get_effective_price(self.student)
        self.assertEqual(price_info['final_price'], Decimal('100000.00'))

        # Once student accepts invitation and becomes active: partner price applies
        PartnerStudent.objects.create(
            institution=inst,
            student=self.student,
            status=PartnerStudent.Status.ACTIVE,
        )
        affil_price_info = partner_course.get_effective_price(self.student)
        self.assertEqual(affil_price_info['final_price'], Decimal('40000.00'))
        self.assertEqual(affil_price_info['pricing_tier'], 'partner')

    def test_15_partner_course_revenue_share_calculated(self):
        """TEST 15: Partner course revenue: -> configured revenue share calculated."""
        inst = Institution.objects.create(
            name='Horizon Academy',
            slug='horizon',
            contact_person=self.teacher,
            is_verified=True,
        )
        partner_course = Course.objects.create(
            title='Horizon Web Development',
            slug='horizon-web-development',
            subject=self.subject,
            owner=self.teacher,
            partner_institution=inst,
            price=Decimal('100000.00'),
            partner_revenue_share_pct=Decimal('80.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )
        partner_amt, plat_amt, p_pct, pl_pct = calculate_partner_revenue(partner_course, Decimal('100000.00'))
        self.assertEqual(p_pct, Decimal('80.00'))
        self.assertEqual(partner_amt, Decimal('80000.00'))
        self.assertEqual(plat_amt, Decimal('20000.00'))

    def test_16_student_starter_free_learning_no_automatic_exam(self):
        """TEST 16: Student Starter: -> free learning access, no automatic official exam/certificate access."""
        free_course = Course.objects.create(
            title='Free Linux Basics',
            slug='free-linux-basics',
            subject=self.subject,
            owner=self.admin,
            price=Decimal('0.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
            exam_required=True,
        )
        Enrollment.objects.create(course=free_course, student=self.student, status=Enrollment.Status.ACTIVE)

        # Learning access allowed
        self.assertTrue(can_access_course(self.student, free_course))

        # Paid course with official exam: Starter student cannot take exam without paying
        Enrollment.objects.create(course=self.course, student=self.student, status=Enrollment.Status.ACTIVE)
        can_exam, reason = can_take_course_exam(self.student, self.course)
        self.assertFalse(can_exam)

    def test_17_student_standard_eligible_courses_and_exams(self):
        """TEST 17: Student Standard: -> eligible Standard courses and eligible exams/certificates."""
        SubscriptionPlan.ensure_default_plans()
        standard_plan = SubscriptionPlan.objects.get(plan_type='standard')
        from django.utils import timezone
        UserSubscription.objects.create(
            user=self.student,
            plan=standard_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
        )

        std_course = Course.objects.create(
            title='Standard Cyber Defense',
            slug='standard-cyber-defense',
            subject=self.subject,
            owner=self.teacher,
            price=Decimal('30000.00'),
            is_premium=False,
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )
        Enrollment.objects.create(course=std_course, student=self.student, status=Enrollment.Status.ACTIVE)

        self.assertTrue(can_access_course(self.student, std_course))
        can_exam, _ = can_take_course_exam(self.student, std_course)
        self.assertTrue(can_exam)

    def test_18_student_premium_courses_and_features(self):
        """TEST 18: Student Premium: -> Premium courses/labs/features."""
        SubscriptionPlan.ensure_default_plans()
        premium_plan = SubscriptionPlan.objects.get(plan_type='premium')
        from django.utils import timezone
        UserSubscription.objects.create(
            user=self.student,
            plan=premium_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
        )

        prem_course = Course.objects.create(
            title='Advanced Exploit Development',
            slug='advanced-exploit-dev',
            subject=self.subject,
            owner=self.teacher,
            price=Decimal('150000.00'),
            is_premium=True,
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )
        Enrollment.objects.create(course=prem_course, student=self.student, status=Enrollment.Status.ACTIVE)

        self.assertTrue(can_access_course(self.student, prem_course))
        can_exam, _ = can_take_course_exam(self.student, prem_course)
        self.assertTrue(can_exam)

    def test_19_course_specific_exam_fee_rules_authoritative(self):
        """TEST 19: Student membership does NOT automatically unlock every course exam/certificate. Course-specific rules remain authoritative."""
        SubscriptionPlan.ensure_default_plans()
        premium_plan = SubscriptionPlan.objects.get(plan_type='premium')
        from django.utils import timezone
        UserSubscription.objects.create(
            user=self.student,
            plan=premium_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
        )

        # Course explicitly requires a separate exam voucher fee
        cert_course = Course.objects.create(
            title='Certified Ethical Hacker Exam Track',
            slug='ceh-exam-track',
            subject=self.subject,
            owner=self.teacher,
            price=Decimal('120000.00'),
            is_premium=True,
            exam_required=True,
            exam_voucher_price=Decimal('35000.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )
        Enrollment.objects.create(course=cert_course, student=self.student, status=Enrollment.Status.ACTIVE)

        # Even though user is Premium, course-specific separate exam fee rule requires payment!
        can_exam, reason = can_take_course_exam(self.student, cert_course)
        self.assertFalse(can_exam)
        self.assertIn("Course-specific exam rules are authoritative", reason)

        # Once student pays exam voucher fee: exam is unlocked!
        Payment.objects.create(
            student=self.student,
            course=cert_course,
            amount=Decimal('35000.00'),
            payment_type=Payment.PaymentType.EXAM_VOUCHER,
            status=Payment.Status.SUCCESS,
        )
        can_exam_after, _ = can_take_course_exam(self.student, cert_course)
        self.assertTrue(can_exam_after)




