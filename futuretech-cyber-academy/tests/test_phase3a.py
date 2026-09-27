import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User, RoleChoices
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabObjective,
    LabHint, LabAttachment, LabFlag, FlagType, LabInstance,
    LabInstanceStatus, LabAccess, LabSubmission,
    ChallengeCategory, Challenge, ChallengeSubmission,
    CTFEvent, CTFEventStatus, CTFScore, Badge, StudentBadge
)
try:
    from apps.labs.serializers import LabDetailSerializer, ChallengeDetailSerializer, LabListSerializer
    DRF_AVAILABLE = True
except (ImportError, AttributeError):
    DRF_AVAILABLE = False
    LabDetailSerializer = None
    ChallengeDetailSerializer = None
    LabListSerializer = None


class Phase3AModelsTestCase(TestCase):
    """
    Validates complete data model integrity for Phase 3A Cyber Range & CTF platform.
    """
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor@futuretech.edu", username="instructor_ciso",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="cadet@futuretech.edu", username="cadet_zero",
            role=RoleChoices.STUDENT
        )
        self.category = LabCategory.objects.create(
            name="Web Application Security", slug="web-app-sec",
            description="OWASP Top 10 hands-on testing targets."
        )

    def test_lab_creation_with_quotas(self):
        lab = Lab.objects.create(
            name="SQL Injection Sandbox",
            slug="sqli-sandbox",
            category=self.category,
            difficulty=LabDifficulty.BEGINNER,
            type=LabType.GUIDED,
            docker_image="futuretech/lab-sqli-vulnerable:1.0",
            cpu_limit=Decimal('1.5'),
            memory_limit_mb=1024,
            storage_limit_mb=2048,
            max_runtime_minutes=60,
            points=100,
            created_by=self.instructor,
            is_published=True
        )
        self.assertEqual(lab.name, "SQL Injection Sandbox")
        self.assertEqual(lab.cpu_limit, Decimal('1.5'))
        self.assertEqual(lab.memory_limit_mb, 1024)
        self.assertTrue(lab.is_published)

    def test_lab_objective_and_hints(self):
        lab = Lab.objects.create(
            name="XSS Playground", slug="xss-playground",
            category=self.category, created_by=self.instructor
        )
        obj = LabObjective.objects.create(
            lab=lab, title="Steal Admin Cookie", order=1, points=50, required=True
        )
        hint = LabHint.objects.create(
            lab=lab, order=1, hint_text="Check document.cookie in alert payload.",
            penalty_percent=15
        )
        self.assertEqual(lab.objectives.count(), 1)
        self.assertEqual(lab.hints.count(), 1)
        self.assertEqual(hint.penalty_percent, 15)

    def test_lab_flags_and_submissions(self):
        lab = Lab.objects.create(
            name="Buffer Overflow 101", slug="bof-101",
            category=self.category, created_by=self.instructor
        )
        flag = LabFlag.objects.create(
            lab=lab, flag_type=FlagType.STATIC_FLAG,
            static_flag="FTCSA{b0f_r3t_2_l1bc_pwnd}", points=150
        )
        submission = LabSubmission.objects.create(
            lab=lab, student=self.student,
            flag_submitted="FTCSA{b0f_r3t_2_l1bc_pwnd}",
            is_correct=True, points_awarded=150
        )
        self.assertTrue(submission.is_correct)
        self.assertEqual(submission.points_awarded, 150)

    def test_challenge_and_submission(self):
        cat = ChallengeCategory.objects.create(name="Cryptography", slug="crypto")
        challenge = Challenge.objects.create(
            title="RSA Small e Vulnerability", slug="rsa-small-e",
            category=cat, difficulty=LabDifficulty.MEDIUM,
            points=200, flag="FTCSA{h4st4d_br04dc4st_4tt4ck}",
            is_active=True
        )
        self.assertEqual(challenge.points, 200)
        self.assertTrue(challenge.is_active)

    def test_ctf_event_and_leaderboard_score(self):
        now = timezone.now()
        event = CTFEvent.objects.create(
            name="Academy Cyber Battle 2026", slug="battle-2026",
            description="Annual cyber security championship.",
            start_time=now, end_time=now + timedelta(hours=24),
            status=CTFEventStatus.LIVE, max_participants=50
        )
        score = CTFScore.objects.create(
            student=self.student, points=350, lab_points=150,
            challenge_points=200, solves_count=1, labs_completed_count=1
        )
        self.assertEqual(event.status, CTFEventStatus.LIVE)
        self.assertEqual(score.points, 350)


