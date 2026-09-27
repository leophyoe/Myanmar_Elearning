from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User, RoleChoices
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabAccessType,
    LabInstance, LabInstanceStatus, LabSubmission, CTFScore
)
from apps.labs.docker_service import docker_service
from apps.labs.providers import get_lab_provider, OWASPJuiceShopProvider, WebApplicationLabProvider


class OWASPJuiceShopProviderTestCase(TestCase):
    """
    Validates OWASPJuiceShopProvider architecture, image allowlisting,
    dynamic instance flags, and AI Tutor hint generation.
    """
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor.juice@futuretech.edu",
            username="juice_instructor",
            role=RoleChoices.INSTRUCTOR,
            is_staff=True
        )
        self.student_a = User.objects.create_user(
            email="student.alice@futuretech.edu",
            username="alice_sec",
            role=RoleChoices.STUDENT
        )
        self.student_b = User.objects.create_user(
            email="student.bob@futuretech.edu",
            username="bob_sec",
            role=RoleChoices.STUDENT
        )

        self.category = LabCategory.objects.create(
            name="Web Application Security",
            slug="web-application-security"
        )
        self.lab = Lab.objects.create(
            name="OWASP Juice Shop: Web Security Range",
            slug="owasp-juice-shop",
            category=self.category,
            difficulty=LabDifficulty.BEGINNER,
            type=LabType.WEB_APPLICATION,
            docker_image="bkimminich/juice-shop:v17.1.1",
            access_type=LabAccessType.WEB,
            cpu_limit=Decimal('1.0'),
            memory_limit_mb=1024,
            storage_limit_mb=2048,
            max_runtime_minutes=120,
            points=500,
            created_by=self.instructor,
            is_published=True
        )

    def test_provider_factory_and_properties(self):
        provider = get_lab_provider(self.lab)
        self.assertIsInstance(provider, OWASPJuiceShopProvider)
        self.assertEqual(provider.internal_web_port, 3000)
        self.assertEqual(provider.IMAGE_NAME, "bkimminich/juice-shop:v17.1.1")
        self.assertGreaterEqual(len(provider.CHALLENGES), 5)

    def test_image_allowlisting(self):
        self.assertIn("bkimminich/juice-shop:v17.1.1", docker_service.DEFAULT_ALLOWLISTED_IMAGES)
        # Lab passes validation
        docker_service.validate_lab_image(self.lab)

    def test_start_juice_shop_instance_via_provider(self):
        provider = get_lab_provider(self.lab)
        instance = provider.start(self.student_a, self.lab)

        self.assertIsNotNone(instance)
        self.assertEqual(instance.status, LabInstanceStatus.RUNNING)
        self.assertEqual(instance.student, self.student_a)
        self.assertEqual(instance.lab, self.lab)
        self.assertEqual(instance.access_url, f"/labs/i/{instance.uuid}/")
        self.assertTrue(instance.is_running)
        self.assertFalse(instance.is_expired)

    def test_dynamic_flag_generation_and_instance_binding(self):
        provider = OWASPJuiceShopProvider()
        inst_a = provider.start(self.student_a, self.lab)

        # Instance B for Bob
        lab2 = Lab.objects.create(
            name="Second Target",
            slug="second-target-lab",
            category=self.category,
            type=LabType.WEB_APPLICATION,
            docker_image="bkimminich/juice-shop:v17.1.1",
            created_by=self.instructor,
            is_published=True
        )
        inst_b = provider.start(self.student_b, lab2)

        flag_a = provider.generate_dynamic_flag(inst_a, "scoreboard")
        flag_b = provider.generate_dynamic_flag(inst_b, "scoreboard")

        # Dynamic flags must be distinct because instance UUIDs differ
        self.assertNotEqual(flag_a, flag_b)
        self.assertTrue(flag_a.startswith("FTACK{js_scoreboard_"))
        self.assertTrue(flag_b.startswith("FTACK{js_scoreboard_"))

        # Verify Alice's flag succeeds on Alice's instance
        valid_a, ch_a = provider.verify_flag(inst_a, flag_a, "scoreboard")
        self.assertTrue(valid_a)
        self.assertEqual(ch_a["id"], "scoreboard")

        # Flag replay attack: Bob's flag on Alice's instance must fail
        valid_replay, _ = provider.verify_flag(inst_a, flag_b, "scoreboard")
        self.assertFalse(valid_replay)

    def test_ai_tutor_hints_progression(self):
        provider = OWASPJuiceShopProvider()
        h1 = provider.get_hint("admin_sqli", 1)
        self.assertEqual(h1["level"], 1)
        self.assertEqual(h1["penalty_percent"], 0)
        self.assertIn("authentication", h1["hint"].lower())

        h2 = provider.get_hint("admin_sqli", 2)
        self.assertEqual(h2["level"], 2)
        self.assertEqual(h2["penalty_percent"], 10)

        h3 = provider.get_hint("admin_sqli", 3)
        self.assertEqual(h3["level"], 3)
        self.assertEqual(h3["penalty_percent"], 25)

        # Ensure no raw flag leakage
        self.assertNotIn("FTACK{", h1["hint"])
        self.assertNotIn("FTACK{", h2["hint"])
        self.assertNotIn("FTACK{", h3["hint"])

    def test_health_check(self):
        provider = OWASPJuiceShopProvider()
        instance = provider.start(self.student_a, self.lab)
        health = provider.health_check(instance)

        self.assertTrue(health["is_healthy"])
        self.assertTrue(health["is_ready"])
        self.assertEqual(health["service_name"], "OWASP Juice Shop")
        self.assertEqual(health["internal_port"], 3000)
        self.assertEqual(health["gateway_url"], f"/labs/i/{instance.uuid}/")


