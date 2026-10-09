"""
Tests for Teacher Course Publishing, Catalog Visibility, and Student Learning Access.
Verifies the complete end-to-end course lifecycle:
Teacher Creation -> Draft -> Content Addition -> Publish -> Catalog Visibility -> Detail -> Enrollment -> Lesson Access.
"""
from django.test import TestCase, Client
from django.urls import reverse

from apps.users.models import User, UserRole, TeacherProfile, StudentProfile
from apps.courses.models import Course, Subject, Module, Lesson, Enrollment


class TeacherCourseCatalogVisibilityTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Subject
        self.subject = Subject.objects.create(
            slug='software-engineering',
            title='Software Engineering',
            description='Modern software engineering practices.',
            kind=Subject.Kind.GENERAL,
            order=1,
            is_active=True,
        )

        # Verified Teacher 1
        self.teacher_1 = User.objects.create_user(
            username='teacher_alpha',
            email='teacher_alpha@thuta.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        self.teacher_profile_1, _ = TeacherProfile.objects.get_or_create(user=self.teacher_1)
        self.teacher_profile_1.is_verified = True
        self.teacher_profile_1.bio = 'Experienced Software Engineering Instructor'
        self.teacher_profile_1.save()

        # Teacher 2 (Another verified teacher)
        self.teacher_2 = User.objects.create_user(
            username='teacher_beta',
            email='teacher_beta@thuta.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        self.teacher_profile_2, _ = TeacherProfile.objects.get_or_create(user=self.teacher_2)
        self.teacher_profile_2.is_verified = True
        self.teacher_profile_2.save()

        # Unverified Teacher 3
        self.teacher_unverified = User.objects.create_user(
            username='teacher_unverified',
            email='teacher_unverified@thuta.edu.mm',
            password='Password123!',
            role=UserRole.TEACHER,
        )
        self.teacher_profile_unverified, _ = TeacherProfile.objects.get_or_create(user=self.teacher_unverified)
        self.teacher_profile_unverified.is_verified = False
        self.teacher_profile_unverified.save()

        # Student
        self.student = User.objects.create_user(
            username='student_one',
            email='student_one@thuta.edu.mm',
            password='Password123!',
            role=UserRole.STUDENT,
        )

        # Admin
        self.admin = User.objects.create_user(
            username='admin_boss',
            email='admin_boss@thuta.edu.mm',
            password='Password123!',
            role=UserRole.ADMIN,
        )

    def test_teacher_creates_course_as_draft_and_hidden_from_students(self):
        """Teacher creates a course; it defaults to Draft and is invisible in catalog."""
        self.client.force_login(self.teacher_1)
        res = self.client.post(reverse('course-create'), {
            'title': 'Advanced Python Metaprogramming',
            'slug': 'advanced-python-metaprogramming',
            'subject': self.subject.id,
            'description': 'Master descriptors, metaclasses, and dynamic execution.',
            'level': Course.Level.ADVANCED,
            'language': Course.Language.BURMESE,
            'duration_months': 3,
            'price': 0,
        })
        self.assertEqual(res.status_code, 302)

        course = Course.objects.get(slug='advanced-python-metaprogramming')
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)
        self.assertEqual(course.owner, self.teacher_1)

        # Student catalog check: Draft course MUST NOT appear
        student_client = Client()
        res_cat_anon = student_client.get(reverse('course-list'))
        self.assertNotIn(course, res_cat_anon.context['courses'])
        self.assertNotContains(res_cat_anon, 'Advanced Python Metaprogramming')

        student_client.force_login(self.student)
        res_cat_student = student_client.get(reverse('course-list'))
        self.assertNotIn(course, res_cat_student.context['courses'])
        self.assertNotContains(res_cat_student, 'Advanced Python Metaprogramming')

        # Student detail access: Draft course returns 404
        res_detail = student_client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(res_detail.status_code, 404)

        # Teacher owner can view preview
        self.client.force_login(self.teacher_1)
        res_teacher_view = self.client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(res_teacher_view.status_code, 200)

    def test_publishing_requires_curriculum_completeness(self):
        """Course cannot be published without at least 1 module and 1 lesson."""
        course = Course.objects.create(
            title='Django Scalability',
            slug='django-scalability',
            owner=self.teacher_1,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )

        self.client.force_login(self.teacher_1)

        # 0 modules -> publish fails
        res_pub_0_mod = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_pub_0_mod.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)

        # 1 module, 0 lessons -> publish fails
        module = Module.objects.create(course=course, code='MOD-01', title='Database Tuning', order=1)
        res_pub_0_les = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_pub_0_les.status_code, 302)
        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)

    def test_verified_teacher_publishes_course_and_becomes_visible_to_students(self):
        """Verified teacher adds module & lesson and publishes; course is visible and enrollable."""
        course = Course.objects.create(
            title='FastAPI Production Architecture',
            slug='fastapi-production-architecture',
            owner=self.teacher_1,
            subject=self.subject,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )
        module = Module.objects.create(course=course, code='FST-01', title='Async Endpoints', order=1)
        lesson = Lesson.objects.create(
            module=module,
            order=1,
            title='Uvicorn and Gunicorn Workers',
            lesson_type='text',
            content_markdown='Production worker tuning...',
        )

        self.client.force_login(self.teacher_1)
        res_pub = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_pub.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.is_published)

        # Student checks Course Catalog -> course is visible!
        student_client = Client()
        student_client.force_login(self.student)
        res_catalog = student_client.get(reverse('course-list'))
        self.assertEqual(res_catalog.status_code, 200)
        self.assertIn(course, res_catalog.context['courses'])
        self.assertContains(res_catalog, 'FastAPI Production Architecture')

        # Student opens Course Detail -> 200 OK
        res_detail = student_client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, 'FastAPI Production Architecture')

        # Student enrolls in the free course
        res_enroll = student_client.post(reverse('enroll', kwargs={'slug': course.slug}))
        self.assertEqual(res_enroll.status_code, 302)
        self.assertTrue(
            Enrollment.objects.filter(course=course, student=self.student, status=Enrollment.Status.ACTIVE).exists()
        )

        # Student accesses lesson player
        res_lesson = student_client.get(reverse('lesson-detail', kwargs={'lesson_id': lesson.id}))
        self.assertEqual(res_lesson.status_code, 200)
        self.assertContains(res_lesson, 'Production worker tuning...')

    def test_editing_published_course_preserves_published_status(self):
        """Updating course title, description, or price does NOT regress published courses to Draft."""
        course = Course.objects.create(
            title='Clean Architecture in Python',
            slug='clean-architecture-in-python',
            owner=self.teacher_1,
            subject=self.subject,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        module = Module.objects.create(course=course, code='CLN-01', title='Domain Layer', order=1)
        Lesson.objects.create(module=module, order=1, title='Entities and Aggregates')

        self.client.force_login(self.teacher_1)
        res_edit = self.client.post(reverse('course-edit', kwargs={'slug': course.slug}), {
            'title': 'Clean Architecture in Python (Updated Edition)',
            'slug': 'clean-architecture-in-python',
            'subject': self.subject.id,
            'description': 'Updated modern guide to hexagonal and clean architecture.',
            'level': Course.Level.INTERMEDIATE,
            'language': Course.Language.BURMESE,
            'duration_months': 4,
            'price': 0,
        })
        self.assertEqual(res_edit.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.title, 'Clean Architecture in Python (Updated Edition)')
        # CRITICAL ASSERTION: Must remain PUBLISHED, not demoted to DRAFT!
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.is_published)

        # Verify still visible to student in catalog
        student_client = Client()
        student_client.force_login(self.student)
        res_catalog = student_client.get(reverse('course-list'))
        self.assertIn(course, res_catalog.context['courses'])
        self.assertContains(res_catalog, 'Clean Architecture in Python (Updated Edition)')

    def test_teacher_can_unpublish_course_and_it_disappears_from_student_catalog(self):
        """Teacher can unpublish a course; it reverts to Draft and is hidden from students."""
        course = Course.objects.create(
            title='Kubernetes for Developers',
            slug='kubernetes-for-developers',
            owner=self.teacher_1,
            subject=self.subject,
            status=Course.Status.PUBLISHED,
            is_published=True,
            price=0,
        )
        module = Module.objects.create(course=course, code='K8S-01', title='Pods and Services', order=1)
        Lesson.objects.create(module=module, order=1, title='Deploying Pods')

        # Teacher unpublishes
        self.client.force_login(self.teacher_1)
        res_unpub = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_unpub.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)

        # Student catalog: no longer appears
        student_client = Client()
        student_client.force_login(self.student)
        res_catalog = student_client.get(reverse('course-list'))
        self.assertNotIn(course, res_catalog.context['courses'])
        self.assertNotContains(res_catalog, 'Kubernetes for Developers')

        # Student detail: returns 404
        res_detail = student_client.get(reverse('course-detail', kwargs={'slug': course.slug}))
        self.assertEqual(res_detail.status_code, 404)

        # Teacher re-publishes
        self.client.force_login(self.teacher_1)
        res_repub = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_repub.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, Course.Status.PUBLISHED)
        self.assertTrue(course.is_published)

        # Student catalog: reappears
        student_client_2 = Client()
        student_client_2.force_login(self.student)
        res_catalog_2 = student_client_2.get(reverse('course-list'))
        self.assertIn(course, res_catalog_2.context['courses'])
        self.assertContains(res_catalog_2, 'Kubernetes for Developers')

    def test_teacher_cannot_publish_or_unpublish_another_teacher_course(self):
        """Teacher 2 cannot publish or unpublish Teacher 1's course."""
        course = Course.objects.create(
            title='Teacher 1 Private Program',
            slug='teacher-1-private-program',
            owner=self.teacher_1,
            subject=self.subject,
            status=Course.Status.DRAFT,
            is_published=False,
            price=0,
        )
        module = Module.objects.create(course=course, code='MOD-01', title='Module 1', order=1)
        Lesson.objects.create(module=module, order=1, title='Lesson 1')

        # Teacher 2 attempts to publish Teacher 1's course
        self.client.force_login(self.teacher_2)
        res_hack = self.client.post(reverse('course-publish', kwargs={'slug': course.slug}))
        self.assertEqual(res_hack.status_code, 302)

        course.refresh_from_db()
        # Course remains Draft
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_published)