class Phase3ASecurityAndSecrecyTestCase(TestCase):
    """
    Zero-Trust Security Verification:
    Ensures secret flags are NEVER leaked in serializers or client contexts.
    """
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="ciso@futuretech.edu", username="ciso",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="operator@futuretech.edu", username="operator1",
            role=RoleChoices.STUDENT
        )
        self.category = LabCategory.objects.create(name="Network Defense", slug="net-def")
        self.lab = Lab.objects.create(
            name="Metasploitable Target", slug="metasploitable-target",
            category=self.category, created_by=self.instructor, is_published=True
        )
        self.secret_flag = "FTACK{ultra_secret_root_flag_do_not_leak}"
        self.flag = LabFlag.objects.create(
            lab=self.lab, static_flag=self.secret_flag, points=100
        )
        self.challenge_cat = ChallengeCategory.objects.create(name="Forensics", slug="forensics")
        self.challenge_secret = "FTACK{secret_pcap_stream_flag}"
        self.challenge = Challenge.objects.create(
            title="Suspicious DNS Tunnel", slug="dns-tunnel",
            category=self.challenge_cat, points=100,
            flag=self.challenge_secret, is_active=True
        )

    def test_serializer_never_exposes_lab_flag(self):
        if not DRF_AVAILABLE or LabDetailSerializer is None:
            self.skipTest("rest_framework not installed in this environment")
        serializer = LabDetailSerializer(self.lab)
        data_str = str(serializer.data)
        self.assertNotIn(self.secret_flag, data_str)
        self.assertNotIn("static_flag", serializer.data)

    def test_serializer_never_exposes_challenge_flag(self):
        if not DRF_AVAILABLE or ChallengeDetailSerializer is None:
            self.skipTest("rest_framework not installed in this environment")
        serializer = ChallengeDetailSerializer(self.challenge)
        self.assertNotIn("flag", serializer.data)
        data_str = str(serializer.data)
        self.assertNotIn(self.challenge_secret, data_str)

    def test_view_context_never_exposes_challenge_flag(self):
        client = Client()
        client.force_login(self.student)
        url = reverse('labs:challenge-detail', kwargs={'slug': self.challenge.slug})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Verify secret flag string does NOT appear anywhere in the rendered HTML output
        self.assertNotContains(resp, self.challenge_secret)


class Phase3AFlagScoringTestCase(TestCase):
    """
    Tests web flag submission, instant evaluation, CTFScore updates, and duplicate prevention.
    """
    def setUp(self):
        self.student = User.objects.create_user(
            email="student1@futuretech.edu", username="student1",
            role=RoleChoices.STUDENT
        )
        self.client = Client()
        self.client.force_login(self.student)
        self.cat = ChallengeCategory.objects.create(name="Web Exploitation", slug="web")
        self.challenge = Challenge.objects.create(
            title="Command Injection", slug="cmdi-challenge",
            category=self.cat, points=150,
            flag="FTACK{c0mm4nd_1nj3ct10n_succ3ss}", is_active=True
        )

    def test_correct_flag_submission_awards_points(self):
        url = reverse('labs:challenge-detail', kwargs={'slug': self.challenge.slug})
        resp = self.client.post(url, {'flag': 'FTACK{c0mm4nd_1nj3ct10n_succ3ss}'}, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Check submission record
        sub = ChallengeSubmission.objects.filter(challenge=self.challenge, student=self.student).first()
        self.assertIsNotNone(sub)
        self.assertTrue(sub.is_correct)
        self.assertEqual(sub.points_awarded, 150)

        # Check CTFScore ledger
        score = CTFScore.objects.get(student=self.student)
        self.assertEqual(score.points, 150)
        self.assertEqual(score.challenge_points, 150)
        self.assertEqual(score.solves_count, 1)

    def test_incorrect_flag_submission_awards_zero_points(self):
        url = reverse('labs:challenge-detail', kwargs={'slug': self.challenge.slug})
        resp = self.client.post(url, {'flag': 'WRONG_FLAG'}, follow=True)
        self.assertEqual(resp.status_code, 200)

        sub = ChallengeSubmission.objects.filter(challenge=self.challenge, student=self.student).first()
        self.assertIsNotNone(sub)
        self.assertFalse(sub.is_correct)
        self.assertEqual(sub.points_awarded, 0)

        # Ensure no CTFScore created or 0 points
        score = CTFScore.objects.filter(student=self.student).first()
        if score:
            self.assertEqual(score.points, 0)

    def test_duplicate_submission_prevented(self):
        url = reverse('labs:challenge-detail', kwargs={'slug': self.challenge.slug})
        # First correct submission
        self.client.post(url, {'flag': 'FTACK{c0mm4nd_1nj3ct10n_succ3ss}'})
        score_after_first = CTFScore.objects.get(student=self.student).points

        # Second submission of same flag
        self.client.post(url, {'flag': 'FTACK{c0mm4nd_1nj3ct10n_succ3ss}'})
        score_after_second = CTFScore.objects.get(student=self.student).points

        # Score must NOT be awarded twice
        self.assertEqual(score_after_first, score_after_second)


class Phase3APageViewsTestCase(TestCase):
    """
    Validates that all Cyber Range and CTF pages render with HTTP 200.
    """
    def setUp(self):
        self.student = User.objects.create_user(
            email="hacker@futuretech.edu", username="hacker_ace",
            role=RoleChoices.STUDENT
        )
        self.client = Client()
        self.client.force_login(self.student)
        self.cat = LabCategory.objects.create(name="Binary Analysis", slug="binary")
        self.lab = Lab.objects.create(
            name="Radare2 Disassembly", slug="radare2-disassembly",
            category=self.cat, created_by=self.student, is_published=True
        )
        self.c_cat = ChallengeCategory.objects.create(name="OSINT", slug="osint")
        self.challenge = Challenge.objects.create(
            title="Geolocate The Rogue Server", slug="rogue-server-geo",
            category=self.c_cat, flag="FTACK{lat_long_found}", is_active=True
        )

    def test_lab_list_view(self):
        resp = self.client.get(reverse('labs:lab-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/lab_list.html')

    def test_lab_detail_view(self):
        resp = self.client.get(reverse('labs:lab-detail', kwargs={'slug': self.lab.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/lab_detail.html')

    def test_challenge_list_view(self):
        resp = self.client.get(reverse('labs:challenge-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/challenge_list.html')

    def test_challenge_detail_view(self):
        resp = self.client.get(reverse('labs:challenge-detail', kwargs={'slug': self.challenge.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/challenge_detail.html')

    def test_leaderboard_view(self):
        resp = self.client.get(reverse('labs:leaderboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/leaderboard.html')

    def test_ctf_event_list_view(self):
        resp = self.client.get(reverse('labs:event-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'labs/ctf_events.html')
