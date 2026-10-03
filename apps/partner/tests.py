from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.users.models import UserRole
from .models import Institution, InstitutionCohort, CohortStudent

User = get_user_model()


class PartnerInstitutionTests(TestCase):
    def setUp(self):
        self.partner_user = User.objects.create_user(
            username='partner_admin', email='partner@uni.edu.mm', password='password123',
            role=UserRole.TEACHER
        )
        self.student = User.objects.create_user(
            username='cohort_student', email='student@uni.edu.mm', password='password123',
            role=UserRole.STUDENT
        )
        self.regular_student = User.objects.create_user(
            username='other_student', email='other@example.com', password='password123',
            role=UserRole.STUDENT
        )

        self.institution = Institution.objects.create(
            name='Yangon Technological University (YTU)',
            slug='ytu',
            institution_type=Institution.InstitutionType.UNIVERSITY,
            contact_person=self.partner_user,
            email='info@ytu.edu.mm',
            is_verified=True,
            mou_signed=True,
            max_student_seats=250,
        )

        self.cohort = InstitutionCohort.objects.create(
            institution=self.institution,
            name='Computer Engineering Batch 2026',
            code='YTU-CE-2026',
            is_active=True,
        )

        self.cohort_student = CohortStudent.objects.create(
            cohort=self.cohort,
            student=self.student,
            student_id_number='YTU-CE-001',
        )

        self.client = Client()

    def test_institution_and_cohort_creation(self):
        self.assertEqual(self.institution.cohorts.count(), 1)
        self.assertEqual(self.cohort.students.count(), 1)
        self.assertEqual(self.cohort_student.student_id_number, 'YTU-CE-001')
        self.assertTrue(self.partner_user.is_partner)

    def test_partner_portal_access(self):
        # Regular student should be redirected/denied
        self.client.login(username='other_student', password='password123')
        res = self.client.get(reverse('partner-portal'))
        self.assertEqual(res.status_code, 302)

        # Partner representative has access
        self.client.login(username='partner_admin', password='password123')
        res = self.client.get(reverse('partner-portal'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Yangon Technological University')
        self.assertContains(res, 'YTU-CE-2026')

    def test_institution_public_views(self):
        # Public listing
        res = self.client.get(reverse('partner-list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Yangon Technological University')

        # Public detail
        res = self.client.get(reverse('partner-detail', kwargs={'slug': 'ytu'}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Computer Engineering Batch 2026')

    def test_api_institutions(self):
        res = self.client.get(reverse('api-partner-institutions'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Yangon Technological University (YTU)')

    def test_api_portal_stats(self):
        self.client.login(username='partner_admin', password='password123')
        res = self.client.get(reverse('api-partner-stats'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['institutions_count'], 1)
        self.assertEqual(data['cohorts_count'], 1)
        self.assertEqual(data['students_count'], 1)


class PartnerArchitectureAndServicesTests(TestCase):
    def setUp(self):
        from apps.users.services import create_user_account, ensure_default_groups
        ensure_default_groups()

        self.institution = Institution.objects.create(
            name='Myanmar Institute of Information Technology (MIIT)',
            slug='miit',
            institution_type=Institution.InstitutionType.UNIVERSITY,
            email='contact@miit.edu.mm',
        )

        self.staff_user = create_user_account(
            username='miit_lecturer',
            email='lecturer@miit.edu.mm',
            password='Password2026!',
            role=UserRole.STUDENT,
        )

        self.student = create_user_account(
            username='miit_student',
            email='student1@miit.edu.mm',
            password='Password2026!',
            role=UserRole.STUDENT,
        )

    def test_organization_id_auto_generation(self):
        self.assertIsNotNone(self.institution.organization_id)
        self.assertTrue(self.institution.organization_id.startswith('MEL-ORG-'))

    def test_add_partner_staff_and_role_escalation(self):
        from .services import add_partner_staff
        from .models import PartnerMembership

        membership = add_partner_staff(
            institution=self.institution,
            user=self.staff_user,
            role=PartnerMembership.StaffRole.TEACHER,
            title='Department Head',
            department='Cyber Security',
        )
        self.assertEqual(membership.role, PartnerMembership.StaffRole.TEACHER)
        self.staff_user.refresh_from_db()
        self.assertTrue(self.staff_user.has_role('partner'))
        self.assertTrue(self.staff_user.is_partner)

    def test_enroll_partner_student_by_account_id(self):
        from .services import enroll_partner_student_by_account_id
        from .models import PartnerStudent

        # Enroll using permanent MEL Account ID
        partner_student = enroll_partner_student_by_account_id(
            institution=self.institution,
            account_id=self.student.account_id,
            external_student_id='MIIT-CS-0042',
        )
        self.assertIsNotNone(partner_student)
        self.assertEqual(partner_student.student, self.student)
        self.assertEqual(partner_student.external_student_id, 'MIIT-CS-0042')
        self.assertEqual(partner_student.status, PartnerStudent.Status.ACTIVE)

        # Re-enrolling is idempotent (no duplicate accounts created)
        again = enroll_partner_student_by_account_id(
            institution=self.institution,
            account_id=self.student.account_id,
            external_student_id='MIIT-CS-0042-UPDATED',
        )
        self.assertEqual(PartnerStudent.objects.filter(institution=self.institution, student=self.student).count(), 1)
        self.assertEqual(again.external_student_id, 'MIIT-CS-0042-UPDATED')

    def test_calculate_partner_revenue_split(self):
        from decimal import Decimal
        from .services import calculate_partner_revenue_split

        split = calculate_partner_revenue_split(Decimal('100000'), Decimal('25.00'))
        self.assertEqual(split['partner_share'], Decimal('25000.00'))
        self.assertEqual(split['platform_author_share'], Decimal('75000.00'))
        self.assertEqual(split['partner_percentage'], Decimal('25.00'))
        self.assertEqual(split['platform_author_percentage'], Decimal('75.00'))

