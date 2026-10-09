from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from apps.courses.models import Subject, Course, Enrollment
from apps.courses.selectors import (
    get_published_courses,
    get_featured_courses,
    get_popular_courses,
    get_new_courses,
    get_free_courses,
    get_popular_categories,
    get_top_instructors,
)

User = get_user_model()


class CourseDiscoveryAndCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.instructor = User.objects.create_user(
            username='prof_kyaw',
            email='kyaw@example.com',
            password='Password123!',
            first_name='Kyaw',
            last_name='Zayar',
        )

        cls.student = User.objects.create_user(
            username='student_mgmg',
            email='mgmg@example.com',
            password='Password123!',
        )

        cls.subject_python, _ = Subject.objects.get_or_create(
            slug='python-programming',
            defaults={
                'title': 'Python Programming',
                'kind': Subject.Kind.GENERAL,
                'order': 1,
                'is_active': True,
            }
        )

        cls.subject_cyber, _ = Subject.objects.get_or_create(
            slug='cyber-security',
            defaults={
                'title': 'Cyber Security',
                'kind': Subject.Kind.CYBER,
                'order': 2,
                'is_active': True,
            }
        )

        # 1. Paid course with discount
        cls.course_paid_discount = Course.objects.create(
            title='Advanced Python Engineering',
            slug='advanced-python-engineering',
            subject=cls.subject_python,
            owner=cls.instructor,
            status=Course.Status.PUBLISHED,
            is_published=True,
            level=Course.Level.ADVANCED,
            price=Decimal('50000.00'),
            discount_price=Decimal('35000.00'),
            duration_months=3,
        )

        # 2. Paid course without discount
        cls.course_paid_full = Course.objects.create(
            title='Network Defense Masterclass',
            slug='network-defense-masterclass',
            subject=cls.subject_cyber,
            owner=cls.instructor,
            status=Course.Status.PUBLISHED,
            is_published=True,
            level=Course.Level.INTERMEDIATE,
            price=Decimal('80000.00'),
            discount_price=None,
            duration_months=4,
            is_official=True,
        )

        # 3. Free course
        cls.course_free = Course.objects.create(
            title='Python for Absolute Beginners',
            slug='python-for-absolute-beginners',
            subject=cls.subject_python,
            owner=cls.instructor,
            status=Course.Status.PUBLISHED,
            is_published=True,
            level=Course.Level.BEGINNER,
            price=Decimal('0.00'),
            duration_months=1,
        )

        # Enroll student in free course to give it popularity
        Enrollment.objects.create(
            course=cls.course_free,
            student=cls.student,
            status=Enrollment.Status.ACTIVE,
        )

    def setUp(self):
        self.client = Client()

    def test_course_properties(self):
        """Verify effective_price, has_discount, is_new_course, and is_free properties."""
        # Paid course with discount
        self.assertEqual(self.course_paid_discount.effective_price, Decimal('35000.00'))
        self.assertTrue(self.course_paid_discount.has_discount)
        self.assertFalse(self.course_paid_discount.is_free)

        # Paid course without discount
        self.assertEqual(self.course_paid_full.effective_price, Decimal('80000.00'))
        self.assertFalse(self.course_paid_full.has_discount)
        self.assertFalse(self.course_paid_full.is_free)

        # Free course
        self.assertEqual(self.course_free.effective_price, Decimal('0.00'))
        self.assertFalse(self.course_free.has_discount)
        self.assertTrue(self.course_free.is_free)

        # Course is newly created
        self.assertTrue(self.course_free.is_new_course)

    def test_selectors_price_filter(self):
        """Verify get_published_courses filters by free vs paid correctly."""
        free_qs = get_published_courses(price_type='free')
        self.assertIn(self.course_free, free_qs)
        self.assertNotIn(self.course_paid_full, free_qs)

        paid_qs = get_published_courses(price_type='paid')
        self.assertIn(self.course_paid_discount, paid_qs)
        self.assertIn(self.course_paid_full, paid_qs)
        self.assertNotIn(self.course_free, paid_qs)

    def test_selectors_sorting(self):
        """Verify get_published_courses sorts by popular, price, and title."""
        # Popular sorts by enrollment count descending
        popular_qs = list(get_published_courses(sort='popular'))
        self.assertEqual(popular_qs[0], self.course_free)

        # Price ascending
        price_asc = list(get_published_courses(sort='price_asc'))
        self.assertEqual(price_asc[0], self.course_free)
        self.assertEqual(price_asc[-1], self.course_paid_full)

        # Price descending
        price_desc = list(get_published_courses(sort='price_desc'))
        self.assertEqual(price_desc[0], self.course_paid_full)

        # Title alphabetical
        title_qs = list(get_published_courses(sort='title'))
        self.assertEqual(title_qs[0], self.course_paid_discount)  # "Advanced..."

    def test_discovery_selectors(self):
        """Verify featured, popular, new, free, categories, and top instructors selectors."""
        featured = list(get_featured_courses())
        self.assertIn(self.course_paid_full, featured)  # is_official=True

        popular = list(get_popular_courses())
        self.assertTrue(len(popular) > 0)
        self.assertEqual(popular[0], self.course_free)

        free = list(get_free_courses())
        self.assertIn(self.course_free, free)

        new = list(get_new_courses())
        self.assertEqual(len(new), 3)

        categories = list(get_popular_categories())
        self.assertEqual(len(categories), 2)
        # Python subject has 2 courses, should be first
        self.assertEqual(categories[0], self.subject_python)

        instructors = list(get_top_instructors())
        self.assertEqual(len(instructors), 1)
        self.assertEqual(instructors[0], self.instructor)
        self.assertEqual(instructors[0].courses_count, 3)

    def test_course_list_view_and_filtering(self):
        """Verify CourseListView handles filters, search, and returns HTTP 200."""
        # Basic catalog request
        response = self.client.get(reverse('course-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/course_list.html')
        self.assertTemplateUsed(response, 'courses/_course_card.html')

        # Filter by category
        res_cat = self.client.get(reverse('course-list') + '?category=python-programming')
        self.assertEqual(res_cat.status_code, 200)
        self.assertEqual(len(res_cat.context['courses']), 2)

        # Filter by price_type=free
        res_free = self.client.get(reverse('course-list') + '?price_type=free')
        self.assertEqual(res_free.status_code, 200)
        self.assertEqual(len(res_free.context['courses']), 1)
        self.assertEqual(res_free.context['courses'][0], self.course_free)

        # Search query
        res_search = self.client.get(reverse('course-list') + '?q=Defense')
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.context['courses']), 1)
        self.assertEqual(res_search.context['courses'][0], self.course_paid_full)

    def test_landing_page_discovery_sections(self):
        """Verify LandingPageView provides all discovery querysets in context."""
        response = self.client.get(reverse('landing-page'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('featured_courses', response.context)
        self.assertIn('popular_courses', response.context)
        self.assertIn('new_courses', response.context)
        self.assertIn('free_courses', response.context)
        self.assertIn('popular_categories', response.context)
        self.assertIn('top_instructors', response.context)

    def test_course_detail_view(self):
        """Verify CourseDetailView renders successfully with dual mode styles."""
        response = self.client.get(reverse('course-detail', kwargs={'slug': self.course_paid_discount.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/course_detail.html')
        self.assertContains(response, 'Advanced Python Engineering')
        self.assertContains(response, '35000')
