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

