from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.blog.models import Article, ArticleCategory
from apps.courses.models import Course
from apps.users.models import UserRole

User = get_user_model()


class KnowledgeHubModelAndPropertiesTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username='cyber_instructor',
            email='instructor@example.com',
            password='Password123!',
            first_name='Ko',
            last_name='Kyaw',
            role=UserRole.TEACHER,
        )
        self.category = ArticleCategory.objects.create(
            name='Cyber Defense',
            slug='cyber-defense',
            icon='shield',
            description='Defensive architecture and threat intelligence.',
        )
        self.course = Course.objects.create(
            title='Practical SOC Operations',
            slug='practical-soc-ops',
            description='Hands-on SOC triage and SIEM alert analysis.',
            certificate_eligible=True,
        )

    def test_category_creation_and_str(self):
        self.assertEqual(str(self.category), 'Cyber Defense')
        self.assertEqual(self.category.slug, 'cyber-defense')

    def test_article_creation_and_properties(self):
        article = Article.objects.create(
            title='Understanding Buffer Overflows in Linux',
            slug='understanding-buffer-overflows-linux',
            author=self.author,
            category=self.category,
            summary='An introduction to memory corruption vulnerabilities.',
            content='Step 1: Inspect stack memory with GDB...',
            reading_time_minutes=8,
            difficulty=Article.Difficulty.INTERMEDIATE,
            tags='linux, memory, exploitation, ctf',
            related_course=self.course,
            is_published=True,
        )
        self.assertEqual(str(article), 'Understanding Buffer Overflows in Linux')
        self.assertEqual(article.reading_time_display, '8 min read')
        self.assertEqual(article.tag_list, ['linux', 'memory', 'exploitation', 'ctf'])
        self.assertIsNotNone(article.published_at)
        self.assertEqual(article.related_course, self.course)


class KnowledgeHubViewsAndRoutingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username='dev_author',
            email='dev@example.com',
            password='Password123!',
            first_name='Min',
            last_name='Thuta',
            role=UserRole.STUDENT,
        )
        self.cat_web = ArticleCategory.objects.create(
            name='Web Engineering',
            slug='web-engineering',
            icon='code',
        )
        self.cat_cyber = ArticleCategory.objects.create(
            name='Penetration Testing',
            slug='pentesting',
            icon='terminal',
        )
        self.course = Course.objects.create(
            title='Web Penetration Testing & OWASP Top 10',
            slug='web-pentest-owasp',
            description='Practical security testing for modern web apps.',
        )

        self.article1 = Article.objects.create(
            title='SQL Injection Defense Cheat Sheet',
            slug='sqli-defense-cheat-sheet',
            author=self.author,
            category=self.cat_web,
            summary='Comprehensive guide to parameterized queries and ORMs.',
            content='Always use parameterized statements...',
            reading_time_minutes=6,
            difficulty=Article.Difficulty.BEGINNER,
            tags='sql, web, security, owasp',
            related_course=self.course,
            is_featured=True,
            is_published=True,
        )

        self.article2 = Article.objects.create(
            title='Advanced Reverse Engineering with Ghidra',
            slug='advanced-re-ghidra',
            author=self.author,
            category=self.cat_cyber,
            summary='Disassembling ELF binaries with Ghidra decompilation.',
            content='Load the binary into Ghidra and analyze the symbol table...',
            reading_time_minutes=12,
            difficulty=Article.Difficulty.ADVANCED,
            tags='ghidra, reverse, binary, ctf',
            is_featured=False,
            is_published=True,
        )

        self.draft_article = Article.objects.create(
            title='Draft Article Not Yet Published',
            slug='draft-article-unpublished',
            author=self.author,
            category=self.cat_web,
            summary='Work in progress.',
            content='Draft text...',
            is_published=False,
        )

    def test_hub_redirect_route(self):
        resp = self.client.get('/hub/')
        self.assertRedirects(resp, reverse('blog:article-list'), fetch_redirect_response=False)

    def test_article_list_view_and_catalog(self):
        url = reverse('blog:article-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Knowledge Hub')
        self.assertContains(resp, 'SQL Injection Defense Cheat Sheet')
        self.assertContains(resp, 'Advanced Reverse Engineering with Ghidra')
        # Drafts must NOT appear
        self.assertNotContains(resp, 'Draft Article Not Yet Published')

    def test_article_list_category_filter(self):
        url = reverse('blog:article-category', kwargs={'category_slug': 'pentesting'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Advanced Reverse Engineering with Ghidra')
        self.assertNotContains(resp, 'SQL Injection Defense Cheat Sheet')

    def test_article_list_search_query(self):
        url = reverse('blog:article-list')
        resp = self.client.get(url, {'q': 'ghidra'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Advanced Reverse Engineering with Ghidra')
        self.assertNotContains(resp, 'SQL Injection Defense Cheat Sheet')

    def test_article_list_difficulty_filter(self):
        url = reverse('blog:article-list')
        resp = self.client.get(url, {'difficulty': 'advanced'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Advanced Reverse Engineering with Ghidra')
        self.assertNotContains(resp, 'SQL Injection Defense Cheat Sheet')

    def test_article_detail_view_and_views_increment(self):
        url = reverse('blog:article-detail', kwargs={'slug': self.article1.slug})
        initial_views = self.article1.views_count
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SQL Injection Defense Cheat Sheet')
        self.assertContains(resp, 'Always use parameterized statements')
        self.assertContains(resp, 'Web Penetration Testing &amp; OWASP Top 10')
        self.assertContains(resp, 'About the Author')

        self.article1.refresh_from_db()
        self.assertEqual(self.article1.views_count, initial_views + 1)

    def test_unpublished_article_404_for_guests(self):
        url = reverse('blog:article-detail', kwargs={'slug': self.draft_article.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_portfolio_detail_shows_authored_articles(self):
        url = reverse('portfolio-detail', kwargs={'username': self.author.username})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Technical Tutorials &amp; Articles')
        self.assertContains(resp, 'SQL Injection Defense Cheat Sheet')
        self.assertContains(resp, 'Advanced Reverse Engineering with Ghidra')
        self.assertNotContains(resp, 'Draft Article Not Yet Published')