class OWASPJuiceShopGatewaySecurityTestCase(TestCase):
    """
    Validates cross-student isolation, gateway reverse proxy access controls,
    and flag submissions via /labs/i/<token>/.
    """
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="ciso@futuretech.edu", username="ciso_lead",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student_alice = User.objects.create_user(
            email="alice@futuretech.edu", username="alice",
            role=RoleChoices.STUDENT
        )
        self.student_bob = User.objects.create_user(
            email="bob@futuretech.edu", username="bob",
            role=RoleChoices.STUDENT
        )

        self.cat = LabCategory.objects.create(name="Web Security", slug="web-sec")
        self.lab = Lab.objects.create(
            name="OWASP Juice Shop",
            slug="owasp-juice-shop",
            category=self.cat,
            type=LabType.WEB_APPLICATION,
            docker_image="bkimminich/juice-shop:v17.1.1",
            created_by=self.instructor,
            is_published=True
        )

        provider = get_lab_provider(self.lab)
        self.alice_instance = provider.start(self.student_alice, self.lab)

    def test_unauthenticated_gateway_redirects(self):
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})
        response = self.client.get(gateway_url)
        # Unauthenticated users must be redirected to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_owner_access_permitted(self):
        self.client.force_login(self.student_alice)
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})
        response = self.client.get(gateway_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OWASP Juice Shop")
        self.assertContains(response, "Score Board Discovery")

    def test_cross_student_access_forbidden(self):
        # Bob tries to access Alice's isolated lab environment
        self.client.force_login(self.student_bob)
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})
        response = self.client.get(gateway_url)

        # STRICT ISOLATION REQUIREMENT: 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn("Security Isolation Policy", response.content.decode())

    def test_staff_access_permitted_for_supervision(self):
        self.client.force_login(self.instructor)
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})
        response = self.client.get(gateway_url)
        self.assertEqual(response.status_code, 200)

    def test_flag_submission_success(self):
        self.client.force_login(self.student_alice)
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})

        provider = OWASPJuiceShopProvider()
        expected_flag = provider.generate_dynamic_flag(self.alice_instance, "scoreboard")

        response = self.client.post(gateway_url, {
            'challenge_id': 'scoreboard',
            'flag': expected_flag
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            LabSubmission.objects.filter(
                lab=self.lab,
                student=self.student_alice,
                is_correct=True,
                points_awarded=50
            ).exists()
        )

        score = CTFScore.objects.get(student=self.student_alice)
        self.assertEqual(score.points, 50)

    def test_flag_submission_incorrect(self):
        self.client.force_login(self.student_alice)
        gateway_url = reverse('labs:lab-gateway', kwargs={'token': self.alice_instance.uuid})

        response = self.client.post(gateway_url, {
            'challenge_id': 'scoreboard',
            'flag': 'FTACK{wrong_flag_value}'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            LabSubmission.objects.filter(
                lab=self.lab,
                student=self.student_alice,
                is_correct=False,
                points_awarded=0
            ).exists()
        )

    def test_ai_tutor_hint_endpoint_isolation(self):
        # Alice can fetch hint
        self.client.force_login(self.student_alice)
        hint_url = reverse('labs:lab-ai-hint', kwargs={'token': self.alice_instance.uuid})
        response = self.client.get(f"{hint_url}?challenge_id=scoreboard&level=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["challenge_id"], "scoreboard")
        self.assertIn("routing", data["hint"].lower())

        # Bob accessing Alice's hint endpoint is forbidden
        self.client.force_login(self.student_bob)
        response_bob = self.client.get(f"{hint_url}?challenge_id=scoreboard&level=1")
        self.assertEqual(response_bob.status_code, 403)

