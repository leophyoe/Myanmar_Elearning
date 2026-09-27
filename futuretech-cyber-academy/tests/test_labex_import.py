from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from apps.accounts.models import User, RoleChoices
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabObjective,
    LabHint, LabFlag, FlagType, LabInstance, LabInstanceStatus,
    LabSubmission
)


class LabExCybersecurityLabsImportTestCase(TestCase):
    """
    Automated test suite validating the LabEx Cybersecurity Labs for Beginners
    import command, metadata attribution, idempotency, student progress preservation,
    and UI catalog filtering.
    """

    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            email="instructor.lead@futuretech.edu",
            username="lead_instructor",
            role=RoleChoices.INSTRUCTOR,
            is_staff=True
        )
        self.student = User.objects.create_user(
            email="student.test@futuretech.edu",
            username="cyber_student",
            role=RoleChoices.STUDENT
        )

    def test_01_import_command_creates_22_labs(self):
        """Verify management command creates exactly 22 LabEx labs with proper metadata."""
        call_command('import_labex_cybersecurity_labs')

        labex_labs = Lab.objects.filter(source_name='LabEx')
        self.assertEqual(labex_labs.count(), 22)

        # Verify all are published
        self.assertEqual(labex_labs.filter(is_published=True).count(), 22)

        # Verify upstream licensing and attribution
        for lab in labex_labs:
            self.assertEqual(lab.source_name, "LabEx")
            self.assertEqual(lab.source_url, "https://github.com/labex-labs/cybersecurity-labs-for-beginners")
            self.assertEqual(lab.source_type, "OPEN_SOURCE")
            self.assertTrue(lab.attribution_required)
            self.assertEqual(lab.license_name, "Apache-2.0")
            self.assertGreaterEqual(lab.display_order, 101)
            self.assertLessEqual(lab.display_order, 122)

    def test_02_difficulty_and_point_allocations(self):
        """
        Verify point system:
        - 50 points for standard beginner labs (20 labs)
        - 75 points for challenge / intermediate labs (Lab 8 & Lab 10)
        """
        call_command('import_labex_cybersecurity_labs')

        # Challenge labs
        challenge_lab_8 = Lab.objects.get(slug="receive-messages-using-netcat")
        self.assertEqual(challenge_lab_8.difficulty, LabDifficulty.MEDIUM)
        self.assertEqual(challenge_lab_8.points, 75)
        self.assertEqual(challenge_lab_8.display_order, 108)

        challenge_lab_10 = Lab.objects.get(slug="capture-google-traffic-with-wireshark")
        self.assertEqual(challenge_lab_10.difficulty, LabDifficulty.MEDIUM)
        self.assertEqual(challenge_lab_10.points, 75)
        self.assertEqual(challenge_lab_10.display_order, 110)

        # Standard beginner labs (e.g. Lab 1, Lab 3, Lab 5)
        lab_1 = Lab.objects.get(slug="using-hydra-to-crack-passwords")
        self.assertEqual(lab_1.difficulty, LabDifficulty.BEGINNER)
        self.assertEqual(lab_1.points, 50)
        self.assertEqual(lab_1.display_order, 101)

        lab_3 = Lab.objects.get(slug="network-scanning-with-nmap")
        self.assertEqual(lab_3.difficulty, LabDifficulty.BEGINNER)
        self.assertEqual(lab_3.points, 50)

        # Verify total points across all 22 labs: (20 * 50) + (2 * 75) = 1150
        from django.db.models import Sum
        total_pts = Lab.objects.filter(source_name='LabEx').aggregate(Sum('points'))['points__sum']
        self.assertEqual(total_pts, (20 * 50) + (2 * 75))

    def test_03_objectives_hints_and_flags_created(self):
        """Verify all 22 labs have structured objectives, hints, and static flags."""
        call_command('import_labex_cybersecurity_labs')

        for lab in Lab.objects.filter(source_name='LabEx'):
            self.assertGreaterEqual(lab.objectives.count(), 1, f"Missing objectives for {lab.slug}")
            self.assertGreaterEqual(lab.hints.count(), 1, f"Missing hints for {lab.slug}")
            self.assertGreaterEqual(lab.flags.count(), 1, f"Missing flags for {lab.slug}")

            flag = lab.flags.first()
            self.assertEqual(flag.flag_type, FlagType.STATIC_FLAG)
            self.assertTrue(flag.static_flag.startswith("FTACK{"))

    def test_04_idempotency_no_duplicates(self):
        """Verify calling import multiple times does not duplicate labs, objectives, or flags."""
        call_command('import_labex_cybersecurity_labs')
        initial_lab_count = Lab.objects.filter(source_name='LabEx').count()
        initial_obj_count = LabObjective.objects.filter(lab__source_name='LabEx').count()
        initial_flag_count = LabFlag.objects.filter(lab__source_name='LabEx').count()

        # Run command a second and third time
        call_command('import_labex_cybersecurity_labs')
        call_command('import_labex_cybersecurity_labs')

        self.assertEqual(Lab.objects.filter(source_name='LabEx').count(), initial_lab_count)
        self.assertEqual(LabObjective.objects.filter(lab__source_name='LabEx').count(), initial_obj_count)
        self.assertEqual(LabFlag.objects.filter(lab__source_name='LabEx').count(), initial_flag_count)

    def test_05_student_progress_preservation_on_reimport(self):
        """
        Verify that student submissions and active instances are preserved
        even when the import command is executed again.
        """
        call_command('import_labex_cybersecurity_labs')

        lab = Lab.objects.get(slug="using-hydra-to-crack-passwords")
        flag = lab.flags.first()

        # Create student submission
        submission = LabSubmission.objects.create(
            lab=lab,
            student=self.student,
            flag_submitted=flag.static_flag,
            is_correct=True,
            points_awarded=lab.points
        )

        # Create student instance
        instance = LabInstance.objects.create(
            student=self.student,
            lab=lab,
            status=LabInstanceStatus.RUNNING,
            container_id="sim-labex-01-container",
            assigned_ip="10.10.101.5"
        )

        # Re-run the import command
        call_command('import_labex_cybersecurity_labs')

        # Check that submission and instance still exist and point to the same lab
        reloaded_sub = LabSubmission.objects.get(id=submission.id)
        self.assertEqual(reloaded_sub.lab.slug, "using-hydra-to-crack-passwords")
        self.assertEqual(reloaded_sub.points_awarded, 50)
        self.assertTrue(reloaded_sub.is_correct)

        reloaded_inst = LabInstance.objects.get(id=instance.id)
        self.assertEqual(reloaded_inst.lab.slug, "using-hydra-to-crack-passwords")
        self.assertEqual(reloaded_inst.status, LabInstanceStatus.RUNNING)

    def test_06_lab_list_view_and_collection_filtering(self):
        """Test web catalog view and collection filtering for Beginner labs."""
        call_command('import_labex_cybersecurity_labs')

        # GET all labs
        url = reverse('labs:lab-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Beginner Cybersecurity")
        self.assertContains(response, "Using Hydra to Crack Passwords")
        self.assertContains(response, "Source: LabEx")
        self.assertContains(response, "Apache-2.0")
        self.assertContains(response, "Start Lab")

        # GET filtered by collection=beginner
        response_beginner = self.client.get(url + '?collection=beginner')
        self.assertEqual(response_beginner.status_code, 200)
        for lab in response_beginner.context['labs']:
            self.assertEqual(lab.source_name, 'LabEx')

        # GET filtered by source=LabEx
        response_source = self.client.get(url + '?source=LabEx')
        self.assertEqual(response_source.status_code, 200)
        self.assertEqual(len(response_source.context['labs']), 12)  # Paginated at 12

    def test_07_lab_detail_view_attribution(self):
        """Test lab detail briefing displays clear upstream attribution and license."""
        call_command('import_labex_cybersecurity_labs')

        url = reverse('labs:lab-detail', kwargs={'slug': 'network-scanning-with-nmap'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Network Scanning with Nmap")
        self.assertContains(response, "Upstream Lab Source:")
        self.assertContains(response, "LabEx")
        self.assertContains(response, "https://github.com/labex-labs/cybersecurity-labs-for-beginners")
        self.assertContains(response, "Apache-2.0")
        self.assertContains(response, "OPEN_SOURCE")

    def test_08_category_mappings(self):
        """Verify that tools are mapped to their proper domain categories."""
        call_command('import_labex_cybersecurity_labs')

        mappings = [
            ("using-hydra-to-crack-passwords", "ethical-hacking-password-security"),
            ("network-scanning-with-nmap", "network-security-reconnaissance"),
            ("introduction-to-encryption-with-openssl", "cryptography"),
            ("using-netcat-for-simple-network-communication", "networking"),
            ("network-analysis-with-wireshark", "network-analysis"),
            ("crack-zip-passwords-in-john-the-ripper", "ethical-hacking-password-security"),
            ("monitor-files-in-tripwire", "host-security-file-integrity"),
            ("scan-ports-with-masscan", "network-scanning"),
            ("hide-data-in-steghide", "digital-forensics-steganography"),
            ("scan-web-servers-in-nikto", "web-security-vulnerability-assessment"),
            ("map-threats-in-a-simple-login-service", "authentication-defensive-security"),
            ("add-a-second-factor-to-a-login-script", "authentication-defensive-security"),
            ("layer-defenses-around-a-local-secret-service", "defensive-security"),
        ]
        for slug, cat_slug in mappings:
            lab = Lab.objects.get(slug=slug)
            self.assertEqual(lab.category.slug, cat_slug, f"Lab {slug} has wrong category {lab.category.slug}")

    def test_09_unpublished_labs_hidden_from_students(self):
        """Verify that unpublished labs are excluded from student catalog and briefing."""
        call_command('import_labex_cybersecurity_labs')

        lab = Lab.objects.get(slug="using-hydra-to-crack-passwords")
        lab.is_published = False
        lab.save()

        # Regular student cannot see it in catalog
        self.client.force_login(self.student)
        url = reverse('labs:lab-list')
        response = self.client.get(url)
        self.assertNotContains(response, "Using Hydra to Crack Passwords")

        # Regular student gets 404 on detail
        detail_url = reverse('labs:lab-detail', kwargs={'slug': 'using-hydra-to-crack-passwords'})
        resp_detail = self.client.get(detail_url)
        self.assertEqual(resp_detail.status_code, 404)

        # Instructor CAN see it
        self.client.force_login(self.instructor)
        resp_inst = self.client.get(detail_url)
        self.assertEqual(resp_inst.status_code, 200)
