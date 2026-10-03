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


class PartnerCoursePermissionAndObjectLevelAuthorizationTests(TestCase):
    def setUp(self):
        self.client = Client()
        from apps.courses.models import Subject, Course, Enrollment

        Subject.ensure_default_subjects()
        self.subject = Subject.objects.first()

        self.partner_a = User.objects.create_user(
            username='partner_a_user', email='a@ytu.edu.mm', password='password123',
            role=UserRole.PARTNER
        )
        self.partner_b = User.objects.create_user(
            username='partner_b_user', email='b@miit.edu.mm', password='password123',
            role=UserRole.PARTNER
        )
        self.student = User.objects.create_user(
            username='test_student', email='student@example.com', password='password123',
            role=UserRole.STUDENT
        )
        self.inst_a = Institution.objects.create(
            name='Institution Alpha',
            slug='inst-alpha',
            contact_person=self.partner_a,
            is_verified=True,
        )
        self.inst_b = Institution.objects.create(
            name='Institution Beta',
            slug='inst-beta',
            contact_person=self.partner_b,
            is_verified=True,
        )

        self.course_a = Course.objects.create(
            title='Course for Institution Alpha',
            slug='course-alpha',
            subject=self.subject,
            owner=self.partner_a,
            partner_institution=self.inst_a,
            owner_type=Course.OwnerType.PARTNER,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )
        self.course_b = Course.objects.create(
            title='Course for Institution Beta',
            slug='course-beta',
            subject=self.subject,
            owner=self.partner_b,
            partner_institution=self.inst_b,
            owner_type=Course.OwnerType.PARTNER,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )

    def test_partner_course_list_object_level_authorization(self):
        """Partner A only sees Course A; cannot see Course B."""
        self.client.force_login(self.partner_a)
        res = self.client.get(reverse('partner-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Course for Institution Alpha')
        self.assertNotContains(res, 'Course for Institution Beta')

    def test_partner_creates_institutional_course(self):
        """Partner can create a course for their assigned institution."""
        self.client.force_login(self.partner_a)
        post_data = {
            'partner_institution': self.inst_a.id,
            'title': 'Alpha Embedded Systems',
            'slug': 'alpha-embedded',
            'subject': self.subject.id,
            'description': 'Microcontroller programming.',
            'level': 'intermediate',
            'language': 'my',
            'duration_months': 3,
            'access_type': 'partner_only',
            'price': 0,
        }
        res = self.client.post(reverse('partner-course-create'), post_data)
        self.assertEqual(res.status_code, 302)

        from apps.courses.models import Course
        new_course = Course.objects.get(slug='alpha-embedded')
        self.assertEqual(new_course.partner_institution, self.inst_a)
        self.assertEqual(new_course.owner_type, Course.OwnerType.PARTNER)
        self.assertEqual(new_course.status, Course.Status.DRAFT)
        self.assertFalse(new_course.is_published)

    def test_partner_cannot_create_course_for_another_institution(self):
        """Partner A cannot create courses for Institution B."""
        self.client.force_login(self.partner_a)
        post_data = {
            'partner_institution': self.inst_b.id,
            'title': 'Hacked Course',
            'slug': 'hacked-course',
            'subject': self.subject.id,
            'description': 'Attempting cross-tenant creation.',
            'price': 0,
        }
        res = self.client.post(reverse('partner-course-create'), post_data)
        # Form validation or dispatch will reject unauthorized institution choice
        self.assertNotEqual(res.status_code, 302)
        from apps.courses.models import Course
        self.assertFalse(Course.objects.filter(slug='hacked-course').exists())

    def test_partner_enrollment_list_object_level_authorization(self):
        """Partner A can only view student enrollments belonging to their courses."""
        from apps.courses.models import Enrollment
        Enrollment.objects.create(
            course=self.course_a, student=self.student,
            source=Enrollment.Source.PARTNER, partner_institution=self.inst_a
        )

        self.client.force_login(self.partner_a)
        res = self.client.get(reverse('partner-enrollments'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Course for Institution Alpha')
        self.assertNotContains(res, 'Course for Institution Beta')

        # Partner B cannot see Institution A enrollments
        self.client.force_login(self.partner_b)
        res = self.client.get(reverse('partner-enrollments'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'Course for Institution Alpha')

    def test_partner_adds_instructor_to_organization(self):
        """Partner can add faculty instructor to their institution."""
        new_teacher = User.objects.create_user(
            username='faculty_prof', email='prof@ytu.edu.mm', password='password123',
            role=UserRole.STUDENT
        )
        self.client.force_login(self.partner_a)
        res = self.client.post(reverse('partner-instructors'), {
            'institution_id': str(self.inst_a.id),
            'username': 'faculty_prof',
        })
        self.assertEqual(res.status_code, 302)

        from apps.partner.models import PartnerMembership
        membership = PartnerMembership.objects.filter(
            institution=self.inst_a, user=new_teacher, role=PartnerMembership.Role.TEACHER
        ).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.status, PartnerMembership.Status.ACTIVE)
        new_teacher.refresh_from_db()
        self.assertTrue(new_teacher.is_teacher)


