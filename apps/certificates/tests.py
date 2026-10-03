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

