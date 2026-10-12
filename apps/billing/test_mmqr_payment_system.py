import io
from decimal import Decimal
from PIL import Image

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Payment, PaymentMethod, SubscriptionPlan, Invoice
from apps.courses.models import Course, Enrollment, Subject

User = get_user_model()


def create_test_image(filename="test_qr.png"):
    """Generates an in-memory test image file."""
    file = io.BytesIO()
    image = Image.new('RGB', (120, 120), color=(56, 189, 248))
    image.save(file, 'PNG')
    file.seek(0)
    return SimpleUploadedFile(filename, file.read(), content_type='image/png')


class MMQRPaymentSystemTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username='admin_mmqr',
            email='admin_mmqr@thuta.edu',
            password='Password123!',
            role='admin',
        )
        cls.student_user = User.objects.create_user(
            username='student_mmqr',
            email='student_mmqr@thuta.edu',
            password='Password123!',
            role='student',
        )
        cls.other_student = User.objects.create_user(
            username='student_two',
            email='student_two@thuta.edu',
            password='Password123!',
            role='student',
        )

        cls.subject = Subject.objects.create(
            title='Cyber Defense & Operations',
            slug='cyber-defense',
        )
        cls.course = Course.objects.create(
            title='Enterprise MMQR Security & Auditing',
            slug='enterprise-mmqr-security',
            owner=cls.admin_user,
            subject=cls.subject,
            price=Decimal('50000.00'),
            currency='MMK',
            status=Course.Status.PUBLISHED,
            is_published=True,
        )

        SubscriptionPlan.ensure_default_plans()

    def setUp(self):
        # Reset or ensure MMQR canonical method exists
        self.mmqr = PaymentMethod.get_mmqr()
        # Default fresh state: disabled and no QR asset
        self.mmqr.is_active = False
        if self.mmqr.qr_image:
            self.mmqr.qr_image.delete(save=False)
            self.mmqr.qr_image = None
        self.mmqr.save()

    def test_initial_state_disabled_and_unconfigured(self):
        """MMQR is disabled by default and identifies missing requirements."""
        mmqr = PaymentMethod.get_mmqr()
        self.assertFalse(mmqr.is_active)
        self.assertFalse(bool(mmqr.qr_image))
        self.assertFalse(mmqr.is_ready_for_checkout())

        missing = mmqr.get_missing_requirements()
        self.assertIn("Availability status is currently set to Disabled.", missing)
        self.assertIn("Official MMQR code image has not been uploaded.", missing)

    def test_customer_checkout_shows_coming_soon_when_unconfigured(self):
        """When MMQR is unconfigured, checkout displays Coming Soon and no fake QR."""
        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        content = res.content.decode('utf-8')
        self.assertIn("MMQR payment is coming soon. Please try again later.", content)
        self.assertIn("MMQR ဖြင့် ငွေပေးချေမှုစနစ် မကြာမီ အသုံးပြုနိုင်ပါမည်", content)
        # Verify no fake QR image is displayed
        self.assertNotIn('<img src="/media/payments/qr/', content)

    def test_checkout_submission_blocked_when_mmqr_not_ready(self):
        """Submitting payment when MMQR is not ready returns 400 and creates no payment."""
        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        res = self.client.post(url, {
            'method': 'mmqr',
            'reference': 'TRANS-FAKE-12345',
        })
        self.assertEqual(res.status_code, 400)
        content = res.content.decode('utf-8')
        self.assertIn("MMQR payment is coming soon. Please try again later.", content)

        # Confirm no payment record created
        self.assertFalse(
            Payment.objects.filter(student=self.student_user, course=self.course).exists()
        )

    def test_admin_settings_permission_check(self):
        """Non-admins cannot access MMQR Payment Settings; admin can."""
        settings_url = reverse('billing:payment-settings')

        # Anonymous -> redirect to login
        res = self.client.get(settings_url)
        self.assertEqual(res.status_code, 302)

        # Student -> Forbidden 403
        self.client.force_login(self.student_user)
        res = self.client.get(settings_url)
        self.assertEqual(res.status_code, 403)

        # Platform Admin -> 200 OK
        self.client.force_login(self.admin_user)
        res = self.client.get(settings_url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("National MMQR Gateway Configuration", res.content.decode('utf-8'))

    def test_admin_can_configure_and_upload_real_mmqr_image(self):
        """Admin can configure merchant details, upload real QR image, and activate MMQR."""
        self.client.force_login(self.admin_user)
        settings_url = reverse('billing:payment-settings')

        test_qr = create_test_image('official_thuta_mmqr.png')

        res = self.client.post(settings_url, {
            'name': 'MMQR',
            'account_name': 'THUTA E-Learning Platform Co., Ltd.',
            'account_number': 'MMQR-MERCH-889900',
            'is_active': 'on',
            'qr_image': test_qr,
            'instructions': 'Scan with KBZPay, WavePay, AYA Pay, or any bank app.',
            'instructions_my': 'မည်သည့် မိုဘိုင်းဘဏ်ဖြင့်မဆို MMQR ကို စကင်ဖတ်ပါ။',
        })
        self.assertEqual(res.status_code, 302)

        self.mmqr.refresh_from_db()
        self.assertTrue(self.mmqr.is_active)
        self.assertTrue(bool(self.mmqr.qr_image))
        self.assertEqual(self.mmqr.account_name, 'THUTA E-Learning Platform Co., Ltd.')
        self.assertEqual(self.mmqr.account_number, 'MMQR-MERCH-889900')
        self.assertTrue(self.mmqr.is_ready_for_checkout())
        self.assertEqual(self.mmqr.get_missing_requirements(), [])

    def test_customer_checkout_displays_real_qr_and_exact_amount(self):
        """When MMQR is configured, checkout displays real QR, exact price, and instructions."""
        # Setup active MMQR
        test_qr = create_test_image('active_mmqr.png')
        self.mmqr.account_name = 'THUTA E-Learning Co.'
        self.mmqr.account_number = 'MMQR-TERM-001'
        self.mmqr.qr_image = test_qr
        self.mmqr.is_active = True
        self.mmqr.save()

        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        content = res.content.decode('utf-8')
        self.assertIn("Official MMQR Payment", content)
        self.assertIn(self.mmqr.qr_image.url, content)
        self.assertIn("50000", content)
        self.assertIn("MMK", content)
        self.assertIn("Exact Amount to Pay:", content)
        self.assertIn("THUTA E-Learning Co.", content)
        self.assertIn("Phase A: Manual Review", content)

    def test_customer_can_submit_payment_proof_and_authoritative_price(self):
        """Student submits proof; server computes exact price and creates pending payment."""
        test_qr = create_test_image('active_mmqr.png')
        self.mmqr.qr_image = test_qr
        self.mmqr.is_active = True
        self.mmqr.save()

        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        receipt_file = create_test_image('student_transfer_slip.png')

        res = self.client.post(url, {
            'method': 'mmqr',
            'reference': 'MMQR-TXN-99887766',
            'receipt': receipt_file,
            'note': 'Paid exact amount via KBZPay MMQR scanner',
        })
        self.assertEqual(res.status_code, 302)

        payment = Payment.objects.filter(
            student=self.student_user, course=self.course
        ).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('50000.00'))  # Authoritative price!
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.reference, 'MMQR-TXN-99887766')
        self.assertEqual(payment.payment_method, self.mmqr)
        self.assertTrue(bool(payment.receipt))

    def test_prevents_duplicate_pending_payment(self):
        """Student cannot submit a second checkout payment while review is pending."""
        test_qr = create_test_image('active_mmqr.png')
        self.mmqr.qr_image = test_qr
        self.mmqr.is_active = True
        self.mmqr.save()

        # Existing pending payment
        Payment.objects.create(
            student=self.student_user,
            course=self.course,
            payment_type=Payment.PaymentType.COURSE_PURCHASE,
            payment_method=self.mmqr,
            method='mmqr',
            amount=Decimal('50000.00'),
            currency='MMK',
            status=Payment.Status.PENDING,
        )

        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        # GET redirects with notice
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("Awaiting Review", res_get.content.decode('utf-8'))

        # POST redirects back to course detail
        res_post = self.client.post(url, {
            'method': 'mmqr',
            'reference': 'SECOND-TRY',
        })
        self.assertEqual(res_post.status_code, 302)
        self.assertEqual(
            Payment.objects.filter(student=self.student_user, course=self.course).count(),
            1
        )

    def test_prevents_duplicate_enrollment_purchase(self):
        """Student already enrolled in course cannot purchase again."""
        Enrollment.objects.create(
            student=self.student_user,
            course=self.course,
            is_active=True,
        )

        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        res_post = self.client.post(url, {
            'method': 'mmqr',
            'reference': 'TRYING-WHILE-ENROLLED',
        })
        self.assertEqual(res_post.status_code, 302)
        self.assertFalse(
            Payment.objects.filter(student=self.student_user, course=self.course).exists()
        )

    def test_admin_can_remove_qr_image(self):
        """Admin can remove uploaded QR image, putting checkout back in Coming Soon mode."""
        test_qr = create_test_image('qr_to_remove.png')
        self.mmqr.qr_image = test_qr
        self.mmqr.is_active = True
        self.mmqr.save()
        self.assertTrue(self.mmqr.is_ready_for_checkout())

        self.client.force_login(self.admin_user)
        settings_url = reverse('billing:payment-settings')

        res = self.client.post(settings_url, {
            'name': 'MMQR',
            'account_name': 'THUTA E-Learning Platform',
            'account_number': '',
            'is_active': 'on',
            'remove_qr_image': 'on',
            'instructions': 'Instructions',
            'instructions_my': 'လမ်းညွှန်',
        })
        self.assertEqual(res.status_code, 302)

        self.mmqr.refresh_from_db()
        self.assertFalse(bool(self.mmqr.qr_image))
        self.assertFalse(self.mmqr.is_ready_for_checkout())

        # Customer now sees coming soon
        self.client.force_login(self.student_user)
        checkout_res = self.client.get(reverse('checkout', kwargs={'slug': self.course.slug}))
        self.assertIn("MMQR payment is coming soon. Please try again later.", checkout_res.content.decode('utf-8'))

    def test_admin_approval_phase_a_activates_enrollment_and_invoice(self):
        """Phase A manual approval workflow activates enrollment and issues invoice."""
        test_qr = create_test_image('active_mmqr.png')
        self.mmqr.qr_image = test_qr
        self.mmqr.is_active = True
        self.mmqr.save()

        # Student submits payment
        payment = Payment.objects.create(
            student=self.student_user,
            course=self.course,
            payment_type=Payment.PaymentType.COURSE_PURCHASE,
            payment_method=self.mmqr,
            method='mmqr',
            amount=Decimal('50000.00'),
            currency='MMK',
            status=Payment.Status.PENDING,
            reference='MMQR-PROOF-5544',
        )

        # Not yet enrolled
        self.assertFalse(
            Enrollment.objects.filter(student=self.student_user, course=self.course, is_active=True).exists()
        )

        # Admin reviews and approves
        self.client.force_login(self.admin_user)
        review_url = reverse('payment-review', kwargs={'payment_id': payment.id})
        res = self.client.post(review_url, {
            'action': 'approve',
            'admin_note': 'MMQR slip verified in KBZPay merchant portal.',
        })
        self.assertEqual(res.status_code, 302)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.reviewed_by, self.admin_user)

        # Enrollment is activated
        enrollment = Enrollment.objects.filter(student=self.student_user, course=self.course, is_active=True).first()
        self.assertIsNotNone(enrollment)

        # Invoice is generated
        invoice = Invoice.objects.filter(payment=payment).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.amount, Decimal('50000.00'))
