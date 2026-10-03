import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.courses.models import Course


def commission_rate():
    """Platform share of every approved payment (default 25 %)."""
    return getattr(settings, 'PAYMENT_PLATFORM_COMMISSION_RATE', 0.25)


class SubscriptionPlan(BaseModel):
    """
    Student Membership Subscription Tiers:
    - Starter: Free (0 MMK)
    - Standard: 5,000 MMK/month (50,000 MMK/year)
    - Premium: 15,000 MMK/month (150,000 MMK/year)
    """

    class PlanType(models.TextChoices):
        STARTER = 'starter', 'Starter (Free)'
        STANDARD = 'standard', 'Standard'
        PREMIUM = 'premium', 'Premium'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64)
    plan_type = models.CharField(
        max_length=16, choices=PlanType.choices, unique=True
    )
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    currency = models.CharField(max_length=8, default='MMK')
    description = models.TextField(blank=True)

    # Entitlements
    has_all_standard_courses = models.BooleanField(default=False)
    has_premium_courses = models.BooleanField(default=False)
    has_cyber_range = models.BooleanField(default=False)
    has_capstone_projects = models.BooleanField(default=False)
    has_priority_support = models.BooleanField(default=False)
    live_class_discount_percent = models.PositiveIntegerField(default=0)

    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'monthly_price']

    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"

    @classmethod
    def ensure_default_plans(cls):
        """Seed the 3 official membership tiers."""
        plans_data = [
            {
                'plan_type': cls.PlanType.STARTER,
                'name': 'Starter',
                'monthly_price': Decimal('0'),
                'yearly_price': Decimal('0'),
                'description': 'Free introductory tier for exploratory learning, previews, and free lessons.',
                'has_all_standard_courses': False,
                'has_premium_courses': False,
                'has_cyber_range': False,
                'has_capstone_projects': False,
                'has_priority_support': False,
                'live_class_discount_percent': 0,
                'order': 1,
            },
            {
                'plan_type': cls.PlanType.STANDARD,
                'name': 'Standard',
                'monthly_price': Decimal('5000'),
                'yearly_price': Decimal('50000'),
                'description': 'Full access to standard courses across all disciplines, quizzes, assignments, and certificates.',
                'has_all_standard_courses': True,
                'has_premium_courses': False,
                'has_cyber_range': False,
                'has_capstone_projects': False,
                'has_priority_support': False,
                'live_class_discount_percent': 0,
                'order': 2,
            },
            {
                'plan_type': cls.PlanType.PREMIUM,
                'name': 'Premium',
                'monthly_price': Decimal('15000'),
                'yearly_price': Decimal('150000'),
                'description': 'Ultimate access: all standard & premium courses, practical Cyber Range labs, capstones, and 20% live class discount.',
                'has_all_standard_courses': True,
                'has_premium_courses': True,
                'has_cyber_range': True,
                'has_capstone_projects': True,
                'has_priority_support': True,
                'live_class_discount_percent': 20,
                'order': 3,
            },
        ]
        created_or_updated = []
        for data in plans_data:
            ptype = data.pop('plan_type')
            plan, _ = cls.objects.update_or_create(plan_type=ptype, defaults=data)
            created_or_updated.append(plan)
        return created_or_updated


class UserSubscription(BaseModel):
    """
    An active subscription assigned to a student.
    """

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY = 'yearly', 'Yearly'
        LIFETIME = 'lifetime', 'Lifetime Free'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'
        PENDING = 'pending', 'Pending Approval'
        SUSPENDED = 'suspended', 'Suspended'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions'
    )
    billing_cycle = models.CharField(
        max_length=16, choices=BillingCycle.choices, default=BillingCycle.MONTHLY
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    auto_renew = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=128, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(
        null=True, blank=True, help_text="Null for lifetime / free"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.get_billing_cycle_display()})"

    @property
    def is_current(self):
        if not self.is_active or self.status != self.Status.ACTIVE:
            return False
        if self.end_date is None:
            return True
        return self.end_date >= timezone.localdate()


class Payment(BaseModel):
    """
    A manual payment submitted by a student (KBZ Pay / Wave Pay / bank transfer)
    and reviewed by an administrator.

    Can be for an individual Course OR a SubscriptionPlan.
    Approval activates the student's enrolment on the course or provisions their subscription.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        REFUNDED = 'refunded', 'Refunded'

    class Method(models.TextChoices):
        KBZ_PAY = 'kbz_pay', 'KBZ Pay'
        WAVE_PAY = 'wave_pay', 'Wave Pay'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        OTHER = 'other', 'Other'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments'
    )
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name='payments',
        null=True, blank=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default='MMK')
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    teacher_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.25)

    billing_period = models.CharField(
        max_length=16, choices=Course.BillingPeriod.choices,
        default=Course.BillingPeriod.ONE_TIME,
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(
        null=True, blank=True, help_text="Null means permanent one-time access."
    )

    method = models.CharField(
        max_length=16, choices=Method.choices, default=Method.KBZ_PAY
    )
    reference = models.CharField(
        max_length=128, blank=True,
        help_text="Transaction ID, wallet phone number or bank reference.",
    )
    receipt = models.FileField(upload_to='payments/receipts/', null=True, blank=True)
    note = models.TextField(blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_payments',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['student', 'course']),
            models.Index(fields=['student', 'plan']),
        ]

    def __str__(self):
        item = self.course.title if self.course else (self.plan.name if self.plan else 'General')
        return f'{self.amount} {self.currency} - {self.student.username} / {item}'

    @classmethod
    def split(cls, amount):
        """Return ``(platform_fee, teacher_amount)`` for a gross amount."""
        amount = Decimal(str(amount))
        fee = (amount * Decimal(str(commission_rate()))).quantize(Decimal('0.01'))
        return fee, amount - fee

    @property
    def is_current(self):
        """Approved and not expired (monthly payments carry a period_end)."""
        if self.status != self.Status.APPROVED:
            return False
        if self.period_end is None:
            return True
        return self.period_end >= timezone.localdate()


def active_payment_for(user, course):
    """The approved, unexpired payment that unlocks ``course`` for ``user``."""
    return (
        Payment.objects.filter(student=user, course=course, status=Payment.Status.APPROVED)
        .order_by('-created_at')
        .first()
    )


def active_subscription_for(user):
    """The active, unexpired subscription tier for ``user``."""
    if not getattr(user, 'is_authenticated', False):
        return None
    sub = (
        UserSubscription.objects.filter(user=user, is_active=True)
        .select_related('plan')
        .order_by('-created_at')
        .first()
    )
    if sub and sub.is_current:
        return sub
    return None
