import hashlib
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.ctf.models import Challenge, ChallengeCategory, ChallengeDifficulty, SolvedChallenge
from apps.labs.models import Lab, LabCategory, LabTemplate

User = get_user_model()


class CtfBoardAndFlagTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='ctf_player',
            email='ctf@example.com',
            password='Password123!',
        )

        self.template = LabTemplate.objects.create(
            name='Web Exploitation Template',
            slug='web-exp-tmpl',
            category=LabCategory.WEB,
        )

        self.lab = Lab.objects.create(
            template=self.template,
            title='SQL Injection DVWA Lab',
            slug='sqli-dvwa-lab',
            points=100,
            is_active=True,
        )

        # Static flag challenge
        static_flag = "FTCR{sql_injection_master_2026}"
        self.challenge1 = Challenge.objects.create(
            title='SQL Injection Authentication Bypass',
            slug='sqli-auth-bypass',
            category=ChallengeCategory.WEB,
            difficulty=ChallengeDifficulty.MEDIUM,
            points=100,
            is_dynamic=False,
            flag_hash=hashlib.sha256(static_flag.encode()).hexdigest(),
            lab=self.lab,
            is_active=True,
        )

        # Another challenge
        self.challenge2 = Challenge.objects.create(
            title='Linux SUID Privesc Flag',
            slug='linux-suid-privesc',
            category=ChallengeCategory.LINUX,
            difficulty=ChallengeDifficulty.EASY,
            points=50,
            is_dynamic=False,
            flag_hash=hashlib.sha256(b"FTCR{suid_bin_owned}").hexdigest(),
            is_active=True,
        )

    def test_ctf_board_stats_and_grouping(self):
        self.client.force_login(self.student)
        url = reverse('ctf-board')

        # Initially 0 solved
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_challenges_count'], 2)
        self.assertEqual(response.context['total_points_available'], 150)
        self.assertEqual(response.context['user_points_earned'], 0)
        self.assertEqual(response.context['solved_count'], 0)
        self.assertEqual(response.context['completion_pct'], 0.0)

        # Mark challenge1 solved
        SolvedChallenge.objects.create(
            user=self.student,
            challenge=self.challenge1,
            points_awarded=100
        )

        # Board now reflects 100 points and 50% completion
        res_solved = self.client.get(url)
        self.assertEqual(res_solved.status_code, 200)
        self.assertEqual(res_solved.context['user_points_earned'], 100)
        self.assertEqual(res_solved.context['solved_count'], 1)
        self.assertEqual(res_solved.context['completion_pct'], 50.0)
        self.assertIn(self.challenge1.id, res_solved.context['solved_challenge_ids'])

    def test_flag_submit_verification(self):
        self.client.force_login(self.student)
        submit_url = reverse('flag-submit', kwargs={'challenge_id': self.challenge1.id})

        # 1. Incorrect flag
        res_wrong = self.client.post(submit_url, {'flag': 'FTCR{wrong_flag_attempt}'})
        self.assertEqual(res_wrong.status_code, 200)
        data_wrong = res_wrong.json()
        self.assertFalse(data_wrong.get('success', False))

        # 2. Correct flag with whitespace
        res_correct = self.client.post(submit_url, {'flag': '  FTCR{sql_injection_master_2026}  '})
        self.assertEqual(res_correct.status_code, 200)
        data_correct = res_correct.json()
        self.assertTrue(data_correct.get('success', False))
        self.assertEqual(data_correct.get('points'), 100)
        self.assertTrue(SolvedChallenge.objects.filter(user=self.student, challenge=self.challenge1).exists())
