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
