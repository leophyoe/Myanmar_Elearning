from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.accounts.models import User, RoleChoices
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabObjective,
    LabFlag, FlagType, LabInstance, LabInstanceStatus
)
from apps.labs.docker_service import docker_service, DockerSandboxService


class Phase3BDockerSandboxServiceTestCase(TestCase):
    """
    Validates Docker Sandbox Engine orchestration, security boundaries, and TTL lifecycle.
    """
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="ciso.boss@futuretech.edu", username="ciso_boss",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="cadet.neo@futuretech.edu", username="cadet_neo",
            role=RoleChoices.STUDENT
        )
        self.cat = LabCategory.objects.create(name="Web Exploitation", slug="web-exploit")
        self.lab = Lab.objects.create(
            name="DVWA Vulnerable Target",
            slug="dvwa-test-target",
            category=self.cat,
            difficulty=LabDifficulty.BEGINNER,
            type=LabType.GUIDED,
            docker_image="futuretech/dvwa-target:1.0",
            cpu_limit=Decimal('1.0'),
            memory_limit_mb=1024,
            max_runtime_minutes=60,
            points=100,
            created_by=self.instructor,
            is_published=True
        )

    def test_allowlisted_image_validation(self):
        # Allowlisted image passes
        docker_service.validate_lab_image(self.lab)

        # Unapproved / arbitrary image is rejected with ValidationError
        self.lab.docker_image = "malicious/cryptominer:latest"
        with self.assertRaises(ValidationError):
            docker_service.validate_lab_image(self.lab)

    def test_start_lab_instance(self):
        instance = docker_service.start_lab(self.student, self.lab)
        self.assertIsNotNone(instance)
        self.assertEqual(instance.status, LabInstanceStatus.RUNNING)
        self.assertEqual(instance.student, self.student)
        self.assertEqual(instance.lab, self.lab)
        self.assertTrue(instance.assigned_ip.startswith("10.10.") or instance.assigned_ip == "127.0.0.1")
        self.assertIsNotNone(instance.started_at)
        self.assertIsNotNone(instance.expires_at)
        self.assertTrue(instance.expires_at > instance.started_at)

    def test_concurrent_lab_restriction(self):
        # Start first lab
        docker_service.start_lab(self.student, self.lab)

        # Create second lab
        lab2 = Lab.objects.create(
            name="Second Machine", slug="second-machine",
            category=self.cat, docker_image="futuretech/linux-privesc-target:1.0",
            created_by=self.instructor, is_published=True
        )

        # Attempting to start second concurrent lab must raise ValidationError
        with self.assertRaises(ValidationError):
            docker_service.start_lab(self.student, lab2)

    def test_stop_lab_instance(self):
        instance = docker_service.start_lab(self.student, self.lab)
        success = docker_service.stop_lab(instance)
        self.assertTrue(success)

        instance.refresh_from_db()
        self.assertEqual(instance.status, LabInstanceStatus.STOPPED)
        self.assertIsNotNone(instance.stopped_at)

    def test_reset_lab_instance(self):
        instance = docker_service.start_lab(self.student, self.lab)
        first_uuid = instance.uuid

        reset_inst = docker_service.reset_lab(instance)
        self.assertEqual(reset_inst.status, LabInstanceStatus.RUNNING)
        self.assertNotEqual(reset_inst.uuid, first_uuid)

    def test_extend_lab_instance(self):
        instance = docker_service.start_lab(self.student, self.lab)
        original_expires = instance.expires_at

        extended = docker_service.extend_lab(instance, minutes=30)
        self.assertTrue(extended.expires_at > original_expires)

    def test_cleanup_expired_instances(self):
        instance = docker_service.start_lab(self.student, self.lab)
        # Artificially expire the instance in the past
        past_time = timezone.now() - timedelta(minutes=10)
        LabInstance.objects.filter(id=instance.id).update(expires_at=past_time)

        reaped = docker_service.cleanup_expired_instances()
        self.assertEqual(reaped, 1)

        instance.refresh_from_db()
        self.assertEqual(instance.status, LabInstanceStatus.EXPIRED)


class Phase3BWebLifecycleViewsTestCase(TestCase):
    """
    Tests HTTP endpoints for student lab control (Start, Stop, Reset, Extend, Status, Terminal).
    """
    def setUp(self):
        self.student = User.objects.create_user(
            email="cadet.trinity@futuretech.edu", username="cadet_trinity",
            role=RoleChoices.STUDENT
        )
        self.client = Client()
        self.client.force_login(self.student)
        self.cat = LabCategory.objects.create(name="Binary Defense", slug="bin-def")
        self.lab = Lab.objects.create(
            name="Stack Canary Sandbox", slug="stack-canary-sandbox",
            category=self.cat, docker_image="futuretech/dvwa-target:1.0",
            created_by=self.student, is_published=True, max_runtime_minutes=60
        )

    def test_start_lab_view_post(self):
        url = reverse('labs:lab-start', kwargs={'slug': self.lab.slug})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        instance = LabInstance.objects.filter(student=self.student, lab=self.lab).first()
        self.assertIsNotNone(instance)
        self.assertEqual(instance.status, LabInstanceStatus.RUNNING)

    def test_extend_lab_view_post(self):
        # Start first
        docker_service.start_lab(self.student, self.lab)
        url = reverse('labs:lab-extend', kwargs={'slug': self.lab.slug})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_reset_lab_view_post(self):
        docker_service.start_lab(self.student, self.lab)
        url = reverse('labs:lab-reset', kwargs={'slug': self.lab.slug})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

    def test_stop_lab_view_post(self):
        docker_service.start_lab(self.student, self.lab)
        url = reverse('labs:lab-stop', kwargs={'slug': self.lab.slug})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        instance = LabInstance.objects.filter(student=self.student, lab=self.lab).first()
        self.assertEqual(instance.status, LabInstanceStatus.STOPPED)

    def test_lab_status_view_json(self):
        # When stopped
        url = reverse('labs:lab-status', kwargs={'slug': self.lab.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_running'])

        # When running
        docker_service.start_lab(self.student, self.lab)
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['is_running'])
        self.assertIn("10.10.", resp2.json()['assigned_ip'])

    def test_lab_terminal_view(self):
        docker_service.start_lab(self.student, self.lab)
        url = reverse('labs:lab-terminal', kwargs={'slug': self.lab.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/lab_terminal.html')

    def test_cleanup_management_command(self):
        call_command('cleanup_expired_labs')

