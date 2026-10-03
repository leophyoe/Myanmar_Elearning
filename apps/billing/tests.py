from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from .models import SubscriptionPlan, UserSubscription, Payment, active_subscription_for

User = get_user_model()


class SubscriptionPlanTests(TestCase):
    def setUp(self):
        self.plans = SubscriptionPlan.ensure_default_plans()

    def test_default_plans_seeded_correctly(self):
        self.assertEqual(len(self.plans), 3)
        starter = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STARTER)
        standard = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        premium = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.PREMIUM)

        self.assertEqual(starter.monthly_price, Decimal('0'))
        self.assertEqual(standard.monthly_price, Decimal('5000'))
        self.assertEqual(standard.yearly_price, Decimal('50000'))
        self.assertEqual(premium.monthly_price, Decimal('15000'))
        self.assertEqual(premium.yearly_price, Decimal('150000'))

        self.assertTrue(standard.has_all_standard_courses)
        self.assertFalse(standard.has_cyber_range)
        self.assertTrue(premium.has_cyber_range)
        self.assertEqual(premium.live_class_discount_percent, 20)

    def test_starter_instant_activation(self):
        user = User.objects.create_user(
            username='starter_student', email='starter@example.com', password='password123'
        )
        starter_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STARTER)

        client = Client()
        client.login(username='starter_student', password='password123')
        response = client.get(reverse('subscribe', kwargs={'plan_type': 'starter'}))
        self.assertEqual(response.status_code, 302)

        sub = active_subscription_for(user)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, starter_plan)
        self.assertTrue(sub.is_current)

    def test_subscription_submission_and_admin_approval(self):
        admin_user = User.objects.create_superuser(
            username='admin_sub', email='admin_sub@example.com', password='password123'
        )
        student = User.objects.create_user(
            username='paying_student', email='paying@example.com', password='password123'
        )
        standard_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)

        client = Client()
        client.login(username='paying_student', password='password123')

        # Submit standard monthly subscription payment
        response = client.post(reverse('subscribe', kwargs={'plan_type': 'standard'}), {
            'billing_cycle': 'monthly',
            'method': Payment.Method.KBZ_PAY,
            'reference': 'KPAY-TRX-998877',
            'note': 'Test subscription payment',
        })
        self.assertEqual(response.status_code, 302)

        payment = Payment.objects.filter(student=student, plan=standard_plan).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('5000'))
        self.assertEqual(payment.status, Payment.Status.PENDING)

        # Admin approves the payment
        admin_client = Client()
        admin_client.login(username='admin_sub', password='password123')
        review_url = reverse('payment-review', kwargs={'payment_id': payment.id})
        resp = admin_client.post(review_url, {'action': 'approve'})
        self.assertEqual(resp.status_code, 302)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertIsNotNone(payment.period_end)

        sub = active_subscription_for(student)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, standard_plan)
        self.assertTrue(sub.is_current)


