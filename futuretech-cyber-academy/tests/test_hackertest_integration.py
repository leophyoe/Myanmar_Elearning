from django.test import TestCase, Client
from django.core.management import call_command
from django.urls import reverse
from apps.accounts.models import User, RoleChoices
from apps.labs.models import (
    ChallengeCategory, Challenge, ChallengeSubmission,
    ExternalResource, CTFScore
)


class HackerTestIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email="hackertest_student@futuretech.edu",
            username="htstudent",
            password="StudentPass123!",
            role=RoleChoices.STUDENT
        )

    def test_import_hackertest_resource_command(self):
        """Test import_hackertest_resource command creates ExternalResource and 8 original challenges."""
        call_command("import_hackertest_resource")

        # 1. Verify ExternalResource
        resource = ExternalResource.objects.filter(slug="hackertest").first()
        self.assertIsNotNone(resource)
        self.assertEqual(resource.name, "HackerTest")
        self.assertEqual(resource.url, "https://www.hackertest.net/")
        self.assertEqual(resource.source_type, "EXTERNAL_RESOURCE")
        self.assertEqual(resource.attribution, "HackerTest.net")
        self.assertTrue(resource.is_active)
        self.assertIn("Cyber Security Fundamentals", resource.tags)
        self.assertIn("Ethical Hacking", resource.tags)
        self.assertIn("Web Security", resource.tags)
        self.assertIn("Security Challenges", resource.tags)

        # 2. Verify 8 Future Tech Original Challenges
        ft_cat = ChallengeCategory.objects.filter(slug="future-tech-security-challenges").first()
        self.assertIsNotNone(ft_cat)
        self.assertEqual(ft_cat.name, "Future Tech Security Challenges")

        original_challenges = Challenge.objects.filter(category=ft_cat)
        self.assertEqual(original_challenges.count(), 8)

        expected_slugs = [
            "futuretech-web-header-analysis",
            "futuretech-suid-inspector",
            "futuretech-pcap-packet-stream",
            "futuretech-xor-keybreaker",
            "futuretech-jwt-algorithm-tampering",
            "futuretech-memory-string-carving",
            "futuretech-python-sandbox-jailbreak",
            "futuretech-cia-triad-classifier",
        ]
        for slug in expected_slugs:
            self.assertTrue(original_challenges.filter(slug=slug).exists(), f"Missing original challenge: {slug}")

    def test_idempotency_of_hackertest_import(self):
        """Test import_hackertest_resource can run repeatedly without creating duplicates."""
        call_command("import_hackertest_resource")
        call_command("import_hackertest_resource")

        self.assertEqual(ExternalResource.objects.filter(slug="hackertest").count(), 1)
        self.assertEqual(Challenge.objects.filter(category__slug="future-tech-security-challenges").count(), 8)

    def test_hackertest_endpoint_and_content_safeguards(self):
        """Test /challenges/hackertest/ renders with proper attribution, external link, and disclaimers."""
        call_command("import_hackertest_resource")
        url = reverse("hackertest-challenge")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/hackertest_resource.html")

        # Official URL and link
        self.assertContains(response, "https://www.hackertest.net/")
        self.assertContains(response, "Open HackerTest")

        # Upstream source attribution
        self.assertContains(response, "HackerTest.net")
        self.assertContains(response, "EXTERNAL_RESOURCE")

        # Not falsely attributed as Future Tech original content
        self.assertContains(response, "Source: <strong class=\"text-white\">HackerTest.net</strong>")
        self.assertContains(response, "Respect of Third-Party Terms")

        # Recommended for specific learning paths
        self.assertContains(response, "Cyber Security Fundamentals")
        self.assertContains(response, "Ethical Hacking")
        self.assertContains(response, "Web Security")
        self.assertContains(response, "Security Challenges")

        # Original challenges are featured
        self.assertContains(response, "Future Tech Security Challenges")
        self.assertContains(response, "FutureTech Web Header Analysis")

    def test_external_resource_does_not_modify_student_score(self):
        """Test accessing or linking external HackerTest resource does not award unearned points."""
        call_command("import_hackertest_resource")
        self.client.force_login(self.student)

        # Student accesses HackerTest portal
        url = reverse("hackertest-challenge")
        self.client.get(url)

        # Student should have 0 points / no submissions
        score = CTFScore.objects.filter(student=self.student).first()
        self.assertTrue(score is None or score.points == 0)
        self.assertEqual(ChallengeSubmission.objects.filter(student=self.student).count(), 0)

    def test_future_tech_original_challenge_solvable(self):
        """Test submitting a flag to an original Future Tech Security Challenge."""
        call_command("import_hackertest_resource")
        challenge = Challenge.objects.get(slug="futuretech-web-header-analysis")
        detail_url = reverse("labs:challenge-detail", kwargs={"slug": challenge.slug})

        self.client.force_login(self.student)

        # 1. Submit incorrect flag
        resp_bad = self.client.post(detail_url, {"flag": "FTACK{wrong_flag}"}, follow=True)
        self.assertContains(resp_bad, "Incorrect flag")
        self.assertFalse(ChallengeSubmission.objects.filter(challenge=challenge, student=self.student, is_correct=True).exists())

        # 2. Submit correct flag
        resp_good = self.client.post(detail_url, {"flag": "FTACK{csp_header_security_audited}"}, follow=True)
        self.assertContains(resp_good, "Flag verified")
        self.assertTrue(ChallengeSubmission.objects.filter(challenge=challenge, student=self.student, is_correct=True).exists())

        score = CTFScore.objects.get(student=self.student)
        self.assertEqual(score.points, 50)
        self.assertEqual(score.solves_count, 1)

