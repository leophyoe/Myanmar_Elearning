from django.test import TestCase, Client
from django.urls import reverse
from apps.users.models import User
from apps.courses.models import Course, Enrollment, UserProgress
from apps.certificates.models import Certificate, AssociateCredential
from apps.certificates.services import (
    issue_certificate_for_enrollment,
    evaluate_associate_eligibility,
    compute_grade,
)


class CertificateServiceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='studenteval',
            email='eval@example.com',
            password='Password123!',
            first_name='Aung',
            last_name='Kyaw',
        )
        self.course = Course.objects.create(
            title='Python Fundamentals',
            slug='python-fundamentals',
            description='Learn Python 3',
            certificate_eligible=True,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=Enrollment.Status.COMPLETED,
            progress_pct=100,
        )

    def test_issue_certificate_eligible_course(self):
        cert = issue_certificate_for_enrollment(self.enrollment)
        self.assertIsNotNone(cert)
        self.assertEqual(cert.student, self.student)
        self.assertEqual(cert.course, self.course)
        self.assertTrue(cert.certificate_code.startswith('MEL-CERT-2026-'))

        # Idempotent call returns existing
        cert_again = issue_certificate_for_enrollment(self.enrollment)
        self.assertEqual(cert.pk, cert_again.pk)

    def test_ineligible_course_does_not_issue_certificate(self):
        ineligible_course = Course.objects.create(
            title='Open Seminar',
            slug='open-seminar',
            description='Free preview seminar',
            certificate_eligible=False,
        )
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=ineligible_course,
            status=Enrollment.Status.COMPLETED,
            progress_pct=100,
        )
        cert = issue_certificate_for_enrollment(enrollment)
        self.assertIsNone(cert)

    def test_associate_credential_evaluation(self):
        eligible, cred, metrics = evaluate_associate_eligibility(self.student)
        self.assertTrue(eligible)
        self.assertIsNotNone(cred)
        self.assertEqual(cred.student, self.student)
        self.assertTrue(cred.credential_code.startswith('MEL-ASSOC-2026-'))

        # Check lookup view redirects for associate serial
        resp = self.client.get(reverse('certificate-lookup'), {'code': cred.credential_code})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('associate-verify', kwargs={'cred_id': cred.pk}))

        # Check associate verify page renders
        verify_resp = self.client.get(reverse('associate-verify', kwargs={'cred_id': cred.pk}))
        self.assertEqual(verify_resp.status_code, 200)
        self.assertContains(verify_resp, 'Associate of Myanmar E-Learning')
        self.assertContains(verify_resp, cred.credential_code)

    def test_canonical_certificate_verification_without_leaking_private_data(self):
        cert = issue_certificate_for_enrollment(self.enrollment)
        self.assertIsNotNone(cert.completion_date)

        # Public canonical verification URL /verify/<code_or_id>/
        canonical_url = reverse('canonical-verify', kwargs={'code': cert.certificate_code})
        resp = self.client.get(canonical_url)
        self.assertEqual(resp.status_code, 200)

        # Check public credential details are present
        self.assertContains(resp, cert.certificate_code)
        self.assertContains(resp, cert.student_name)
        self.assertContains(resp, cert.program_title)

        # Confirm private student data is NOT leaked
        self.assertNotContains(resp, self.student.email)
        self.assertNotContains(resp, "eval@example.com")

    def test_generic_certificate_attributes_and_program_title(self):
        cert = issue_certificate_for_enrollment(self.enrollment)
        # Universal properties:
        self.assertEqual(cert.certificate_id, cert.certificate_code)
        self.assertEqual(cert.verification_code, cert.certificate_code)
        self.assertEqual(cert.course_name, self.course.title)
        self.assertEqual(cert.program, cert.program_title)
        self.assertEqual(cert.issue_date, cert.issued_at)
        # Not hardcoded to Cyber Security
        self.assertEqual(cert.program_title, 'Python Fundamentals')
        self.assertNotEqual(cert.program_title, 'Diploma in Cyber Security')

    def test_certificate_revocation_and_unrevocation(self):
        cert = issue_certificate_for_enrollment(self.enrollment)
        self.assertFalse(cert.is_revoked)

        # Revoke certificate
        cert.revoke(reason="Academic plagiarism detected on final assessment.")
        self.assertTrue(cert.is_revoked)
        self.assertEqual(cert.revocation_reason, "Academic plagiarism detected on final assessment.")

        # Canonical verify view shows REVOKED status
        canonical_url = reverse('canonical-verify', kwargs={'code': cert.certificate_code})
        resp = self.client.get(canonical_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'REVOKED')

        # Unrevoke certificate
        cert.unrevoke()
        self.assertFalse(cert.is_revoked)
        self.assertEqual(cert.revocation_reason, "")

        resp_valid = self.client.get(canonical_url)
        self.assertEqual(resp_valid.status_code, 200)
        self.assertContains(resp_valid, 'VALID')
        self.assertContains(resp_valid, 'OFFICIALLY VERIFIED CREDENTIAL')


class InstructorAndPartnerCertificateTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Teacher
        self.teacher = User.objects.create_user(
            username='prof_thuta',
            email='teacher@example.com',
            password='Password123!',
            role='teacher',
        )

        # Partner User & Institution
        from apps.partner.models import Institution, PartnerMembership
        self.partner_user = User.objects.create_user(
            username='partner_admin',
            email='partner@example.com',
            password='Password123!',
            role='partner',
        )
        self.institution = Institution.objects.create(
            name='Tech Academy Myanmar',
            slug='tech-academy-myanmar',
            contact_person=self.partner_user,
            is_verified=True,
        )

        # Student
        self.student = User.objects.create_user(
            username='kyaw_student',
            email='kyaw@example.com',
            password='Password123!',
            first_name='Kyaw',
            last_name='Zin',
        )

        # Teacher's course & certificate
        self.teacher_course = Course.objects.create(
            title='Cyber Defense Masterclass',
            slug='cyber-defense-masterclass',
            owner=self.teacher,
            certificate_eligible=True,
        )
        self.teacher_cert = Certificate.objects.create(
            student=self.student,
            course=self.teacher_course,
            certificate_code='THUTA-CERT-2026-TEACH1',
            grade='Distinction',
            is_revoked=False,
        )

        # Partner course & certificate
        self.partner_course = Course.objects.create(
            title='Enterprise Cloud Architecture',
            slug='enterprise-cloud-architecture',
            partner_institution=self.institution,
            certificate_eligible=True,
        )
        self.partner_cert = Certificate.objects.create(
            student=self.student,
            course=self.partner_course,
            certificate_code='THUTA-CERT-2026-PART1',
            grade='Pass',
            is_revoked=False,
        )

    def test_instructor_certificate_list_view_as_teacher(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse('instructor-certificate-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'THUTA-CERT-2026-TEACH1')
        self.assertContains(resp, 'Kyaw Zin')
        self.assertContains(resp, 'Cyber Defense Masterclass')
        # Does not show partner course certificate that is not taught by teacher
        self.assertNotContains(resp, 'THUTA-CERT-2026-PART1')

    def test_instructor_certificate_list_filtering(self):
        self.client.force_login(self.teacher)
        # Search match
        resp = self.client.get(reverse('instructor-certificate-list'), {'q': 'Kyaw'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'THUTA-CERT-2026-TEACH1')

        # Status distinction filter
        resp_dist = self.client.get(reverse('instructor-certificate-list'), {'status': 'distinction'})
        self.assertEqual(resp_dist.status_code, 200)
        self.assertContains(resp_dist, 'THUTA-CERT-2026-TEACH1')

        # Search miss
        resp_miss = self.client.get(reverse('instructor-certificate-list'), {'q': 'NonExistentXYZ'})
        self.assertEqual(resp_miss.status_code, 200)
        self.assertContains(resp_miss, 'No Student Certificates Found')

    def test_instructor_certificate_export_csv(self):
        self.client.force_login(self.teacher)
        resp = self.client.get(reverse('instructor-certificate-export-csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        self.assertIn('Serial Code', content)
        self.assertIn('THUTA-CERT-2026-TEACH1', content)
        self.assertIn('Cyber Defense Masterclass', content)

    def test_partner_certificate_list_view_as_partner(self):
        self.client.force_login(self.partner_user)
        resp = self.client.get(reverse('partner-certificates'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'THUTA-CERT-2026-PART1')
        self.assertContains(resp, 'Enterprise Cloud Architecture')
        self.assertContains(resp, 'Tech Academy Myanmar')
        # Does not show unrelated teacher course
        self.assertNotContains(resp, 'THUTA-CERT-2026-TEACH1')

    def test_partner_certificate_export_csv(self):
        self.client.force_login(self.partner_user)
        resp = self.client.get(reverse('partner-certificate-export-csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        content = resp.content.decode('utf-8')
        self.assertIn('Serial Code', content)
        self.assertIn('THUTA-CERT-2026-PART1', content)
        self.assertIn('Tech Academy Myanmar', content)


