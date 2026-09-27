from django.test import TestCase, Client
from django.core.management import call_command
from django.urls import reverse
from apps.accounts.models import User, RoleChoices
from apps.courses.models import Course, CourseModule
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType,
    ChallengeCategory, Challenge, ChallengeSubmission,
    LabSubmission, CTFScore
)


class LearnToCloudLinuxCtfsImportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@futuretech.edu",
            username="testadmin",
            password="TestPassword123!"
        )
        self.student = User.objects.create_user(
            email="student@futuretech.edu",
            username="linuxstudent",
            password="StudentPass123!",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="DIPLOMA IN CYBER SECURITY",
            slug="diploma-in-cyber-security",
            created_by=self.admin_user
        )
        self.mod2 = CourseModule.objects.create(
            course=self.course,
            title="Computer Systems & OS Security",
            slug="computer-systems-os-security",
            order=2
        )
        self.mod4 = CourseModule.objects.create(
            course=self.course,
            title="Linux for Cyber Security",
            slug="linux-for-cyber-security",
            order=4
        )

    def test_import_command_and_metadata(self):
        """Test import_linux_ctfs creates 19 labs and 19 challenges with proper attribution."""
        call_command("import_linux_ctfs")

        labs = Lab.objects.filter(source_name="LearnToCloud")
        self.assertEqual(labs.count(), 19)

        challenges = Challenge.objects.filter(category__slug__startswith="linux-")
        self.assertEqual(challenges.count(), 19)

        # Check sample lab metadata
        sample_lab = Lab.objects.get(slug="ltc-00-example-challenge")
        self.assertEqual(sample_lab.source_name, "LearnToCloud")
        self.assertEqual(sample_lab.source_url, "https://github.com/learntocloud/linux-ctfs")
        self.assertEqual(sample_lab.license_name, "MIT")
        self.assertTrue(sample_lab.attribution_required)
        self.assertEqual(sample_lab.difficulty, LabDifficulty.BEGINNER)
        self.assertEqual(sample_lab.points, 50)
        self.assertEqual(sample_lab.type, LabType.GUIDED)
        self.assertEqual(sample_lab.objectives.count(), 2)
        self.assertEqual(sample_lab.flags.count(), 1)
        self.assertEqual(sample_lab.hints.count(), 1)

        # Check module linkage
        self.assertEqual(sample_lab.module, self.mod2)
        lab_ch2 = Lab.objects.get(slug="ltc-02-the-secret-file")
        self.assertEqual(lab_ch2.module, self.mod4)

    def test_ten_linux_categories_created(self):
        """Test all 10 Linux categories exist in LabCategory and ChallengeCategory."""
        call_command("import_linux_ctfs")

        expected_slugs = [
            "linux-fundamentals", "linux-commands", "linux-filesystem",
            "linux-permissions", "linux-users-groups", "linux-processes",
            "linux-networking", "linux-services", "linux-security",
            "linux-troubleshooting"
        ]

        for slug in expected_slugs:
            self.assertTrue(LabCategory.objects.filter(slug=slug).exists(), f"LabCategory missing: {slug}")
            self.assertTrue(ChallengeCategory.objects.filter(slug=slug).exists(), f"ChallengeCategory missing: {slug}")

    def test_idempotency_and_preservation(self):
        """Test running import_linux_ctfs multiple times does not create duplicates or wipe submissions."""
        call_command("import_linux_ctfs")
        initial_labs_count = Lab.objects.filter(source_name="LearnToCloud").count()
        initial_ch_count = Challenge.objects.filter(category__slug__startswith="linux-").count()

        # Simulate a student submission
        challenge = Challenge.objects.get(slug="linux-ltc-00-example-challenge")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            student=self.student,
            flag_submitted="CTF{example}",
            is_correct=True,
            points_awarded=50
        )
        challenge.solves_count = 1
        challenge.save()

        # Run command second time
        call_command("import_linux_ctfs")

        self.assertEqual(Lab.objects.filter(source_name="LearnToCloud").count(), initial_labs_count)
        self.assertEqual(Challenge.objects.filter(category__slug__startswith="linux-").count(), initial_ch_count)

        # Ensure submission and solves_count preserved
        sub = ChallengeSubmission.objects.filter(challenge=challenge, student=self.student).first()
        self.assertIsNotNone(sub)
        self.assertTrue(sub.is_correct)
        challenge.refresh_from_db()
        self.assertEqual(challenge.solves_count, 1)

    def test_linux_labs_list_view(self):
        """Test /labs/linux/ endpoint renders correctly."""
        call_command("import_linux_ctfs")
        response = self.client.get(reverse("labs:linux-lab-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/linux_labs.html")
        self.assertContains(response, "Linux Guided Cyber Security Labs")
        self.assertContains(response, "LearnToCloud")
        self.assertContains(response, "Hidden File Discovery")

    def test_linux_ctf_list_view(self):
        """Test /ctf/linux/ endpoint renders correctly."""
        call_command("import_linux_ctfs")
        response = self.client.get(reverse("linux-ctf-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/linux_ctf.html")
        self.assertContains(response, "Linux CTF Arena")
        self.assertContains(response, "Hidden File Discovery")

    def test_linux_challenge_detail_view_and_flag_submission(self):
        """Test /ctf/linux/<slug>/ view and secure server-side flag validation."""
        call_command("import_linux_ctfs")
        challenge = Challenge.objects.get(slug="linux-ltc-01-the-hidden-file")
        detail_url = reverse("linux-challenge-detail", kwargs={"slug": challenge.slug})

        # 1. Unauthenticated GET works
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "labs/linux_challenge_detail.html")
        # Ensure flag is NOT leaked in context or html
        self.assertNotContains(resp, challenge.flag)

        # 2. Login student and submit incorrect flag
        self.client.force_login(self.student)
        resp_bad = self.client.post(detail_url, {"flag": "CTF{wrong_flag}"}, follow=True)
        self.assertContains(resp_bad, "Incorrect flag")
        self.assertFalse(ChallengeSubmission.objects.filter(challenge=challenge, student=self.student, is_correct=True).exists())

        # 3. Submit correct flag
        resp_good = self.client.post(detail_url, {"flag": "CTF{hidden_files_found}"}, follow=True)
        self.assertContains(resp_good, "Flag verified")
        self.assertTrue(ChallengeSubmission.objects.filter(challenge=challenge, student=self.student, is_correct=True).exists())

        # Check score updated
        score = CTFScore.objects.get(student=self.student)
        self.assertEqual(score.points, 50)
        self.assertEqual(score.challenge_points, 50)
        self.assertEqual(score.solves_count, 1)

        # 4. Duplicate submission is prevented
        resp_dup = self.client.post(detail_url, {"flag": "CTF{hidden_files_found}"}, follow=True)
        self.assertContains(resp_dup, "already solved")
        score.refresh_from_db()
        self.assertEqual(score.points, 50)  # no extra points
