from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.labs.models import Lab, LabCategory, LabDifficulty, LabInstance, LabTemplate
from apps.ctf.models import Challenge, ChallengeCategory, SolvedChallenge

User = get_user_model()


class LabViewsAndSandboxTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='lab_student',
            email='student@example.com',
            password='Password123!',
        )
        self.other_student = User.objects.create_user(
            username='other_student',
            email='other@example.com',
            password='Password123!',
        )

        self.template = LabTemplate.objects.create(
            name='Linux Privilege Escalation',
            slug='linux-priv-esc',
            category=LabCategory.LINUX,
            description='Kernel & SUID exploits.',
        )

        self.lab1 = Lab.objects.create(
            template=self.template,
            title='SUID Binary Exploitation',
            slug='suid-binary-exploitation',
            difficulty=LabDifficulty.EASY,
            points=50,
            is_active=True,
        )

        self.lab2 = Lab.objects.create(
            template=self.template,
            title='Kernel Race Condition Lab',
            slug='kernel-race-condition',
            difficulty=LabDifficulty.HARD,
            points=150,
            is_active=True,
        )

        # Attach CTF Challenge to lab1
        self.challenge = Challenge.objects.create(
            title='SUID Root Flag',
            slug='suid-root-flag',
            category=ChallengeCategory.LINUX,
            difficulty=LabDifficulty.EASY,
            points=50,
            lab=self.lab1,
            is_active=True,
        )

    def test_lab_list_view_and_filters(self):
        self.client.force_login(self.student)
        url = reverse('lab-list')

        # 1. Base list
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SUID Binary Exploitation')
        self.assertContains(response, 'Kernel Race Condition Lab')
        self.assertEqual(response.context['total_labs_count'], 2)
        self.assertEqual(response.context['total_points_pool'], 200)

        # 2. Search filter
        res_search = self.client.get(url + '?q=SUID')
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.context['labs']), 1)
        self.assertEqual(res_search.context['labs'][0].id, self.lab1.id)

        # 3. Difficulty filter
        res_diff = self.client.get(url + '?difficulty=hard')
        self.assertEqual(res_diff.status_code, 200)
        self.assertEqual(len(res_diff.context['labs']), 1)
        self.assertEqual(res_diff.context['labs'][0].id, self.lab2.id)

    def test_lab_active_instance_banner_and_solved_status(self):
        self.client.force_login(self.student)
        now = timezone.now()

        # Mark challenge solved
        SolvedChallenge.objects.create(user=self.student, challenge=self.challenge, points_awarded=50)

        # Create active running instance for lab2
        instance = LabInstance.objects.create(
            lab=self.lab2,
            user=self.student,
            status='running',
            target_ip='10.10.10.25',
            started_at=now,
            expires_at=now + timedelta(minutes=60),
        )

        # Verify list shows active banner and solved lab ID
        response = self.client.get(reverse('lab-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.lab1.id, response.context['solved_lab_ids'])
        self.assertIsNotNone(response.context['active_instance'])
        self.assertEqual(response.context['active_instance'].id, instance.id)
        self.assertContains(response, 'Active Container Sandbox Running')
        self.assertContains(response, '10.10.10.25')

    def test_lab_extend_view_lifecycle(self):
        self.client.force_login(self.student)
        now = timezone.now()

        instance = LabInstance.objects.create(
            lab=self.lab1,
            user=self.student,
            status='running',
            started_at=now,
            expires_at=now + timedelta(minutes=30),
            extensions_used=0,
        )

        extend_url = reverse('lab-extend', kwargs={'instance_id': instance.id})

        # 1. Successful extension
        orig_expires = instance.expires_at
        response = self.client.post(extend_url)
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.extensions_used, 1)
        self.assertTrue(instance.expires_at > orig_expires)

        # 2. Second extension (max = 2)
        response = self.client.post(extend_url)
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.extensions_used, 2)

        # 3. Third extension should be blocked
        third_expires = instance.expires_at
        response = self.client.post(extend_url)
        self.assertEqual(response.status_code, 302)
        instance.refresh_from_db()
        self.assertEqual(instance.extensions_used, 2)
        self.assertEqual(instance.expires_at, third_expires)

        # 4. Other student cannot extend
        self.client.force_login(self.other_student)
        response_other = self.client.post(extend_url)
        self.assertEqual(response_other.status_code, 404)
