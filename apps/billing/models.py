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

    @property
    def annual_savings(self):
        diff = (self.monthly_price * Decimal('12')) - self.yearly_price
        return diff if diff > 0 else Decimal('0.00')

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

    def renew(self, billing_cycle=None):
        """Extends subscription end date."""
        cycle = billing_cycle or self.billing_cycle
        days = 365 if cycle == self.BillingCycle.YEARLY else 30
        base = self.end_date if (self.end_date and self.end_date >= timezone.localdate()) else timezone.localdate()
        self.end_date = base + timezone.timedelta(days=days)
        self.is_active = True
        self.status = self.Status.ACTIVE
        self.save(update_fields=['end_date', 'is_active', 'status', 'updated_at'])

    def cancel(self, reason=''):
        """Cancels auto-renew and deactivates subscription."""
        self.is_active = False
        self.auto_renew = False
        self.status = self.Status.CANCELLED
        self.save(update_fields=['is_active', 'auto_renew', 'status', 'updated_at'])

    def expire(self):
        """Marks subscription expired."""
        self.is_active = False
        self.status = self.Status.EXPIRED
        self.save(update_fields=['is_active', 'status', 'updated_at'])

    def upgrade(self, new_plan, billing_cycle=None, payment_reference=''):
        """Upgrades subscription to a higher tier plan."""
        cycle = billing_cycle or self.billing_cycle
        days = 365 if cycle == self.BillingCycle.YEARLY else 30
        now_date = timezone.localdate()
        self.plan = new_plan
        self.billing_cycle = cycle
        self.start_date = now_date
        self.end_date = now_date + timezone.timedelta(days=days)
        self.is_active = True
        self.status = self.Status.ACTIVE
        if payment_reference:
            self.payment_reference = payment_reference
        self.save(update_fields=['plan', 'billing_cycle', 'start_date', 'end_date', 'is_active', 'status', 'payment_reference', 'updated_at'])
        return self

    def downgrade(self, new_plan, billing_cycle=None, payment_reference=''):
        """Downgrades subscription to a lower tier plan or Starter."""
        cycle = billing_cycle or self.billing_cycle
        now_date = timezone.localdate()
        self.plan = new_plan
        self.billing_cycle = cycle
        self.start_date = now_date
        if new_plan.plan_type == SubscriptionPlan.PlanType.STARTER or cycle == self.BillingCycle.LIFETIME:
            self.end_date = None
        else:
            days = 365 if cycle == self.BillingCycle.YEARLY else 30
            self.end_date = now_date + timezone.timedelta(days=days)
        self.is_active = True
        self.status = self.Status.ACTIVE
        if payment_reference:
            self.payment_reference = payment_reference
        self.save(update_fields=['plan', 'billing_cycle', 'start_date', 'end_date', 'is_active', 'status', 'payment_reference', 'updated_at'])
        return self


