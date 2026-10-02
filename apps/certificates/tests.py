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

