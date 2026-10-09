from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.billing.models import SubscriptionPlan, UserSubscription

User = get_user_model()


class PricingPageUITests(TestCase):
    def setUp(self):
        SubscriptionPlan.ensure_default_plans()
        self.client = Client()
        self.student = User.objects.create_user(
            username='pricing_student', email='pstudent@example.com', password='password123'
        )

    def test_public_pricing_page_renders_cleanly(self):
        """Unauthenticated visitors should see all 3 tiers, features, prices, and payment methods."""
        res = self.client.get(reverse('pricing'))
        self.assertEqual(res.status_code, 200)

        # Basic structure & titles
        self.assertContains(res, 'Affordable Learning for Everyone in')
        self.assertContains(res, 'lang-en')
        self.assertContains(res, 'lang-my')

        # Tiers present
        self.assertContains(res, 'Starter')
        self.assertContains(res, 'Standard')
        self.assertContains(res, 'Premium')

        # Prices present
        self.assertContains(res, '5,000')
        self.assertContains(res, '50,000')
        self.assertContains(res, '15,000')
        self.assertContains(res, '150,000')

        # Interactive billing switcher
        self.assertContains(res, 'billingMonthlyBtn')
        self.assertContains(res, 'billingYearlyBtn')

        # Payment options
        self.assertContains(res, 'KBZPay (KPay)')
        self.assertContains(res, 'Wave Money')
        self.assertContains(res, '09-974288199')

        # Entitlements Comparison Matrix
        self.assertContains(res, 'Feature Breakdown &amp; Entitlements')
        self.assertContains(res, 'Interactive Cyber Range &amp; Docker Labs')
        self.assertContains(res, 'Official Exams &amp; QR Certificates')

        # Public layout should have no sidebar
        self.assertNotContains(res, '<aside id="melSidebar"')

    def test_authenticated_student_active_plan_state(self):
        """Active subscribers see their current tier marked as Active Plan."""
        starter_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STARTER)
        UserSubscription.objects.create(
            user=self.student,
            plan=starter_plan,
            billing_cycle=UserSubscription.BillingCycle.LIFETIME,
            is_active=True,
        )

        self.client.force_login(self.student)
        res = self.client.get(reverse('pricing'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Current Active Plan')

    def test_subscribe_page_ui(self):
        """Subscribe page for Standard tier displays payment accounts and submission form."""
        self.client.force_login(self.student)
        res = self.client.get(reverse('subscribe', kwargs={'plan_type': 'standard'}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Standard Membership')
        self.assertContains(res, 'KBZPay (KPay)')
        self.assertContains(res, '09-974288199')
        self.assertContains(res, 'Submit Subscription Payment')
