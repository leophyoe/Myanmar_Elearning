from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.portfolio.models import PortfolioProject, Skill
from apps.users.models import UserRole

User = get_user_model()


class PublicPortfolioDirectoryTests(TestCase):
    def setUp(self):
        # Create student 1
        self.student1 = User.objects.create_user(
            username='student_alice',
            email='alice@example.com',
            password='Password123!',
            first_name='Alice',
            last_name='Security',
            role=UserRole.STUDENT,
        )
        self.student1.student_profile.bio = 'Aspiring SOC Analyst specializing in SIEM triage.'
        self.student1.student_profile.points = 150
        self.student1.student_profile.save()

        Skill.objects.create(
            owner=self.student1,
            name='Wazuh',
            level=4,
        )
        PortfolioProject.objects.create(
            owner=self.student1,
            title='Enterprise Wazuh Detection Rules',
            excerpt='Automated detection rules for MITRE ATT&CK techniques.',
            is_published=True,
        )

        # Create student 2
        self.student2 = User.objects.create_user(
            username='student_bob',
            email='bob@example.com',
            password='Password123!',
            first_name='Bob',
            last_name='Hacker',
            role=UserRole.STUDENT,
        )
        self.student2.student_profile.bio = 'Web penetration tester and bug hunter.'
        self.student2.student_profile.points = 320
        self.student2.student_profile.save()

        Skill.objects.create(
            owner=self.student2,
            name='Burp Suite',
            level=5,
        )

        # Create teacher
        self.teacher = User.objects.create_user(
            username='teacher_charlie',
            email='charlie@example.com',
            password='Password123!',
            first_name='Charlie',
            last_name='Lecturer',
            role=UserRole.TEACHER,
        )
        self.teacher.teacher_profile.title = 'Senior Cyber Range Instructor'
        self.teacher.teacher_profile.department = 'Offensive Security Department'
        self.teacher.teacher_profile.qualifications = 'OSCP, CISSP, 10 years experience.'
        self.teacher.teacher_profile.is_verified = True
        self.teacher.teacher_profile.save()

        Skill.objects.create(
            owner=self.teacher,
            name='Reverse Engineering',
            level=5,
        )

    def test_public_portfolio_directory_accessible_without_auth(self):
        """Unauthenticated guests can view the public portfolio directory."""
        response = self.client.get(reverse('portfolio-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Public Portfolios')
        self.assertContains(response, 'student_alice')
        self.assertContains(response, 'student_bob')
        self.assertContains(response, 'teacher_charlie')

    def test_public_portfolio_directory_search(self):
        """Guests can search users by username, bio, or skills."""
        response = self.client.get(reverse('portfolio-list'), {'q': 'Wazuh'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student_alice')
        self.assertNotContains(response, 'student_bob')

    def test_public_portfolio_directory_role_filter(self):
        """Filtering by role isolates students or instructors correctly."""
        # Students filter
        response = self.client.get(reverse('portfolio-list'), {'role': 'student'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'student_alice')
        self.assertContains(response, 'student_bob')
        self.assertNotContains(response, 'teacher_charlie')

        # Teachers filter
        response = self.client.get(reverse('portfolio-list'), {'role': 'teacher'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'teacher_charlie')
        self.assertNotContains(response, 'student_alice')
        self.assertNotContains(response, 'student_bob')

    def test_public_portfolio_directory_skill_filter(self):
        """Filtering by skill shows only profiles with matching competency."""
        response = self.client.get(reverse('portfolio-list'), {'skill': 'Reverse Engineering'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'teacher_charlie')
        self.assertNotContains(response, 'student_alice')

    def test_public_portfolio_detail_accessible_without_auth(self):
        """Unauthenticated guests can view an individual portfolio detail page with back link."""
        url = reverse('portfolio-detail', kwargs={'username': 'student_alice'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice')
        self.assertContains(response, 'Public Verified Portfolio')
        self.assertContains(response, reverse('portfolio-list'))

    def test_navbar_and_landing_contain_public_portfolio_links(self):
        """Landing page and navigation include public portfolio links for all guests."""
        response = self.client.get(reverse('landing-page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('portfolio-list'))
        self.assertContains(response, 'Explore Public Portfolios')

    def test_language_switch_and_talent_directory_bilingual_rendering(self):
        """Talent directory separates English and Myanmar text and supports language switching."""
        # 1. Check default English view
        res = self.client.get(reverse('portfolio-list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Verified Talent Directory')
        self.assertContains(res, 'အတည်ပြုပြီး ပရိုဖိုင်များ စာရင်း')
        self.assertContains(res, 'data-lang-toggle')
        self.assertContains(res, 'lang-badge-en')
        self.assertContains(res, 'lang-badge-my')
        # Ensure the old mixed string with slash is completely gone!
        self.assertNotContains(res, 'Verified Talent Directory / ကျောင်းသားနှင့် ဆရာများ ပရိုဖိုင်')

        # 2. Switch language to Myanmar via endpoint
        switch_res = self.client.get(reverse('set-language') + '?lang=my&next=' + reverse('portfolio-list'))
        self.assertEqual(switch_res.status_code, 302)
        self.assertEqual(switch_res.cookies['mel_lang'].value, 'my')

        # 3. Switch language back to English
        switch_en = self.client.get(reverse('set-language') + '?lang=en&next=' + reverse('portfolio-list'))
        self.assertEqual(switch_en.status_code, 302)
        self.assertEqual(switch_en.cookies['mel_lang'].value, 'en')