class SubscriptionAPITests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.user = User.objects.create_user(
            username='api_student', email='api@example.com', password='password123'
        )
        self.client = Client()
        self.client.login(username='api_student', password='password123')

    def test_api_plans_list(self):
        response = self.client.get(reverse('api-plans'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 3)

    def test_api_starter_subscribe(self):
        response = self.client.post(reverse('api-subscribe'), {
            'plan_type': 'starter',
            'billing_cycle': 'monthly',
            'method': 'kbz_pay'
        }, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        sub_resp = self.client.get(reverse('api-my-subscription'))
        self.assertEqual(sub_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(sub_resp.json()['plan']['plan_type'], 'starter')


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.user = User.objects.create_user(
            username='lifecycle_student', email='lifecycle@mel.edu.mm', password='password123'
        )
        self.std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)

    def test_subscription_status_affects_is_current(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            status=UserSubscription.Status.ACTIVE,
            is_active=True,
            auto_renew=True,
        )
        self.assertTrue(sub.is_current)
        self.assertTrue(sub.auto_renew)

        # Cancelled subscription is not current
        sub.status = UserSubscription.Status.CANCELLED
        sub.save()
        self.assertFalse(sub.is_current)

        # Suspended subscription is not current
        sub.status = UserSubscription.Status.SUSPENDED
        sub.save()
        self.assertFalse(sub.is_current)

        # Expired subscription is not current
        sub.status = UserSubscription.Status.EXPIRED
        sub.save()
        self.assertFalse(sub.is_current)

        # Active status is current
        sub.status = UserSubscription.Status.ACTIVE
        sub.save()
        self.assertTrue(sub.is_current)


from apps.courses.models import Course, Enrollment, Subject
from apps.partner.models import Institution, PartnerMembership
from apps.billing.models import PartnerRevenueRecord, Invoice
from apps.billing.providers.registry import get_payment_provider, register_payment_provider, list_available_providers
from apps.billing.providers.base import BasePaymentProvider, PaymentRequest, PaymentResponse, RefundResponse
from apps.billing.providers.sandbox import SandboxGatewayProvider
from apps.billing.services import (
    calculate_partner_revenue, fulfill_payment, process_refund,
    create_course_payment, create_subscription_payment,
    get_partner_revenue_summary, get_platform_revenue_summary,
    create_or_get_invoice
)
from django.core.exceptions import ValidationError, PermissionDenied


class PaymentProviderAbstractionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='prov_student', email='prov@example.com', password='password123'
        )
        self.instructor = User.objects.create_user(
            username='prov_inst', email='inst@example.com', password='password123'
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='prov-test', defaults={'title': 'Provider Testing Subject'}
        )
        self.course = Course.objects.create(
            title='Intro to Networking',
            slug='intro-networking-prov',
            subject=self.subject,
            owner=self.instructor,
            price=Decimal('30000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )

    def test_provider_registry_discovery(self):
        providers = list_available_providers()
        codes = [p['code'] for p in providers]
        self.assertIn('manual_transfer', codes)
        self.assertIn('sandbox_gateway', codes)

        manual = get_payment_provider('manual_transfer')
        self.assertIsNotNone(manual)
        self.assertEqual(manual.provider_code, 'manual_transfer')

    def test_sandbox_provider_instant_success(self):
        provider = get_payment_provider('sandbox')
        self.assertTrue(isinstance(provider, SandboxGatewayProvider))

        payment, resp = create_course_payment(
            student=self.user,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='SANDBOX-TX-101',
            provider_code='sandbox',
        )
        self.assertEqual(resp.status, 'success')
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

        # Enrollment is immediately active
        enrollment = Enrollment.objects.filter(student=self.user, course=self.course).first()
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)

        # Invoice is automatically generated
        self.assertTrue(hasattr(payment, 'invoice'))
        self.assertEqual(payment.invoice.status, Invoice.Status.PAID)
        self.assertEqual(payment.invoice.amount, Decimal('30000'))

    def test_sandbox_provider_failure(self):
        payment, resp = create_course_payment(
            student=self.user,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='FAIL-TX-999',
            provider_code='sandbox',
        )
        self.assertEqual(resp.status, 'failed')
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(Enrollment.objects.filter(student=self.user, course=self.course).exists())

    def test_custom_provider_registration(self):
        class DummyProvider(BasePaymentProvider):
            provider_code = 'dummy_gateway'
            display_name = 'Dummy Gateway'

            def process_payment(self, request: PaymentRequest) -> PaymentResponse:
                return PaymentResponse(status='success', transaction_id='DUMMY-001')

            def process_refund(self, payment, amount=None, reason='') -> RefundResponse:
                return RefundResponse(status='success', refund_id='REF-DUMMY-001')

        register_payment_provider('dummy_gateway', DummyProvider())
        provider = get_payment_provider('dummy_gateway')
        self.assertEqual(provider.provider_code, 'dummy_gateway')


class PricingAndZeroTrustTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        self.instructor = User.objects.create_user(
            username='pricing_teacher', email='pteach@example.com', password='password123'
        )
        self.institution = Institution.objects.create(
            name='Yangon Tech Partner',
            slug='yangon-tech-partner',
            contact_person=self.instructor,
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='cyber-sec-pricing-test', defaults={'title': 'Cyber Security Pricing'}
        )
        self.course = Course.objects.create(
            title='Network Defense',
            slug='network-defense-sec',
            subject=self.subject,
            owner=self.instructor,
            partner_institution=self.institution,
            price=Decimal('50000'),
            discount_price=Decimal('40000'),
            partner_price=Decimal('25000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )

        self.regular_student = User.objects.create_user(
            username='regular_std', email='reg@example.com', password='password123'
        )
        self.partner_student = User.objects.create_user(
            username='partner_std', email='pstd@example.com', password='password123'
        )
        from apps.partner.models import PartnerStudent
        PartnerStudent.objects.create(
            institution=self.institution,
            student=self.partner_student,
            status=PartnerStudent.Status.ACTIVE,
        )

    def test_promotional_discount_price_for_regular_student(self):
        pricing = self.course.calculate_price_for_user(self.regular_student)
        self.assertEqual(pricing['final_price'], Decimal('40000'))
        self.assertEqual(pricing['pricing_tier'], 'discount')
        self.assertFalse(pricing['is_free'])

    def test_partner_price_precedence_for_affiliated_student(self):
        pricing = self.course.calculate_price_for_user(self.partner_student)
        self.assertEqual(pricing['final_price'], Decimal('25000'))
        self.assertEqual(pricing['pricing_tier'], 'partner')

    def test_special_price_override(self):
        self.course.special_price = Decimal('20000')
        self.course.save()

        pricing = self.course.calculate_price_for_user(self.partner_student)
        self.assertEqual(pricing['final_price'], Decimal('20000'))
        self.assertEqual(pricing['pricing_tier'], 'special')

    def test_membership_covered_course_is_free(self):
        # Give regular_student active Standard membership
        UserSubscription.objects.create(
            user=self.regular_student,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )

        pricing = self.course.calculate_price_for_user(self.regular_student)
        self.assertTrue(pricing['is_free'])
        self.assertEqual(pricing['final_price'], Decimal('0.00'))
        self.assertEqual(pricing['pricing_tier'], 'membership')

    def test_server_side_price_enforcement_and_zero_trust(self):
        # When creating course payment, price is calculated strictly server-side
        payment, resp = create_course_payment(
            student=self.partner_student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='PROOF-REF-1234',
            provider_code='manual_transfer',
        )
        self.assertEqual(payment.amount, Decimal('25000'))
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_cannot_pay_for_already_covered_course(self):
        UserSubscription.objects.create(
            user=self.regular_student,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            create_course_payment(
                student=self.regular_student,
                course=self.course,
                provider_code='manual_transfer',
            )


class PartnerRevenueSplitAndAccountingTests(TestCase):
    def setUp(self):
        self.partner_admin = User.objects.create_user(
            username='partner_admin_acc', email='padmin@example.com', password='password123'
        )
        self.institution = Institution.objects.create(
            name='Mandalay Academy',
            slug='mandalay-academy',
            contact_person=self.partner_admin,
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='it-cat-rev-test', defaults={'title': 'Information Technology Partner Test'}
        )
        self.course = Course.objects.create(
            title='Cloud Solutions',
            slug='cloud-solutions',
            subject=self.subject,
            owner=self.partner_admin,
            partner_institution=self.institution,
            partner_revenue_share_pct=Decimal('75.00'),
            price=Decimal('100000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )
        self.student = User.objects.create_user(
            username='cloud_student', email='cstudent@example.com', password='password123'
        )

    def test_configurable_revenue_split_calculation(self):
        partner_amt, plat_amt, p_pct, pl_pct = calculate_partner_revenue(self.course, Decimal('100000'))
        self.assertEqual(p_pct, Decimal('75.00'))
        self.assertEqual(pl_pct, Decimal('25.00'))
        self.assertEqual(partner_amt, Decimal('75000.00'))
        self.assertEqual(plat_amt, Decimal('25000.00'))

        # Custom configured 80% partner share
        self.course.partner_revenue_share_pct = Decimal('80.00')
        self.course.save()
        partner_amt, plat_amt, p_pct, pl_pct = calculate_partner_revenue(self.course, Decimal('100000'))
        self.assertEqual(partner_amt, Decimal('80000.00'))
        self.assertEqual(plat_amt, Decimal('20000.00'))

    def test_partner_revenue_record_creation_on_fulfillment(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-PARTNER-77',
            provider_code='sandbox',
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)

        record = PartnerRevenueRecord.objects.filter(payment=payment).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.partner_institution, self.institution)
        self.assertEqual(record.course, self.course)
        self.assertEqual(record.gross_amount, Decimal('100000'))
        self.assertEqual(record.partner_amount, Decimal('75000.00'))
        self.assertEqual(record.platform_amount, Decimal('25000.00'))
        self.assertEqual(record.status, PartnerRevenueRecord.Status.PENDING)

    def test_partner_revenue_summary_service(self):
        create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-PARTNER-88',
            provider_code='sandbox',
        )
        summary = get_partner_revenue_summary(self.institution)
        self.assertEqual(summary['total_sales'], 1)
        self.assertEqual(summary['total_enrollments'], 1)
        self.assertEqual(summary['gross_revenue'], Decimal('100000'))
        self.assertEqual(summary['partner_share'], Decimal('75000.00'))
        self.assertEqual(summary['mel_share'], Decimal('25000.00'))
        self.assertEqual(summary['outstanding_balance'], Decimal('75000.00'))
        self.assertEqual(summary['total_refunds'], Decimal('0.00'))

    def test_partner_revenue_report_view_authorization(self):
        client = Client()
        # 1. Anonymous user redirected to login
        url = reverse('partner-revenue-report')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 302)

        # 2. Regular student forbidden
        client.login(username='cloud_student', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 403)

        # 3. Authorized partner admin passes
        client.login(username='partner_admin_acc', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mandalay Academy')
        self.assertContains(resp, 'Audited Financial Transaction Ledger')


class RefundProcessingTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        self.instructor = User.objects.create_user(
            username='ref_instructor', email='rinst@example.com', password='password123'
        )
        self.institution = Institution.objects.create(
            name='Refund Test Partner',
            slug='refund-test-partner',
            contact_person=self.instructor,
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='sec-stud-ref-test', defaults={'title': 'Security Studies Refund Test'}
        )
        self.course = Course.objects.create(
            title='Incident Response',
            slug='incident-response-ref',
            subject=self.subject,
            owner=self.instructor,
            partner_institution=self.institution,
            price=Decimal('60000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )
        self.student = User.objects.create_user(
            username='ref_student', email='rstud@example.com', password='password123'
        )
        self.admin = User.objects.create_superuser(
            username='ref_admin', email='radmin@example.com', password='password123'
        )

    def test_full_course_refund(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-REF-1',
            provider_code='sandbox',
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=self.course, status=Enrollment.Status.ACTIVE).exists())

        # Process refund
        process_refund(payment, amount=Decimal('60000'), reason='Student request within 7-day guarantee', user=self.admin)
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(payment.refunded_amount, Decimal('60000'))
        self.assertEqual(payment.refund_reason, 'Student request within 7-day guarantee')

        # Enrollment is revoked / dropped
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        self.assertEqual(enrollment.status, Enrollment.Status.DROPPED)

        # Partner revenue record is reversed
        revenue_record = PartnerRevenueRecord.objects.get(payment=payment)
        self.assertEqual(revenue_record.status, PartnerRevenueRecord.Status.REFUNDED)
        self.assertEqual(revenue_record.refunded_amount, Decimal('60000'))

        # Invoice is marked REFUNDED
        self.assertEqual(payment.invoice.status, Invoice.Status.REFUNDED)

    def test_subscription_refund(self):
        payment, resp = create_subscription_payment(
            student=self.student,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            method=Payment.Method.KBZ_PAY,
            reference='SUB-TX-99',
            provider_code='sandbox',
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        sub = active_subscription_for(self.student)
        self.assertIsNotNone(sub)
        self.assertTrue(sub.is_current)

        process_refund(payment, reason='Accidental subscription purchase', user=self.admin)
        payment.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertIsNone(active_subscription_for(self.student))
        sub.refresh_from_db()
        self.assertEqual(sub.status, UserSubscription.Status.CANCELLED)
        self.assertFalse(sub.is_active)

    def test_cannot_refund_pending_payment(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-PENDING',
            provider_code='manual_transfer',
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        with self.assertRaises(ValidationError):
            process_refund(payment, reason='Refund before approval')

    def test_cannot_double_refund(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-DOUBLE',
            provider_code='sandbox',
        )
        process_refund(payment, reason='First refund')
        with self.assertRaises(ValidationError):
            process_refund(payment, reason='Second refund attempt')


class SubscriptionLifecycleAndBillingTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.std_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        self.user = User.objects.create_user(
            username='sub_user', email='suser@example.com', password='password123'
        )

    def test_annual_savings_property(self):
        # Monthly is 5,000 * 12 = 60,000, Yearly is 50,000 -> Savings 10,000
        self.assertEqual(self.std_plan.annual_savings, Decimal('10000'))

    def test_subscription_renewal(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        original_end = sub.end_date
        sub.renew(UserSubscription.BillingCycle.MONTHLY)
        sub.refresh_from_db()
        self.assertEqual(sub.end_date, original_end + timezone.timedelta(days=30))

    def test_subscription_cancel_and_expire(self):
        sub = UserSubscription.objects.create(
            user=self.user,
            plan=self.std_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        sub.cancel(reason='Switching to annual plan')
        self.assertEqual(sub.status, UserSubscription.Status.CANCELLED)
        self.assertFalse(sub.is_active)

        # Expiry
        sub.is_active = True
        sub.status = UserSubscription.Status.ACTIVE
        sub.save()
        sub.expire()
        self.assertEqual(sub.status, UserSubscription.Status.EXPIRED)
        self.assertFalse(sub.is_active)


class InvoiceAndDuplicatePreventionTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.instructor = User.objects.create_user(
            username='inv_teacher', email='iteach@example.com', password='password123'
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='math-inv-test', defaults={'title': 'Mathematics Invoice Test'}
        )
        self.course = Course.objects.create(
            title='Discrete Math',
            slug='discrete-math-inv',
            subject=self.subject,
            owner=self.instructor,
            price=Decimal('20000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )
        self.student = User.objects.create_user(
            username='inv_student', email='istud@example.com', password='password123'
        )
        self.other_student = User.objects.create_user(
            username='other_student', email='other@example.com', password='password123'
        )
        self.admin = User.objects.create_superuser(
            username='inv_admin', email='iadmin@example.com', password='password123'
        )

    def test_invoice_generation_and_number_format(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-INV-001',
            provider_code='sandbox',
        )
        invoice = payment.invoice
        self.assertIsNotNone(invoice)
        self.assertTrue(invoice.invoice_number.startswith(f"INV-{timezone.localdate().year}-"))
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.amount, Decimal('20000'))

    def test_invoice_detail_view_permissions(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-INV-002',
            provider_code='sandbox',
        )
        invoice = payment.invoice
        url = reverse('invoice-detail', kwargs={'invoice_id': invoice.id})

        client = Client()
        # 1. Other student receives 403 Forbidden
        client.login(username='other_student', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 403)

        # 2. Owner student receives 200 OK
        client.login(username='inv_student', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, invoice.invoice_number)
        self.assertContains(resp, 'Discrete Math')

        # 3. Admin receives 200 OK
        client.login(username='inv_admin', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_duplicate_pending_payment_prevention(self):
        create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='TX-PEND-1',
            provider_code='manual_transfer',
        )
        with self.assertRaises(ValidationError):
            create_course_payment(
                student=self.student,
                course=self.course,
                method=Payment.Method.KBZ_PAY,
                reference='TX-PEND-2',
                provider_code='manual_transfer',
            )

    def test_duplicate_active_enrollment_payment_prevention(self):
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            status=Enrollment.Status.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            create_course_payment(
                student=self.student,
                course=self.course,
                method=Payment.Method.KBZ_PAY,
                reference='TX-ENROLLED',
                provider_code='manual_transfer',
            )


class PaymentLifecycleStateSafetyTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.student = User.objects.create_user(
            username='lifecycle_user', email='luser@example.com', password='password123'
        )
        self.instructor = User.objects.create_user(
            username='lifecycle_inst', email='linst@example.com', password='password123'
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='lifecycle-sub', defaults={'title': 'Lifecycle Safety Subject'}
        )
        self.course = Course.objects.create(
            title='Security Foundations',
            slug='sec-foundations-lifecycle',
            subject=self.subject,
            owner=self.instructor,
            price=Decimal('25000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )

    def test_lifecycle_state_transitions(self):
        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='STATE-TX-1',
            provider_code='manual_transfer',
        )
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(payment.is_pending)

        # Transition to PROCESSING
        payment.mark_processing()
        self.assertEqual(payment.status, Payment.Status.PROCESSING)
        self.assertTrue(payment.is_processing)

        # Transition to SUCCESS
        payment.mark_success()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertTrue(payment.is_successful)

        # Settled payment cannot be marked FAILED directly
        with self.assertRaises(ValidationError):
            payment.mark_failed(reason='Should fail')

        # Settled payment cannot be marked CANCELLED directly
        with self.assertRaises(ValidationError):
            payment.mark_cancelled(reason='Should fail')

        # Refund settled payment
        payment.mark_refunded(reason='Valid refund')
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertTrue(payment.is_refunded)

        # Refunded payment cannot be revived to SUCCESS or PROCESSING
        with self.assertRaises(ValidationError):
            payment.mark_success()
        with self.assertRaises(ValidationError):
            payment.mark_processing()


class SubscriptionUpgradeAndDowngradeTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.starter_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STARTER)
        self.standard_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        self.premium_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.PREMIUM)
        self.student = User.objects.create_user(
            username='tier_switcher', email='switch@example.com', password='password123'
        )

    def test_upgrade_from_standard_to_premium(self):
        from apps.billing.services import upgrade_subscription
        # Start on Standard
        sub = UserSubscription.objects.create(
            user=self.student,
            plan=self.standard_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        self.assertEqual(sub.plan, self.standard_plan)

        # Upgrade to Premium
        upgraded = upgrade_subscription(
            self.student, self.premium_plan, billing_cycle=UserSubscription.BillingCycle.YEARLY, payment_reference='UPGRADE-001'
        )
        upgraded.refresh_from_db()
        self.assertEqual(upgraded.plan, self.premium_plan)
        self.assertEqual(upgraded.billing_cycle, UserSubscription.BillingCycle.YEARLY)
        self.assertTrue(upgraded.is_current)

    def test_downgrade_from_premium_to_starter(self):
        from apps.billing.services import downgrade_subscription
        sub = UserSubscription.objects.create(
            user=self.student,
            plan=self.premium_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        downgraded = downgrade_subscription(self.student, self.starter_plan)
        downgraded.refresh_from_db()
        self.assertEqual(downgraded.plan, self.starter_plan)
        self.assertIsNone(downgraded.end_date)
        self.assertTrue(downgraded.is_current)

    def test_self_cancellation_web_view_and_api(self):
        UserSubscription.objects.create(
            user=self.student,
            plan=self.standard_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        client = Client()
        client.login(username='tier_switcher', password='password123')

        # Test Web View Cancellation
        resp = client.post(reverse('cancel-subscription'), {'reason': 'Cost saving'})
        self.assertEqual(resp.status_code, 302)
        sub = active_subscription_for(self.student)
        self.assertIsNone(sub)

        # Reactivate and test API Cancellation
        UserSubscription.objects.create(
            user=self.student,
            plan=self.standard_plan,
            billing_cycle=UserSubscription.BillingCycle.MONTHLY,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
        )
        api_resp = client.post(reverse('api-cancel-subscription'), {'reason': 'API cancel test'}, content_type='application/json')
        self.assertEqual(api_resp.status_code, 200)
        self.assertIsNone(active_subscription_for(self.student))


class ExamAndCertificateFeePaymentTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.student = User.objects.create_user(
            username='exam_candidate', email='exam@example.com', password='password123'
        )
        self.instructor = User.objects.create_user(
            username='cert_instructor', email='cinst@example.com', password='password123'
        )
        self.institution = Institution.objects.create(
            name='National Testing Partner',
            slug='national-testing-partner',
            contact_person=self.instructor,
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='exam-sub-cert', defaults={'title': 'Exam & Certificate Subject'}
        )
        self.course = Course.objects.create(
            title='Certified Ethical Hacking',
            slug='certified-ethical-hacking-exam',
            subject=self.subject,
            owner=self.instructor,
            partner_institution=self.institution,
            partner_revenue_share_pct=Decimal('75.00'),
            price=Decimal('50000'),
            exam_required=True,
            exam_voucher_price=Decimal('15000'),
            certificate_fee=Decimal('8000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )

    def test_exam_voucher_payment_fulfillment_and_invoice(self):
        from apps.billing.services import create_exam_voucher_payment
        from apps.billing.models import has_paid_exam_voucher

        self.assertFalse(has_paid_exam_voucher(self.student, self.course))

        payment, resp = create_exam_voucher_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='EXAM-VOUCH-01',
            provider_code='sandbox',
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(payment.payment_type, Payment.PaymentType.EXAM_VOUCHER)
        self.assertEqual(payment.amount, Decimal('15000'))
        self.assertTrue(has_paid_exam_voucher(self.student, self.course))

        # Official Invoice is created with Exam Voucher item title
        self.assertTrue(hasattr(payment, 'invoice'))
        self.assertIn("Exam Voucher", payment.invoice.item_title)

        # Partner revenue record is created with 75% split
        partner_rec = PartnerRevenueRecord.objects.filter(payment=payment).first()
        self.assertIsNotNone(partner_rec)
        self.assertEqual(partner_rec.gross_amount, Decimal('15000'))
        self.assertEqual(partner_rec.partner_amount, Decimal('11250.00'))
        self.assertEqual(partner_rec.platform_amount, Decimal('3750.00'))

    def test_certificate_fee_payment_fulfillment_and_invoice(self):
        from apps.billing.services import create_certificate_fee_payment
        from apps.billing.models import has_paid_certificate_fee

        self.assertFalse(has_paid_certificate_fee(self.student, self.course))

        payment, resp = create_certificate_fee_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.WAVE_PAY,
            reference='CERT-FEE-01',
            provider_code='sandbox',
        )
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(payment.payment_type, Payment.PaymentType.CERTIFICATE_FEE)
        self.assertEqual(payment.amount, Decimal('8000'))
        self.assertTrue(has_paid_certificate_fee(self.student, self.course))

        # Official invoice created
        self.assertTrue(hasattr(payment, 'invoice'))
        self.assertIn("Certificate Fee", payment.invoice.item_title)

        # Partner split created
        partner_rec = PartnerRevenueRecord.objects.filter(payment=payment).first()
        self.assertIsNotNone(partner_rec)
        self.assertEqual(partner_rec.gross_amount, Decimal('8000'))
        self.assertEqual(partner_rec.partner_amount, Decimal('6000.00'))

    def test_refund_exam_voucher_reverses_entitlement_and_partner_ledger(self):
        from apps.billing.services import create_exam_voucher_payment, process_refund
        from apps.billing.models import has_paid_exam_voucher

        payment, _ = create_exam_voucher_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='EXAM-REF-TX',
            provider_code='sandbox',
        )
        self.assertTrue(has_paid_exam_voucher(self.student, self.course))

        process_refund(payment, reason='Exam date cancelled')
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertFalse(has_paid_exam_voucher(self.student, self.course))

        partner_rec = PartnerRevenueRecord.objects.get(payment=payment)
        self.assertEqual(partner_rec.status, PartnerRevenueRecord.Status.REFUNDED)


class PartnerSettlementAndAdminReportingTests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.admin = User.objects.create_superuser(
            username='platform_fin_admin', email='finadmin@example.com', password='password123'
        )
        self.partner_contact = User.objects.create_user(
            username='settle_partner', email='settle@example.com', password='password123'
        )
        self.student = User.objects.create_user(
            username='paying_std_fin', email='pfin@example.com', password='password123'
        )
        self.institution = Institution.objects.create(
            name='Settlement Partner Uni',
            slug='settlement-partner-uni',
            contact_person=self.partner_contact,
        )
        self.subject, _ = Subject.objects.get_or_create(
            slug='settle-subj', defaults={'title': 'Settlement Subject'}
        )
        self.course = Course.objects.create(
            title='Data Engineering',
            slug='data-engineering-settle',
            subject=self.subject,
            owner=self.partner_contact,
            partner_institution=self.institution,
            partner_revenue_share_pct=Decimal('75.00'),
            price=Decimal('80000'),
            is_published=True,
            status=Course.Status.PUBLISHED,
        )

    def test_partner_revenue_settlement_services_and_view(self):
        from apps.billing.services import settle_partner_revenue_record, settle_partner_records_for_institution

        payment, resp = create_course_payment(
            student=self.student,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='SETTLE-TX-01',
            provider_code='sandbox',
        )
        record = PartnerRevenueRecord.objects.get(payment=payment)
        self.assertEqual(record.status, PartnerRevenueRecord.Status.PENDING)

        # Admin settles via service
        settle_partner_revenue_record(record, settled_by=self.admin)
        record.refresh_from_db()
        self.assertEqual(record.status, PartnerRevenueRecord.Status.SETTLED)
        self.assertIsNotNone(record.settled_at)

        # Batch settlement
        student2 = User.objects.create_user(
            username='batch_settle_std', email='batch@example.com', password='password123'
        )
        payment2, _ = create_course_payment(
            student=student2,
            course=self.course,
            method=Payment.Method.KBZ_PAY,
            reference='SETTLE-TX-02',
            provider_code='sandbox',
        )
        count = settle_partner_records_for_institution(self.institution, settled_by=self.admin)
        self.assertEqual(count, 1)

    def test_platform_revenue_report_view_authorization(self):
        client = Client()
        # 1. Anonymous redirected to login
        url = reverse('platform-revenue-report')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 302)

        # 2. Regular student forbidden
        client.login(username='paying_std_fin', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 403)

        # 3. Superuser/Admin gets 200 OK
        client.login(username='platform_fin_admin', password='password123')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Platform Revenue & Financial Ledger')
        self.assertContains(resp, 'Revenue Breakdown by Stream')

    def test_payment_webhook_idempotent_fulfillment(self):
        # Create a pending payment
        payment = Payment.objects.create(
            student=self.student,
            course=self.course,
            payment_type=Payment.PaymentType.COURSE_PURCHASE,
            provider='sandbox',
            amount=Decimal('80000'),
            currency='MMK',
            billing_period='one_time',
            platform_fee=Decimal('20000'),
            teacher_amount=Decimal('60000'),
            reference='WEBHOOK-REF-777',
            status=Payment.Status.PENDING,
        )

        client = Client()
        webhook_url = reverse('api-payment-webhook', kwargs={'provider_code': 'sandbox'})

        # Provider calls webhook with success event
        resp = client.post(webhook_url, {
            'reference': 'WEBHOOK-REF-777',
            'status': 'success',
            'transaction_id': 'GATEWAY-TRX-101',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=self.course, status=Enrollment.Status.ACTIVE).exists())
        self.assertTrue(hasattr(payment, 'invoice'))

        # Idempotent second webhook call does not duplicate
        resp2 = client.post(webhook_url, {
            'reference': 'WEBHOOK-REF-777',
            'status': 'success',
        }, content_type='application/json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(Enrollment.objects.filter(student=self.student, course=self.course).count(), 1)



