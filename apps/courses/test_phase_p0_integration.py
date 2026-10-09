from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.users.models import UserRole
from apps.courses.models import Subject, Course, Module, Lesson
from apps.partner.models import Institution, PartnerMembership

User = get_user_model()


class PhaseP0MasterIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Subject
        Subject.ensure_default_subjects()
        self.subject = Subject.objects.first()

        # Users
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@example.com',
            password='Password123!',
            role=UserRole.STUDENT,
        )

        self.teacher_1 = User.objects.create_user(
            username='teacher_bob',
            email='bob@example.com',
            password='Password123!',
            role=UserRole.TEACHER,
        )

        self.teacher_2 = User.objects.create_user(
            username='teacher_carol',
            email='carol@example.com',
            password='Password123!',
            role=UserRole.TEACHER,
        )

        self.partner_user = User.objects.create_user(
            username='partner_dave',
            email='dave@example.com',
            password='Password123!',
            role=UserRole.PARTNER,
        )
        self.institution = Institution.objects.create(
            name='Yangon Tech Institute',
            slug='yangon-tech-inst',
            contact_person=self.partner_user,
            email='info@yti.edu.mm',
        )
        PartnerMembership.objects.create(
            institution=self.institution,
            user=self.partner_user,
            role=PartnerMembership.Role.ADMIN,
            status=PartnerMembership.Status.ACTIVE,
        )

        self.admin = User.objects.create_superuser(
            username='admin_eve',
            email='eve@example.com',
            password='Password123!',
            role=UserRole.ADMIN,
        )

    def test_anonymous_user_public_layout_has_no_sidebar(self):
        """Unauthenticated visitors should see full-width layout without any role sidebars."""
        # Home
        res_home = self.client.get(reverse('landing-page'))
        self.assertEqual(res_home.status_code, 200)
        self.assertNotContains(res_home, '<aside id="melSidebar"')

        # Catalog
        res_catalog = self.client.get(reverse('course-list'))
        self.assertEqual(res_catalog.status_code, 200)
        self.assertNotContains(res_catalog, '<aside id="melSidebar"')

        # Pricing
        res_pricing = self.client.get(reverse('pricing'))
        self.assertEqual(res_pricing.status_code, 200)
        self.assertNotContains(res_pricing, '<aside id="melSidebar"')

    def test_student_authenticated_layout_sidebar(self):
        """Authenticated students should see student navigation and not teacher/admin bars."""
        self.client.force_login(self.student)
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '<aside id="melSidebar"')
        self.assertContains(res, 'My Courses')
        self.assertContains(res, 'Cyber Labs')
        self.assertContains(res, 'Career Portfolio')
        self.assertNotContains(res, 'Instructor Dashboard')
        self.assertNotContains(res, 'Admin Console')
        self.assertNotContains(res, 'Institution Directory')

    def test_teacher_authenticated_layout_sidebar(self):
        """Authenticated instructors should see teacher cockpit navigation."""
        self.client.force_login(self.teacher_1)
        res = self.client.get(reverse('teacher-dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '<aside id="melSidebar"')
        self.assertContains(res, 'Instructor Dashboard')
        self.assertContains(res, 'Course Builder')
        self.assertContains(res, 'Grading Queue')
        self.assertNotContains(res, 'Admin Console')
        self.assertNotContains(res, 'Institution Directory')

    def test_partner_authenticated_layout_sidebar_and_redirect(self):
        """Authenticated partners should land on partner-dashboard with partner sidebar."""
        self.client.force_login(self.partner_user)
        # Dashboard URL redirect for partner
        res_dash = self.client.get(reverse('dashboard'))
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn(reverse('partner-dashboard'), res_dash.url)

        res = self.client.get(reverse('partner-dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '<aside id="melSidebar"')
        self.assertContains(res, 'Partner Dashboard')
        self.assertContains(res, 'Institution Directory')
        self.assertContains(res, 'Revenue &amp; Settlements')
        self.assertNotContains(res, 'Admin Console')

    def test_admin_authenticated_layout_sidebar(self):
        """Authenticated admins should see admin navigation and controls."""
        self.client.force_login(self.admin)
        res_dash = self.client.get(reverse('dashboard'))
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn(reverse('admin-dashboard'), res_dash.url)

        res = self.client.get(reverse('admin-dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '<aside id="melSidebar"')
        self.assertContains(res, 'Admin Console')
        self.assertContains(res, 'Content Studio')
        self.assertContains(res, 'Range Ops')

    def test_rbac_student_blocked_from_teacher_and_admin_routes(self):
        """Students must be blocked from teacher dashboard, course creation, and admin console."""
        self.client.force_login(self.student)

        # Teacher dashboard
        res_td = self.client.get(reverse('teacher-dashboard'))
        self.assertIn(res_td.status_code, (302, 403))

        # Course create
        res_cc = self.client.get(reverse('course-create'))
        self.assertIn(res_cc.status_code, (302, 403))

        # Admin console
        res_ac = self.client.get(reverse('console-home'))
        self.assertIn(res_ac.status_code, (302, 403))

    def test_course_builder_object_level_isolation_and_publishing_workflow(self):
        """Verify teacher cannot edit another teacher's course, validation on publish, and admin approval."""
        self.client.force_login(self.teacher_1)

        # 1. Teacher 1 creates course
        course = Course.objects.create(
            title='Web Penetration Testing 101',
            slug='web-pentest-101',
            subject=self.subject,
            owner=self.teacher_1,
            price=Decimal('25000'),
            status=Course.Status.DRAFT,
            is_published=False,
        )

        # 2. Teacher 2 cannot access course edit
        self.client.force_login(self.teacher_2)
        res_unauth = self.client.get(reverse('course-edit', kwargs={'slug': course.slug}))
        self.assertEqual(res_unauth.status_code, 404)

        # 3. Teacher 1 cannot submit for review if 0 modules / 0 lessons
        self.client.force_login(self.teacher_1)
        res_submit_empty = self.client.post(reverse('course-submit-review', kwargs={'slug': course.slug}))
        self.assertEqual(res_submit_empty.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.DRAFT)

        # 4. Teacher 1 adds module and lesson
        module = Module.objects.create(
            course=course,
            title='SQL Injection Fundamentals',
            code='MOD-01',
            order=1,
        )
        lesson = Lesson.objects.create(
            module=module,
            title='Intro to UNION Based SQLi',
            order=1,
            lesson_type='video',
        )

        # 5. Teacher 1 submits for review
        res_submit_valid = self.client.post(reverse('course-submit-review', kwargs={'slug': course.slug}))
        self.assertEqual(res_submit_valid.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PENDING_REVIEW)

        # 6. While in review, teacher cannot edit course
        res_edit_locked = self.client.get(reverse('course-edit', kwargs={'slug': course.slug}))
        self.assertEqual(res_edit_locked.status_code, 302)

        # 7. Anonymous visitor cannot see pending course in catalog
        self.client.logout()
        res_catalog_before = self.client.get(reverse('course-list'))
        self.assertNotContains(res_catalog_before, 'Web Penetration Testing 101')

        # 8. Admin approves and publishes course
        self.client.force_login(self.admin)
        res_publish = self.client.post(reverse('course-review-action', kwargs={'slug': course.slug}), {
            'action': 'publish',
            'admin_review_notes': 'Course meets quality standards.',
        })
        self.assertEqual(res_publish.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.is_published)

        # 9. Anonymous visitor now sees course in catalog
        self.client.logout()
        res_catalog_after = self.client.get(reverse('course-list'))
        self.assertContains(res_catalog_after, 'Web Penetration Testing 101')

    def test_module_delete_view_rbac_and_flow(self):
        """Test ModuleDeleteView is isolated to owner and redirects to course-edit."""
        course = Course.objects.create(
            title='Network Forensics Track',
            slug='network-forensics-track',
            subject=self.subject,
            owner=self.teacher_1,
            price=Decimal('15000'),
            status=Course.Status.DRAFT,
            is_published=False,
        )
        module = Module.objects.create(
            course=course,
            title='PCAP Analysis',
            code='NET-01',
            order=1,
        )

        # Teacher 2 cannot delete module
        self.client.force_login(self.teacher_2)
        res_del_unauth = self.client.post(reverse('module-delete', kwargs={'module_id': module.id}))
        self.assertEqual(res_del_unauth.status_code, 404)
        self.assertTrue(Module.objects.filter(id=module.id).exists())

        # Teacher 1 deletes module
        self.client.force_login(self.teacher_1)
        res_del_auth = self.client.post(reverse('module-delete', kwargs={'module_id': module.id}))
        self.assertEqual(res_del_auth.status_code, 302)
        self.assertIn(reverse('course-edit', kwargs={'slug': course.slug}), res_del_auth.url)
        self.assertFalse(Module.objects.filter(id=module.id).exists())