class Payment(BaseModel):
    """
    Payment abstraction model for manual and gateway payments.
    Can be for a Course, SubscriptionPlan, Exam Voucher, or Certificate Fee.
    """

    class PaymentType(models.TextChoices):
        COURSE_PURCHASE = 'course_purchase', 'Course Purchase'
        SUBSCRIPTION = 'subscription', 'Subscription'
        EXAM_VOUCHER = 'exam_voucher', 'Exam Voucher'
        CERTIFICATE_FEE = 'certificate_fee', 'Certificate Fee'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting review'
        PROCESSING = 'processing', 'Processing'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class Method(models.TextChoices):
        KBZ_PAY = 'kbz_pay', 'KBZ Pay'
        WAVE_PAY = 'wave_pay', 'Wave Pay'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        SANDBOX = 'sandbox', 'Sandbox Gateway'
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
    payment_type = models.CharField(
        max_length=32, choices=PaymentType.choices, default=PaymentType.COURSE_PURCHASE, db_index=True
    )
    provider = models.CharField(max_length=32, default='manual_transfer', db_index=True)
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
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

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
            models.Index(fields=['payment_type', 'status']),
        ]

    def __str__(self):
        item = self.course.title if self.course else (self.plan.name if self.plan else self.get_payment_type_display())
        return f'{self.amount} {self.currency} - {self.student.username} / {item}'

    @classmethod
    def split(cls, amount):
        """Return ``(platform_fee, teacher_amount)`` for a gross amount."""
        amount = Decimal(str(amount))
        fee = (amount * Decimal(str(commission_rate()))).quantize(Decimal('0.01'))
        return fee, amount - fee

    @property
    def is_successful(self):
        return self.status in [self.Status.SUCCESS, self.Status.APPROVED]

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_processing(self):
        return self.status == self.Status.PROCESSING

    @property
    def is_refunded(self):
        return self.status == self.Status.REFUNDED

    @property
    def is_failed(self):
        return self.status in [self.Status.FAILED, self.Status.REJECTED]

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    def mark_processing(self):
        if self.status == self.Status.REFUNDED:
            from django.core.exceptions import ValidationError
            raise ValidationError("Refunded payment cannot be moved to processing.")
        self.status = self.Status.PROCESSING
        self.save(update_fields=['status', 'updated_at'])

    def mark_success(self, reviewer=None):
        if self.status == self.Status.REFUNDED:
            from django.core.exceptions import ValidationError
            raise ValidationError("Refunded payment cannot be marked as success.")
        self.status = self.Status.SUCCESS
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

    def mark_failed(self, reason='', status=None):
        if self.status in [self.Status.SUCCESS, self.Status.APPROVED]:
            from django.core.exceptions import ValidationError
            raise ValidationError("Settled successful payment cannot be marked failed. Process a refund instead.")
        self.status = status or self.Status.FAILED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])

    def mark_cancelled(self, reason=''):
        if self.status in [self.Status.SUCCESS, self.Status.APPROVED]:
            from django.core.exceptions import ValidationError
            raise ValidationError("Settled successful payment cannot be cancelled. Process a refund instead.")
        self.status = self.Status.CANCELLED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])

    def mark_refunded(self, amount=None, reason=''):
        if self.status not in [self.Status.SUCCESS, self.Status.APPROVED]:
            from django.core.exceptions import ValidationError
            raise ValidationError("Only successful/approved payments can be marked as refunded.")
        self.status = self.Status.REFUNDED
        self.refunded_amount = amount or self.amount
        self.refund_reason = reason
        self.refunded_at = timezone.now()
        self.save(update_fields=['status', 'refunded_amount', 'refund_reason', 'refunded_at', 'updated_at'])

    @property
    def is_current(self):
        """Approved or successful and not expired (monthly payments carry a period_end)."""
        if not self.is_successful:
            return False
        if self.period_end is None:
            return True
        return self.period_end >= timezone.localdate()


class PartnerRevenueRecord(BaseModel):
    """
    Audited financial ledger record recording partner earnings split.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Settlement'
        SETTLED = 'settled', 'Settled'
        REFUNDED = 'refunded', 'Refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='partner_revenue_records'
    )
    partner_institution = models.ForeignKey(
        'partner.Institution', on_delete=models.CASCADE, related_name='revenue_records'
    )
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='partner_revenue_records'
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    partner_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=75.00,
        help_text="Partner entitlement percentage."
    )
    platform_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=25.00,
        help_text="MEL platform commission percentage."
    )
    partner_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['partner_institution', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        course_name = self.course.title if self.course else "Institutional Course"
        return f"{self.partner_institution.name} - {course_name} ({self.partner_amount} MMK)"


class Invoice(BaseModel):
    """
    Official student invoice and tax-deductible receipt for payment verification.
    """
    class Status(models.TextChoices):
        ISSUED = 'issued', 'Issued'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'
        VOIDED = 'voided', 'Voided'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=64, unique=True, db_index=True)
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name='invoice'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices'
    )
    item_title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='MMK')
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PAID, db_index=True
    )
    billing_name = models.CharField(max_length=255, blank=True)
    billing_email = models.EmailField(blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_number} ({self.amount} {self.currency}) - {self.student.username}"

    @classmethod
    def generate_invoice_number(cls):
        import secrets
        token = secrets.token_hex(4).upper()
        year = timezone.localdate().year
        return f"INV-{year}-{token}"


def active_payment_for(user, course):
    """The approved / successful, unexpired payment that unlocks ``course`` for ``user``."""
    if not getattr(user, 'is_authenticated', False):
        return None
    return (
        Payment.objects.filter(
            student=user,
            course=course,
            status__in=[Payment.Status.APPROVED, Payment.Status.SUCCESS]
        )
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


def has_paid_exam_voucher(user, course):
    """Checks whether the student holds an approved/successful exam voucher for ``course``."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if not getattr(course, 'exam_required', False) or getattr(course, 'exam_voucher_price', 0) <= 0:
        return True
    return Payment.objects.filter(
        student=user,
        course=course,
        payment_type=Payment.PaymentType.EXAM_VOUCHER,
        status__in=[Payment.Status.APPROVED, Payment.Status.SUCCESS]
    ).exists()


def has_paid_certificate_fee(user, course):
    """Checks whether the student has paid the certificate issuance fee for ``course``."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(course, 'certificate_fee', 0) <= 0:
        return True
    return Payment.objects.filter(
        student=user,
        course=course,
        payment_type=Payment.PaymentType.CERTIFICATE_FEE,
        status__in=[Payment.Status.APPROVED, Payment.Status.SUCCESS]
    ).exists()

