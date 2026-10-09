from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Payment, PaymentMethod, SubscriptionPlan
from apps.courses.models import Course, Subject

User = get_user_model()


class DynamicPaymentMethodsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username='admin_pay',
            email='admin_pay@thuta.edu',
            password='Password123!',
            role='admin',
        )
        cls.student_user = User.objects.create_user(
            username='student_pay',
            email='student_pay@thuta.edu',
            password='Password123!',
            role='student',
        )

        cls.subject = Subject.objects.create(
            title='Systems Engineering',
            slug='systems-engineering',
        )
        cls.course = Course.objects.create(
            title='DevOps with Docker',
            slug='devops-with-docker',
            owner=cls.admin_user,
            subject=cls.subject,
            price=Decimal('45000.00'),
            currency='MMK',
            status=Course.Status.PUBLISHED,
            is_published=True,
        )

        SubscriptionPlan.ensure_default_plans()
        PaymentMethod.ensure_default_methods()

    def test_default_methods_seeded(self):
        """Default payment channels exist including MMQR, KPay, Wave, Bank."""
        self.assertTrue(PaymentMethod.objects.filter(code='mmqr').exists())
        self.assertTrue(PaymentMethod.objects.filter(code='kbz_pay').exists())
        self.assertTrue(PaymentMethod.objects.filter(code='wave_pay').exists())
        self.assertTrue(PaymentMethod.objects.filter(code='bank_transfer').exists())

    def test_admin_can_add_new_payment_method(self):
        """Admin can create a new dynamic payment method via in-app view."""
        self.client.force_login(self.admin_user)
        res = self.client.post(reverse('billing:method-create'), {
            'name': 'AYA Pay Wallet',
            'code': 'aya_pay',
            'method_type': PaymentMethod.MethodType.WALLET,
            'account_name': 'THUTA Academy',
            'account_number': '09-123456789',
            'instructions': 'Send with AYA Pay and upload screenshot.',
            'display_order': 5,
            'is_active': True,
        })
        self.assertEqual(res.status_code, 302)

        method = PaymentMethod.objects.get(code='aya_pay')
        self.assertEqual(method.name, 'AYA Pay Wallet')
        self.assertTrue(method.is_active)

    def test_admin_can_toggle_payment_method(self):
        """Admin can toggle a payment channel active or disabled."""
        self.client.force_login(self.admin_user)
        mmqr = PaymentMethod.objects.get(code='mmqr')
        initial_status = mmqr.is_active

        res = self.client.post(reverse('billing:method-toggle', kwargs={'pk': mmqr.pk}))
        self.assertEqual(res.status_code, 302)

        mmqr.refresh_from_db()
        self.assertNotEqual(mmqr.is_active, initial_status)

    def test_safe_delete_deactivates_method_with_transactions(self):
        """Payment method with recorded transactions is deactivated instead of hard-deleted."""
        self.client.force_login(self.admin_user)
        kpay = PaymentMethod.objects.get(code='kbz_pay')

        # Create a payment using kpay
        Payment.objects.create(
            student=self.student_user,
            course=self.course,
            payment_type=Payment.PaymentType.COURSE_PURCHASE,
            payment_method=kpay,
            method='kbz_pay',
            amount=Decimal('45000.00'),
            currency='MMK',
            status=Payment.Status.PENDING,
        )

        res = self.client.post(reverse('billing:method-delete', kwargs={'pk': kpay.pk}))
        self.assertEqual(res.status_code, 302)

        # Still exists in DB, but deactivated
        kpay.refresh_from_db()
        self.assertFalse(kpay.is_active)

    def test_checkout_links_payment_method_foreign_key(self):
        """Course purchase checkout links the PaymentMethod entity to Payment."""
        self.client.force_login(self.student_user)
        url = reverse('checkout', kwargs={'slug': self.course.slug})

        res = self.client.post(url, {
            'method': 'wave_pay',
            'reference': 'WAVE-11223344',
            'note': 'Paid with Wave Money',
        })
        self.assertEqual(res.status_code, 302)

        payment = Payment.objects.filter(student=self.student_user, course=self.course).first()
        self.assertIsNotNone(payment)
        self.assertIsNotNone(payment.payment_method)
        self.assertEqual(payment.payment_method.code, 'wave_pay')
        self.assertEqual(payment.method_display, 'Wave Money (WavePay)')
