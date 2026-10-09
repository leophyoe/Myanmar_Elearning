from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.users.models import User, UserRole
from apps.partner.models import Institution, PartnerMembership, InstitutionCohort, CohortStudent, PartnerStudent
from apps.courses.models import Course, Enrollment
from apps.certificates.models import Certificate


class PartnerMultiTenancyAndWorkflowTests(TestCase):
    """
    Comprehensive multi-tenant isolation and end-to-end workflow test suite.
    Guarantees strict tenant separation between Partner A and Partner B,
    verifies unauthorized access restrictions for non-partners, and tests
    real database state mutations across all partner management operations.
    """

    def setUp(self):
        self.client = Client()

        # Partner A User & Institution
        self.partner_a_user = User.objects.create_user(
            username='partner_a',
            email='partner_a@alpha.edu',
            password='Password123!',
            role=UserRole.PARTNER,
            account_id='MEL-PA-001'
        )
        self.inst_alpha = Institution.objects.create(
            name='Alpha University',
            slug='alpha-university',
            contact_person=self.partner_a_user,
            email='contact@alpha.edu',
            is_verified=True,
            max_student_seats=50
        )
        PartnerMembership.objects.create(
            institution=self.inst_alpha,
            user=self.partner_a_user,
            role=PartnerMembership.Role.OWNER,
            status=PartnerMembership.Status.ACTIVE
        )

        # Partner B User & Institution
        self.partner_b_user = User.objects.create_user(
            username='partner_b',
            email='partner_b@beta.edu',
            password='Password123!',
            role=UserRole.PARTNER,
            account_id='MEL-PB-002'
        )
        self.inst_beta = Institution.objects.create(
            name='Beta Polytechnic',
            slug='beta-polytechnic',
            contact_person=self.partner_b_user,
            email='contact@beta.edu',
            is_verified=True,
            max_student_seats=50
        )
        PartnerMembership.objects.create(
            institution=self.inst_beta,
            user=self.partner_b_user,
            role=PartnerMembership.Role.OWNER,
            status=PartnerMembership.Status.ACTIVE
        )

        # Regular Students & Teachers
        self.student_a = User.objects.create_user(
            username='student_alpha',
            email='alice@alpha.edu',
            password='Password123!',
            role=UserRole.STUDENT,
            account_id='MEL-ST-001'
        )
        self.student_b = User.objects.create_user(
            username='student_beta',
            email='bob@beta.edu',
            password='Password123!',
            role=UserRole.STUDENT,
            account_id='MEL-ST-002'
        )
        self.unaffiliated_student = User.objects.create_user(
            username='unaffiliated_student',
            email='stranger@gmail.com',
            password='Password123!',
            role=UserRole.STUDENT
        )
        self.teacher_user = User.objects.create_user(
            username='faculty_member',
            email='faculty@alpha.edu',
            password='Password123!',
            role=UserRole.TEACHER
        )

        # Courses
        self.course_alpha = Course.objects.create(
            title='Alpha Defense 101',
            slug='alpha-defense-101',
            owner=self.partner_a_user,
            partner_institution=self.inst_alpha,
            access_type=Course.AccessType.PARTNER_ONLY,
            is_published=True
        )
        self.course_beta = Course.objects.create(
            title='Beta Security 201',
            slug='beta-security-201',
            owner=self.partner_b_user,
            partner_institution=self.inst_beta,
            access_type=Course.AccessType.PARTNER_ONLY,
            is_published=True
        )

        # Cohorts
        self.cohort_alpha = InstitutionCohort.objects.create(
            institution=self.inst_alpha,
            name='Alpha Spring 2026',
            code='ALPHA-2026-A',
            course=self.course_alpha,
            is_active=True
        )
        self.cohort_beta = InstitutionCohort.objects.create(
            institution=self.inst_beta,
            name='Beta Spring 2026',
            code='BETA-2026-B',
            course=self.course_beta,
            is_active=True
        )

        # PartnerStudent affiliations
        self.ps_alpha = PartnerStudent.objects.create(
            institution=self.inst_alpha,
            student=self.student_a,
            status=PartnerStudent.Status.ACTIVE,
            class_group='ALPHA-2026-A'
        )
        self.ps_beta = PartnerStudent.objects.create(
            institution=self.inst_beta,
            student=self.student_b,
            status=PartnerStudent.Status.ACTIVE,
            class_group='BETA-2026-B'
        )

    # -------------------------------------------------------------------------
    # 1. Institution Settings & Multi-tenant Profile Isolation
    # -------------------------------------------------------------------------
    def test_partner_can_view_and_update_own_institution_settings(self):
        self.client.force_login(self.partner_a_user)
        response = self.client.get(reverse('partner-institution-settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha University')
        self.assertNotContains(response, 'Beta Polytechnic')

        # Update profile
        update_data = {
            'institution_id': self.inst_alpha.id,
            'name': 'Alpha University of Technology',
            'website': 'https://tech.alpha.edu',
            'notes': 'Leading Cybersecurity Academy - Premier center for defense',
            'email': 'security@alpha.edu',
        }
        res = self.client.post(reverse('partner-institution-settings'), update_data)
        self.assertEqual(res.status_code, 302)

        self.inst_alpha.refresh_from_db()
        self.assertEqual(self.inst_alpha.name, 'Alpha University of Technology')
        self.assertEqual(self.inst_alpha.website, 'https://tech.alpha.edu')
        self.assertEqual(self.inst_alpha.notes, 'Leading Cybersecurity Academy - Premier center for defense')

    def test_partner_b_cannot_update_partner_a_institution(self):
        self.client.force_login(self.partner_b_user)
        # Attempt to modify Alpha's institution with Partner B's credentials
        hijack_data = {
            'institution_id': self.inst_alpha.id,
            'name': 'Hacked University',
            'website': 'https://hacked.com',
        }
        res = self.client.post(reverse('partner-institution-settings'), hijack_data)
        self.assertIn(res.status_code, [403, 404])

        self.inst_alpha.refresh_from_db()
        self.assertEqual(self.inst_alpha.name, 'Alpha University')

    # -------------------------------------------------------------------------
    # 2. Cohort Management & Multi-tenant Isolation
    # -------------------------------------------------------------------------
    def test_cohort_list_only_shows_own_institution_cohorts(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('partner-cohorts'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'ALPHA-2026-A')
        self.assertNotContains(res, 'BETA-2026-B')

    def test_partner_cannot_view_or_edit_foreign_cohort(self):
        self.client.force_login(self.partner_a_user)

        # Attempt to view Cohort Beta detail -> 403
        res = self.client.get(reverse('partner-cohort-detail', kwargs={'cohort_id': self.cohort_beta.id}))
        self.assertEqual(res.status_code, 403)

        # Attempt to view Cohort Beta edit page -> 403
        res = self.client.get(reverse('partner-cohort-edit', kwargs={'cohort_id': self.cohort_beta.id}))
        self.assertEqual(res.status_code, 403)

        # Attempt to post edit to Cohort Beta -> 403
        res = self.client.post(reverse('partner-cohort-edit', kwargs={'cohort_id': self.cohort_beta.id}), {
            'name': 'Tampered Cohort Name'
        })
        self.assertEqual(res.status_code, 403)
        self.cohort_beta.refresh_from_db()
        self.assertEqual(self.cohort_beta.name, 'Beta Spring 2026')

        # Attempt to export CSV of Cohort Beta -> 403
        res = self.client.get(reverse('partner-cohort-export-csv', kwargs={'cohort_id': self.cohort_beta.id}))
        self.assertEqual(res.status_code, 403)

        # Attempt to enroll student into Cohort Beta -> 403
        res = self.client.post(reverse('partner-cohort-enroll-student', kwargs={'cohort_id': self.cohort_beta.id}), {
            'identifier': self.student_a.username,
        })
        self.assertEqual(res.status_code, 403)

    def test_partner_can_create_cohort_and_enroll_student(self):
        self.client.force_login(self.partner_a_user)

        # Create new cohort
        res = self.client.post(reverse('partner-cohort-create'), {
            'institution_id': self.inst_alpha.id,
            'name': 'Alpha Autumn 2026',
            'code': 'ALPHA-2026-AUTUMN',
            'course_id': self.course_alpha.id,
            'is_active': 'on'
        })
        self.assertEqual(res.status_code, 302)
        new_cohort = InstitutionCohort.objects.get(code='ALPHA-2026-AUTUMN')
        self.assertEqual(new_cohort.institution, self.inst_alpha)

        # Enroll student using Account ID
        enroll_res = self.client.post(reverse('partner-cohort-enroll-student', kwargs={'cohort_id': new_cohort.id}), {
            'identifier': self.unaffiliated_student.email,
            'student_id_number': 'ROLL-2026-99',
        })
        self.assertEqual(enroll_res.status_code, 302)

        # Verify database changes
        self.assertTrue(CohortStudent.objects.filter(cohort=new_cohort, student=self.unaffiliated_student).exists())
        self.assertTrue(PartnerStudent.objects.filter(institution=self.inst_alpha, student=self.unaffiliated_student).exists())
        self.assertTrue(Enrollment.objects.filter(course=self.course_alpha, student=self.unaffiliated_student, source='partner').exists())

    # -------------------------------------------------------------------------
    # 3. Learner Roster & Action Multi-tenant Isolation
    # -------------------------------------------------------------------------
    def test_learner_roster_isolation(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('partner-learners'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'student_alpha')
        self.assertNotContains(res, 'student_beta')

    def test_partner_cannot_remove_foreign_learner(self):
        self.client.force_login(self.partner_a_user)
        # Attempt to remove Beta's learner ps_beta -> 404 because get_object_or_404 filters by institution__in=user_institutions
        res = self.client.post(reverse('partner-learner-remove', kwargs={'pk': self.ps_beta.id}))
        self.assertEqual(res.status_code, 404)
        self.assertTrue(PartnerStudent.objects.filter(id=self.ps_beta.id).exists())

    def test_partner_can_remove_own_learner(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.post(reverse('partner-learner-remove', kwargs={'pk': self.ps_alpha.id}))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(PartnerStudent.objects.filter(id=self.ps_alpha.id).exists())

    # -------------------------------------------------------------------------
    # 4. Faculty Instructor Assignment & Multi-tenant Isolation
    # -------------------------------------------------------------------------
    def test_partner_can_assign_faculty_instructor(self):
        self.client.force_login(self.partner_a_user)
        new_teacher_candidate = User.objects.create_user(
            username='cyber_instructor',
            email='instructor@alpha.edu',
            password='Password123!',
            role=UserRole.STUDENT
        )
        res = self.client.post(reverse('partner-instructors'), {
            'institution_id': self.inst_alpha.id,
            'username': 'cyber_instructor',
        })
        self.assertEqual(res.status_code, 302)

        # Check membership and role promotion
        membership = PartnerMembership.objects.filter(institution=self.inst_alpha, user=new_teacher_candidate).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, PartnerMembership.Role.TEACHER)
        new_teacher_candidate.refresh_from_db()
        self.assertTrue(new_teacher_candidate.is_teacher)

    def test_partner_cannot_assign_instructor_to_foreign_institution(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.post(reverse('partner-instructors'), {
            'institution_id': self.inst_beta.id,
            'username': self.teacher_user.username,
        })
        self.assertEqual(res.status_code, 403)
        self.assertFalse(PartnerMembership.objects.filter(institution=self.inst_beta, user=self.teacher_user).exists())

    def test_partner_cannot_remove_foreign_faculty_instructor(self):
        # Create membership for Beta
        beta_teacher = User.objects.create_user(username='beta_prof', password='Password123!')
        pm_beta = PartnerMembership.objects.create(
            institution=self.inst_beta,
            user=beta_teacher,
            role=PartnerMembership.Role.TEACHER,
            status=PartnerMembership.Status.ACTIVE
        )
        self.client.force_login(self.partner_a_user)
        res = self.client.post(reverse('partner-instructor-remove', kwargs={'pk': pm_beta.id}))
        self.assertEqual(res.status_code, 404)
        self.assertTrue(PartnerMembership.objects.filter(id=pm_beta.id).exists())

    # -------------------------------------------------------------------------
    # 5. Course Catalog & Course Builder Authorization
    # -------------------------------------------------------------------------
    def test_courses_roster_isolation(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('partner-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Alpha Defense 101')
        self.assertNotContains(res, 'Beta Security 201')

    def test_partner_can_edit_own_institutional_course(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('course-edit', kwargs={'slug': self.course_alpha.slug}))
        self.assertEqual(res.status_code, 200)

    def test_partner_cannot_edit_foreign_institutional_course(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('course-edit', kwargs={'slug': self.course_beta.slug}))
        self.assertEqual(res.status_code, 404)

    # -------------------------------------------------------------------------
    # 6. Certificates & Credentials Roster Isolation
    # -------------------------------------------------------------------------
    def test_certificates_roster_isolation(self):
        cert_alpha = Certificate.objects.create(
            student=self.student_a,
            course=self.course_alpha,
            certificate_code='CERT-ALPHA-001',
            student_name='Alice Alpha',
            program_title='Alpha Defense 101',
            grade='DISTINCTION',
            issued_at=timezone.now()
        )
        cert_beta = Certificate.objects.create(
            student=self.student_b,
            course=self.course_beta,
            certificate_code='CERT-BETA-002',
            student_name='Bob Beta',
            program_title='Beta Security 201',
            grade='PASSED',
            issued_at=timezone.now()
        )

        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('partner-certificates'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'CERT-ALPHA-001')
        self.assertNotContains(res, 'CERT-BETA-002')

    # -------------------------------------------------------------------------
    # 7. Academic Reports & CSV Export Isolation
    # -------------------------------------------------------------------------
    def test_reports_isolation(self):
        self.client.force_login(self.partner_a_user)
        res = self.client.get(reverse('partner-reports'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'ALPHA-2026-A')
        self.assertNotContains(res, 'BETA-2026-B')

        # CSV Learners export
        csv_res = self.client.get(reverse('partner-reports-learners-csv'))
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res['Content-Type'], 'text/csv; charset=utf-8')
        content = csv_res.content.decode('utf-8')
        self.assertIn('student_alpha', content)
        self.assertNotIn('student_beta', content)

    # -------------------------------------------------------------------------
    # 8. Financial Revenue Isolation
    # -------------------------------------------------------------------------
    def test_partner_cannot_view_foreign_revenue(self):
        self.client.force_login(self.partner_a_user)
        # Attempt to access Beta's revenue
        res = self.client.get(reverse('partner-revenue-report') + f'?institution_id={self.inst_beta.id}')
        self.assertEqual(res.status_code, 404)

    # -------------------------------------------------------------------------
    # 9. Non-Partner Role Denied Access
    # -------------------------------------------------------------------------
    def test_unauthorized_student_access_denied(self):
        self.client.force_login(self.student_a)
        endpoints = [
            reverse('partner-portal'),
            reverse('partner-dashboard'),
            reverse('partner-cohorts'),
            reverse('partner-cohort-create'),
            reverse('partner-learners'),
            reverse('partner-instructors'),
            reverse('partner-courses'),
            reverse('partner-certificates'),
            reverse('partner-reports'),
            reverse('partner-revenue-report'),
        ]
        for url in endpoints:
            res = self.client.get(url)
            # Either 302 redirect to login/dashboard or 403 Forbidden
            self.assertIn(res.status_code, [302, 403], f"Endpoint {url} allowed unauthorized student access!")
