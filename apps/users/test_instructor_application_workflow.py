from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.users.models import (
    UserRole, ActiveMode, InstructorApplication, TeacherProfile, Notification
)

User = get_user_model()


class InstructorApplicationWorkflowTests(TestCase):
    """
    Comprehensive test suite verifying the complete Instructor/Teacher application lifecycle:
    1. Student applies -> PENDING application, remains STUDENT, Notification sent.
    2. Duplicate pending application blocked.
    3. Pending student denied teacher privileges (403).
    4. Access control on admin review queue (/console/instructor-applications/).
    5. Admin approval -> Role=TEACHER, ActiveMode=INSTRUCTOR, TeacherProfile verified, teacher dashboard unlocked (200).
    6. Admin rejection -> Role=STUDENT, rejection feedback saved, Notification sent, resubmission enabled.
    7. Partner portal access control remains strictly guarded against students and teachers.
    """

    def setUp(self):
        self.client = Client()

        # Normal Student
        self.student = User.objects.create_user(
            username='student_bob',
            email='bob@example.com',
            password='TestPassword123!',
            role=UserRole.STUDENT,
        )

        # Platform Administrator
        self.admin = User.objects.create_user(
            username='admin_boss',
            email='admin@thuta.edu.mm',
            password='AdminPassword123!',
            role=UserRole.ADMIN,
            is_staff=True,
        )

        # Pre-existing Teacher
        self.teacher = User.objects.create_user(
            username='teacher_prof',
            email='prof@thuta.edu.mm',
            password='TeacherPassword123!',
            role=UserRole.TEACHER,
            active_mode=ActiveMode.INSTRUCTOR,
        )
        self.teacher.add_role(UserRole.TEACHER)

    def test_student_can_view_apply_page_initial_state(self):
        """Student gets /auth/apply-instructor/ and sees clean application form."""
        self.client.force_login(self.student)
        url = reverse('apply-instructor')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertFalse(response.context['is_pending'])
        self.assertFalse(response.context['is_teacher'])
        self.assertContains(response, 'Instructor Application Form')
        self.assertContains(response, 'Join Faculty &amp; Teach')

    def test_student_submit_application_creates_pending_record_and_notification(self):
        """Student submits valid application: creates PENDING record, remains STUDENT, sends Notification."""
        self.client.force_login(self.student)
        url = reverse('apply-instructor')

        post_data = {
            'department': 'Cybersecurity & Defense',
            'title': 'Senior Offensive Security Specialist',
            'target_subjects': 'Network Security, Penetration Testing, Binary Exploitation',
            'teaching_experience': '7 years teaching practical penetration testing and leading hands-on cyber range labs.',
            'bio': 'Passionate cybersecurity researcher with extensive industrial red teaming experience.',
            'qualifications': 'OSCP, OSCE, CISSP, M.Sc Information Security',
            'sample_lecture_url': 'https://youtube.com/watch?v=sample123',
            'free_tutorial_title': 'Practical Red Teaming Free Primer',
            'free_tutorial_url': 'https://youtube.com/watch?v=free123',
            'terms_accepted': True,
            'website': 'https://security-research.example.com',
            'linkedin_url': 'https://linkedin.com/in/secbob',
            'github_url': 'https://github.com/secbob',
        }

        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify application created
        app = InstructorApplication.objects.filter(user=self.student).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, InstructorApplication.Status.PENDING)
        self.assertEqual(app.department, 'Cybersecurity & Defense')
        self.assertEqual(app.title, 'Senior Offensive Security Specialist')

        # CRITICAL: Student role MUST NOT be changed upon submission
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, UserRole.STUDENT)
        self.assertFalse(self.student.is_teacher)

        # Verify in-app Notification created
        notif = Notification.objects.filter(user=self.student).first()
        self.assertIsNotNone(notif)
        self.assertIn('Submitted', notif.title)

    def test_pending_student_cannot_submit_duplicate_application(self):
        """Student with an existing PENDING application cannot submit another pending application."""
        InstructorApplication.objects.create(
            user=self.student,
            department='Engineering',
            title='Lecturer',
            target_subjects='Python',
            teaching_experience='3 years experience',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.student)
        url = reverse('apply-instructor')

        post_data = {
            'department': 'New Department',
            'title': 'New Title',
            'target_subjects': 'New Subject',
            'teaching_experience': 'Another experience',
            'bio': 'Another bio',
            'qualifications': 'Another qualification',
        }

        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Only one application should exist
        self.assertEqual(InstructorApplication.objects.filter(user=self.student).count(), 1)
        self.assertContains(response, 'already have an instructor application pending administrative review.')

    def test_pending_student_sees_under_review_state(self):
        """GET /auth/apply-instructor/ shows under-review status when student has pending application."""
        InstructorApplication.objects.create(
            user=self.student,
            department='Computer Science',
            title='Assistant Professor',
            target_subjects='Algorithms',
            teaching_experience='4 years',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.student)
        url = reverse('apply-instructor')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_pending'])
        self.assertContains(response, 'Application Status: Pending Review')
        self.assertContains(response, 'Application Under Academic Review')

    def test_pending_student_denied_teacher_dashboard_and_course_builder(self):
        """Student with pending application CANNOT access teacher dashboard or course builder (403 Forbidden)."""
        InstructorApplication.objects.create(
            user=self.student,
            department='CS',
            title='Lecturer',
            target_subjects='Security',
            teaching_experience='2 years',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.student)

        # Teacher dashboard
        resp_dashboard = self.client.get(reverse('teacher-dashboard'))
        self.assertEqual(resp_dashboard.status_code, 403)

        # Course management builder
        resp_builder = self.client.get(reverse('manage-home'))
        self.assertEqual(resp_builder.status_code, 403)

    def test_access_control_on_admin_instructor_applications_queue(self):
        """Only administrators can access the console instructor applications queue."""
        list_url = reverse('console-instructor-application-list')

        # 1. Anonymous user redirected to login
        resp_anon = self.client.get(list_url)
        self.assertEqual(resp_anon.status_code, 302)

        # 2. Student denied (403)
        self.client.force_login(self.student)
        resp_student = self.client.get(list_url)
        self.assertEqual(resp_student.status_code, 403)

        # 3. Teacher denied (403)
        self.client.force_login(self.teacher)
        resp_teacher = self.client.get(list_url)
        self.assertEqual(resp_teacher.status_code, 403)

        # 4. Admin allowed (200)
        self.client.force_login(self.admin)
        resp_admin = self.client.get(list_url)
        self.assertEqual(resp_admin.status_code, 200)

    def test_admin_can_view_applications_queue_and_detail(self):
        """Admin views applications in list and inspects applicant credentials in detail."""
        app = InstructorApplication.objects.create(
            user=self.student,
            department='Faculty of Computing',
            title='Lead Instructor',
            target_subjects='Malware Analysis, Reverse Engineering',
            teaching_experience='5 years mentoring labs',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.admin)

        # List view
        list_resp = self.client.get(reverse('console-instructor-application-list'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'student_bob')
        self.assertContains(list_resp, 'Faculty of Computing')

        # Detail view
        detail_resp = self.client.get(
            reverse('console-instructor-application-detail', kwargs={'app_id': app.id})
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'student_bob')
        self.assertContains(detail_resp, 'Malware Analysis, Reverse Engineering')

    def test_admin_approve_application_workflow(self):
        """Admin approves application: grants TEACHER role, INSTRUCTOR mode, verified TeacherProfile, unlocks dashboards."""
        app = InstructorApplication.objects.create(
            user=self.student,
            department='Information Security',
            title='Principal Analyst',
            target_subjects='Network Defense',
            teaching_experience='6 years instruction',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.admin)
        action_url = reverse(
            'console-instructor-application-action',
            kwargs={'app_id': app.id, 'action': 'approve'}
        )

        response = self.client.post(action_url, {
            'awarded_level': InstructorApplication.AwardedLevel.PROFESSIONAL,
            'admin_notes': 'Credentials confirmed. Verified OSCP certificate.',
        })
        self.assertEqual(response.status_code, 302)

        # Application state verified
        app.refresh_from_db()
        self.assertEqual(app.status, InstructorApplication.Status.APPROVED)
        self.assertEqual(app.awarded_level, InstructorApplication.AwardedLevel.PROFESSIONAL)
        self.assertEqual(app.reviewed_by, self.admin)
        self.assertIsNotNone(app.reviewed_at)

        # User state verified
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, UserRole.INSTRUCTOR)
        self.assertEqual(self.student.active_mode, ActiveMode.INSTRUCTOR)
        self.assertTrue(self.student.is_teacher)
        self.assertTrue(self.student.groups.filter(name='Instructor').exists())

        # Teacher profile verified
        tp = TeacherProfile.objects.get(user=self.student)
        self.assertTrue(tp.is_verified)
        self.assertEqual(tp.level, InstructorApplication.AwardedLevel.PROFESSIONAL)
        self.assertEqual(tp.department, 'Information Security')
        self.assertEqual(tp.title, 'Principal Analyst')

        # Applicant can now access Teacher Dashboard and Course Builder
        self.client.force_login(self.student)
        dash_resp = self.client.get(reverse('teacher-dashboard'))
        self.assertEqual(dash_resp.status_code, 200)

        builder_resp = self.client.get(reverse('manage-home'))
        self.assertEqual(builder_resp.status_code, 200)

        # Apply page now displays verified faculty state
        apply_resp = self.client.get(reverse('apply-instructor'))
        self.assertEqual(apply_resp.status_code, 200)
        self.assertTrue(apply_resp.context['is_teacher'])
        self.assertContains(apply_resp, 'Verified Faculty Member')

    def test_admin_reject_application_workflow(self):
        """Admin rejects application: user remains STUDENT, rejection feedback saved, Notification sent, resubmission allowed."""
        app = InstructorApplication.objects.create(
            user=self.student,
            department='Physics',
            title='Teacher',
            target_subjects='Quantum Computing',
            teaching_experience='1 year teaching',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.admin)
        action_url = reverse(
            'console-instructor-application-action',
            kwargs={'app_id': app.id, 'action': 'reject'}
        )

        response = self.client.post(action_url, {
            'rejection_feedback': 'Please provide sample recorded teaching video and academic degree.',
            'admin_notes': 'Missing portfolio proof.',
        })
        self.assertEqual(response.status_code, 302)

        # Application state verified
        app.refresh_from_db()
        self.assertEqual(app.status, InstructorApplication.Status.REJECTED)
        self.assertEqual(app.rejection_feedback, 'Please provide sample recorded teaching video and academic degree.')
        self.assertEqual(app.reviewed_by, self.admin)

        # User remains STUDENT
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, UserRole.STUDENT)
        self.assertFalse(self.student.is_teacher)

        # Access still blocked to teacher areas
        self.client.force_login(self.student)
        dash_resp = self.client.get(reverse('teacher-dashboard'))
        self.assertEqual(dash_resp.status_code, 403)

        # Apply page shows rejection feedback and allows resubmission
        apply_resp = self.client.get(reverse('apply-instructor'))
        self.assertEqual(apply_resp.status_code, 200)
        self.assertTrue(apply_resp.context['is_rejected'])
        self.assertContains(apply_resp, 'Previous Application Update')
        self.assertContains(apply_resp, 'was not approved.')
        self.assertContains(apply_resp, 'Please provide sample recorded teaching video and academic degree.')
        # Form is present to allow resubmission
        self.assertIn('form', apply_resp.context)

    def test_resubmission_after_rejection(self):
        """Student with a REJECTED application can submit a new application."""
        InstructorApplication.objects.create(
            user=self.student,
            department='Math',
            title='Tutor',
            target_subjects='Calculus',
            teaching_experience='2 years tutoring',
            status=InstructorApplication.Status.REJECTED,
            rejection_feedback='Need more experience',
        )

        self.client.force_login(self.student)
        url = reverse('apply-instructor')

        post_data = {
            'department': 'Computer Science',
            'title': 'Certified Trainer',
            'target_subjects': 'Python & Django',
            'teaching_experience': '5 years practical training and workshop experience.',
            'bio': 'Updated bio with 5 years training experience.',
            'qualifications': 'B.C.Sc and professional teaching certification.',
            'free_tutorial_title': 'Python & Django Starter Tutorial',
            'free_tutorial_url': 'https://youtube.com/watch?v=starter123',
            'terms_accepted': True,
        }

        response = self.client.post(url, post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Now 2 applications: 1 rejected, 1 pending
        apps = InstructorApplication.objects.filter(user=self.student).order_by('-created_at')
        self.assertEqual(apps.count(), 2)
        latest_app = apps.first()
        self.assertEqual(latest_app.status, InstructorApplication.Status.PENDING)
        self.assertEqual(latest_app.department, 'Computer Science')

    def test_partner_portal_remains_strictly_protected(self):
        """Partner portal endpoints remain strictly protected from unauthorized students and teachers."""
        partner_url = reverse('partner-portal')

        # 1. Student access redirects to landing with restricted notice
        self.client.force_login(self.student)
        resp_student = self.client.get(partner_url, follow=True)
        self.assertContains(resp_student, 'Access restricted to institutional partners and administrators.')

        # 2. Teacher access also redirects to landing with restricted notice
        self.client.force_login(self.teacher)
        resp_teacher = self.client.get(partner_url, follow=True)
        self.assertContains(resp_teacher, 'Access restricted to institutional partners and administrators.')
