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


class PaymentMethod(BaseModel):
    """
    Accepted payment methods managed dynamically by administrators.
    Supports national MMQR, mobile wallets, and bank transfers.
    """
    class MethodType(models.TextChoices):
        QR = 'qr', 'QR Code (MMQR / Dynamic QR)'
        CARD = 'card', 'Card Payment (Visa / Mastercard / MPU / JCB)'
        WALLET = 'wallet', 'Mobile Wallet (KBZPay / WavePay / AYA Pay)'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        GATEWAY = 'gateway', 'Online Payment Gateway'
        OTHER = 'other', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=True, db_index=True)
    name = models.CharField(max_length=64)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    method_type = models.CharField(
        max_length=20, choices=MethodType.choices, default=MethodType.QR
    )
    account_name = models.CharField(max_length=128, blank=True)
    account_number = models.CharField(max_length=128, blank=True)
    qr_image = models.FileField(upload_to='payments/qrs/', null=True, blank=True)
    instructions = models.TextField(blank=True)
    instructions_my = models.TextField(
        blank=True, help_text="Myanmar language payment instructions."
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['display_order', 'name']

    def __str__(self):
        status = "Active" if self.is_active else "Disabled"
        return f"{self.name} ({self.get_method_type_display()}) - {status}"

    @property
    def is_mmqr(self) -> bool:
        return self.code == 'mmqr' or self.method_type == self.MethodType.QR

    @property
    def is_card(self) -> bool:
        return self.method_type == self.MethodType.CARD or self.code in ['visa', 'mastercard', 'mpu', 'visa_master', 'card']

    @property
    def is_wallet(self) -> bool:
        return self.method_type == self.MethodType.WALLET

    @property
    def is_bank(self) -> bool:
        return self.method_type == self.MethodType.BANK_TRANSFER

    def is_ready_for_checkout(self) -> bool:
        """
        MMQR is only ready for customer checkout if it is enabled AND
        has an actual administrator-uploaded QR image.
        """
        return bool(self.is_active and self.qr_image)

    def get_missing_requirements(self) -> list:
        """Returns list of missing requirements to display as admin warnings."""
        missing = []
        if not self.is_active:
            missing.append("Availability status is currently set to Disabled.")
        if not self.qr_image:
            missing.append("Official MMQR code image has not been uploaded.")
        if not (self.account_name or '').strip():
            missing.append("Merchant / Platform display name is missing.")
        if not (self.instructions or self.instructions_my or '').strip():
            missing.append("Customer payment instructions are missing.")
        return missing

    @classmethod
    def get_mmqr(cls):
        """Retrieves or creates the canonical MMQR payment method."""
        mmqr = cls.objects.filter(code='mmqr').first()
        if not mmqr:
            mmqr, _ = cls.objects.get_or_create(
                code='mmqr',
                defaults={
                    'name': 'MMQR',
                    'method_type': cls.MethodType.QR,
                    'account_name': 'THUTA E-Learning Platform',
                    'account_number': '',
                    'instructions': 'Scan the official MMQR with any Myanmar banking or mobile wallet app (KBZPay, WavePay, AYA Pay, CB Pay, etc.). Pay the exact amount displayed above and submit your transaction slip below.',
                    'instructions_my': 'မည်သည့် မြန်မာမိုဘိုင်းဘဏ် သို့မဟုတ် ဝေါလက်အက်ပ်ဖြင့်မဆို (KBZPay, WavePay, AYA, CB စသည်) တရားဝင် MMQR ကို စကင်ဖတ်ပါ။ အထက်ဖော်ပြပါ ငွေပမာဏအတိအကျကို ထည့်သွင်းပေးချေပြီး ငွေလွှဲပြေစာနံပါတ် သို့မဟုတ် စလစ်ကို အောက်တွင် တင်သွင်းပါ။',
                    'display_order': 1,
                    'is_active': False,
                }
            )
        return mmqr

    @classmethod
    def ensure_default_methods(cls):
        defaults = [
            {
                'code': 'mmqr',
                'name': 'MMQR',
                'method_type': cls.MethodType.QR,
                'account_name': 'THUTA E-Learning Platform',
                'instructions': 'Scan the MMQR with any supported Myanmar banking or wallet app.',
                'instructions_my': 'မည်သည့် မြန်မာ မိုဘိုင်းဘဏ် သို့မဟုတ် ဝေါလက် အက်ပ်ဖြင့်မဆို MMQR ကို စကင်ဖတ်၍ ပေးချေနိုင်ပါသည်။',
                'display_order': 1,
                'is_active': False,
            },
            {
                'code': 'visa_master',
                'name': 'Visa / Mastercard',
                'method_type': cls.MethodType.CARD,
                'account_name': 'THUTA E-Learning Co., Ltd.',
                'account_number': 'Merchant ID: THUTA-CARD-01',
                'instructions': 'Pay via Visa or Mastercard credit/debit card. Submit payment reference number and transaction slip.',
                'instructions_my': 'Visa သို့မဟုတ် Mastercard ကတ်ဖြင့် ပေးချေပါ။ ငွေလွှဲခွင့်ပြုချက်နံပါတ် သို့မဟုတ် စလစ်ကို ထည့်သွင်းပါ။',
                'display_order': 2,
                'is_active': False,
            },
            {
                'code': 'mpu',
                'name': 'MPU Card (Myanmar Payment Union)',
                'method_type': cls.MethodType.CARD,
                'account_name': 'THUTA E-Learning Co., Ltd.',
                'account_number': 'Merchant ID: THUTA-MPU-01',
                'instructions': 'Pay via Myanmar Payment Union (MPU) debit card. Submit authorization code or receipt.',
                'instructions_my': 'MPU ကတ်ဖြင့် ပေးချေပါ။ ငွေလွှဲခွင့်ပြုချက်နံပါတ် သို့မဟုတ် စလစ်ကို ထည့်သွင်းပါ။',
                'display_order': 3,
                'is_active': False,
            },
            {
                'code': 'kbz_pay',
                'name': 'KBZPay (KPay)',
                'method_type': cls.MethodType.WALLET,
                'account_name': 'THUTA Academy',
                'account_number': '09-974288199',
                'instructions': 'Transfer to the KBZPay phone number and attach screenshot.',
                'instructions_my': 'KBZPay ဖုန်းနံပါတ်သို့ လွှဲပြီး ငွေလွှဲပြေစာ screenshot ထည့်သွင်းပါ။',
                'display_order': 4,
                'is_active': True,
            },
            {
                'code': 'wave_pay',
                'name': 'Wave Money (WavePay)',
                'method_type': cls.MethodType.WALLET,
                'account_name': 'THUTA Academy',
                'account_number': '09-974288199',
                'instructions': 'Transfer to the WavePay phone number and attach screenshot.',
                'instructions_my': 'WavePay ဖုန်းနံပါတ်သို့ လွှဲပြီး ငွေလွှဲပြေစာ screenshot ထည့်သွင်းပါ။',
                'display_order': 5,
                'is_active': True,
            },
            {
                'code': 'bank_transfer',
                'name': 'KBZ Bank Transfer',
                'method_type': cls.MethodType.BANK_TRANSFER,
                'account_name': 'THUTA E-Learning Co., Ltd.',
                'account_number': '1234-5678-9012-3456',
                'instructions': 'Transfer to KBZ Bank account and attach bank receipt.',
                'instructions_my': 'KBZ ဘဏ်အကောင့်သို့ လွှဲပြီး ငွေလွှဲစလစ် ထည့်သွင်းပါ။',
                'display_order': 6,
                'is_active': True,
            },
        ]
        created_or_updated = []
        for d in defaults:
            code = d.pop('code')
            obj, _ = cls.objects.get_or_create(code=code, defaults=d)
            created_or_updated.append(obj)
        return created_or_updated

    @classmethod
    def ensure_defaults(cls):
        return cls.ensure_default_methods()


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
        MMQR = 'mmqr', 'MMQR'
        VISA = 'visa', 'Visa'
        MASTERCARD = 'mastercard', 'Mastercard'
        MPU = 'mpu', 'MPU Card'
        CARD = 'card', 'Card Payment'
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
    exam = models.ForeignKey(
        'courses.Quiz', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    payment_type = models.CharField(
        max_length=32, choices=PaymentType.choices, default=PaymentType.COURSE_PURCHASE, db_index=True
    )
    provider = models.CharField(max_length=32, default='manual_transfer', db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    original_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Original price before discount."
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Total discount applied."
    )
    coupon_code = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="Coupon code redeemed at checkout."
    )
    promotion = models.ForeignKey(
        'billing.Promotion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments'
    )
    currency = models.CharField(max_length=8, default='MMK')
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    teacher_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.25)

    # Frozen financial split attributes (immutable upon settlement)
    instructor_level_at_payment = models.CharField(
        max_length=32, blank=True, default='', db_index=True,
        help_text="Instructor pedagogical rank frozen at transaction time."
    )
    platform_commission_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        help_text="Platform commission percentage frozen at payment settlement."
    )
    instructor_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('50.00'),
        help_text="Instructor revenue share percentage frozen at payment settlement."
    )
    net_financial_basis = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Actual net discounted amount paid by student forming financial basis."
    )

    billing_period = models.CharField(
        max_length=16, choices=Course.BillingPeriod.choices,
        default=Course.BillingPeriod.ONE_TIME,
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(
        null=True, blank=True, help_text="Null means permanent one-time access."
    )

    method = models.CharField(
        max_length=32, choices=Method.choices, default=Method.KBZ_PAY
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
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['student', 'plan']),
            models.Index(fields=['payment_type', 'status']),
        ]

    def __str__(self):
        item = self.course.title if self.course else (self.exam.title if self.exam else (self.plan.name if self.plan else self.get_payment_type_display()))
        return f'{self.amount} {self.currency} - {self.student.username} / {item}'

    @classmethod
    def calculate_level_split(cls, amount, course=None):
        """
        Calculates exact revenue share split based on instructor level or partner terms:
        - Freezes financial basis to actual discounted amount paid by the student.
        - Associate Instructor: THUTA 60% / Instructor 40%
        - Instructor: THUTA 50% / Instructor 50%
        - Professional Instructor: THUTA 40% / Instructor 60%
        - Teacher: Entry level (only free tutorials; 100% platform / 0% teacher fallback)
        - Partner Course: Partner share based on course.partner_revenue_share_pct (e.g. 75/25)
        - Platform Course / Subscription: THUTA 100% / Instructor 0%
        """
        amount = Decimal(str(amount or '0.00')).quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            return {
                'platform_fee': Decimal('0.00'),
                'teacher_amount': Decimal('0.00'),
                'platform_commission_pct': Decimal('50.00'),
                'instructor_share_pct': Decimal('50.00'),
                'instructor_level_at_payment': '',
                'net_financial_basis': Decimal('0.00'),
            }

        if not course:
            comm_rate = Decimal(str(commission_rate()))
            plat_fee = (amount * comm_rate).quantize(Decimal('0.01'))
            teach_amt = amount - plat_fee
            plat_pct = (comm_rate * Decimal('100.00')).quantize(Decimal('0.01'))
            return {
                'platform_fee': plat_fee,
                'teacher_amount': teach_amt,
                'platform_commission_pct': plat_pct,
                'instructor_share_pct': Decimal('100.00') - plat_pct,
                'instructor_level_at_payment': '',
                'net_financial_basis': amount,
            }

        # Check partner course
        if getattr(course, 'partner_institution', None):
            raw_partner_pct = getattr(course, 'partner_revenue_share_pct', None)
            partner_pct = Decimal(str(raw_partner_pct if raw_partner_pct is not None else '75.00'))
            plat_pct = Decimal('100.00') - partner_pct
            plat_fee = (amount * (plat_pct / Decimal('100.00'))).quantize(Decimal('0.01'))
            return {
                'platform_fee': plat_fee,
                'teacher_amount': Decimal('0.00'),
                'platform_commission_pct': plat_pct,
                'instructor_share_pct': Decimal('0.00'),
                'instructor_level_at_payment': '',
                'net_financial_basis': amount,
            }

        # Check official platform course or no owner
        owner = getattr(course, 'owner', None)
        if not owner or getattr(course, 'is_official', False) or getattr(owner, 'is_admin', False):
            return {
                'platform_fee': amount,
                'teacher_amount': Decimal('0.00'),
                'platform_commission_pct': Decimal('100.00'),
                'instructor_share_pct': Decimal('0.00'),
                'instructor_level_at_payment': '',
                'net_financial_basis': amount,
            }

        # Individual instructor course
        teacher_profile = getattr(owner, 'teacher_profile', None)
        from apps.users.models import InstructorLevel
        clvl = getattr(teacher_profile, 'canonical_level', None)

        if clvl == InstructorLevel.ASSOCIATE_INSTRUCTOR:
            plat_pct = Decimal('60.00')
            inst_pct = Decimal('40.00')
        elif clvl == InstructorLevel.INSTRUCTOR:
            plat_pct = Decimal('50.00')
            inst_pct = Decimal('50.00')
        elif clvl == InstructorLevel.PROFESSIONAL_INSTRUCTOR:
            plat_pct = Decimal('40.00')
            inst_pct = Decimal('60.00')
        else:
            # Fallback to default platform commission rate for backwards compatibility
            comm_rate = Decimal(str(commission_rate()))
            plat_pct = (comm_rate * Decimal('100.00')).quantize(Decimal('0.01'))
            inst_pct = Decimal('100.00') - plat_pct
            clvl = clvl or ''

        plat_fee = (amount * (plat_pct / Decimal('100.00'))).quantize(Decimal('0.01'))
        teach_amt = amount - plat_fee

        return {
            'platform_fee': plat_fee,
            'teacher_amount': teach_amt,
            'platform_commission_pct': plat_pct,
            'instructor_share_pct': inst_pct,
            'instructor_level_at_payment': clvl or '',
            'net_financial_basis': amount,
        }

    @classmethod
    def split(cls, amount, course=None):
        """Return ``(platform_fee, teacher_amount)`` for a gross amount."""
        res = cls.calculate_level_split(amount, course=course)
        return res['platform_fee'], res['teacher_amount']

    def freeze_revenue_split(self):
        """
        Freezes revenue split percentages and amounts at transaction time.
        Once set, historical records remain immutable regardless of future
        instructor promotions or platform policy changes.
        """
        if self.payment_type == self.PaymentType.SUBSCRIPTION or not self.course:
            self.net_financial_basis = self.amount
            self.platform_commission_pct = Decimal('100.00')
            self.instructor_share_pct = Decimal('0.00')
            self.instructor_level_at_payment = ''
            self.platform_fee = self.amount
            self.teacher_amount = Decimal('0.00')
            return

        split = self.calculate_level_split(self.amount, course=self.course)
        self.net_financial_basis = split['net_financial_basis']
        self.platform_commission_pct = split['platform_commission_pct']
        self.instructor_share_pct = split['instructor_share_pct']
        self.instructor_level_at_payment = split['instructor_level_at_payment']
        self.platform_fee = split['platform_fee']
        self.teacher_amount = split['teacher_amount']

    def save(self, *args, **kwargs):
        if self.amount and (self.net_financial_basis == Decimal('0.00') or not self.instructor_level_at_payment):
            self.freeze_revenue_split()
        super().save(*args, **kwargs)

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
        self.freeze_revenue_split()
        self.save(update_fields=[
            'status', 'reviewed_by', 'reviewed_at', 'updated_at',
            'net_financial_basis', 'platform_commission_pct', 'instructor_share_pct',
            'instructor_level_at_payment', 'platform_fee', 'teacher_amount'
        ])

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

    @property
    def method_display(self):
        if self.payment_method:
            return self.payment_method.name
        return self.get_method_display()


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


def has_paid_standalone_exam(user, exam):
    """Checks whether the student holds access to the standalone exam (free or approved payment)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False) or user == getattr(exam, 'owner', None) or user == getattr(exam, 'assigned_instructor', None):
        return True
    if getattr(exam, 'is_free', False):
        return True
    return Payment.objects.filter(
        student=user,
        exam=exam,
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


def generate_unique_coupon_code(prefix='THUTA'):
    """Generates an uppercase unique coupon code formatted like THUTA-XXXX-XXXX."""
    import secrets
    token = secrets.token_hex(4).upper()
    return f"{prefix}-{token[:4]}-{token[4:]}"


class Promotion(BaseModel):
    """
    Promotions and Discount Codes created by Admin, Teachers, or Partners.
    """
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage (%)'
        FIXED = 'fixed', 'Fixed Amount (MMK)'

    class CreatorRole(models.TextChoices):
        ADMIN = 'admin', 'Platform Administrator'
        TEACHER = 'teacher', 'Teacher / Instructor'
        PARTNER = 'partner', 'Partner Institution'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, help_text="Internal campaign or promotion name")
    code = models.CharField(
        max_length=64, unique=True, db_index=True,
        help_text="Coupon code applied at checkout (normalized to uppercase)."
    )
    description = models.TextField(blank=True)

    discount_type = models.CharField(
        max_length=16, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Discount value: e.g. 20 for 20% or 10000 for 10,000 MMK. Use 100% for 100% free."
    )

    # Scoping: Blank means platform-wide (Admin only).
    # Teachers and Partners MUST select only their authorized courses.
    courses = models.ManyToManyField(
        'courses.Course', blank=True, related_name='promotions',
        help_text="Specific courses this coupon applies to. Empty applies platform-wide (Admin only)."
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_promotions'
    )
    creator_role = models.CharField(
        max_length=16, choices=CreatorRole.choices, default=CreatorRole.ADMIN
    )
    partner_institution = models.ForeignKey(
        'partner.Institution', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotions',
        help_text="Set if created on behalf of a partner institution."
    )

    start_at = models.DateTimeField(null=True, blank=True, help_text="Promotion start time (null for immediate)")
    end_at = models.DateTimeField(null=True, blank=True, help_text="Promotion expiration time (null for no expiry)")

    usage_limit = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Global maximum usage count across all users (null for unlimited)."
    )
    usage_count = models.PositiveIntegerField(default=0)
    per_user_limit = models.PositiveIntegerField(
        default=1, blank=True,
        help_text="Maximum redemptions allowed per student."
    )

    minimum_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True,
        help_text="Minimum course price required to apply this coupon."
    )
    maximum_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Maximum discount cap for percentage discounts."
    )

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['creator', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        val_str = f"{self.discount_value}%" if self.discount_type == self.DiscountType.PERCENTAGE else f"{self.discount_value:,.0f} MMK"
        return f"{self.code} ({val_str} off) - {self.name}"

    @property
    def is_expired(self):
        now = timezone.now()
        if self.end_at and now > self.end_at:
            return True
        return False

    @property
    def is_scheduled(self):
        now = timezone.now()
        if self.start_at and now < self.start_at:
            return True
        return False

    @property
    def is_limit_reached(self):
        if self.usage_limit is not None and self.usage_count >= self.usage_limit:
            return True
        return False

    @property
    def computed_status(self):
        if not self.is_active:
            return 'disabled'
        if self.is_scheduled:
            return 'scheduled'
        if self.is_expired:
            return 'expired'
        if self.is_limit_reached:
            return 'limit_reached'
        return 'active'

    @property
    def is_valid_now(self):
        return self.computed_status == 'active'

    def validate_for_course_and_user(self, course, user=None):
        """
        Validates whether this coupon can be applied to `course` by `user`.
        Returns (is_valid: bool, error_message: str).
        """
        if not self.is_active:
            return False, "This coupon code is currently disabled."

        now = timezone.now()
        if self.start_at and now < self.start_at:
            return False, f"This coupon is scheduled to start on {self.start_at.strftime('%Y-%m-%d %H:%M')}."

        if self.end_at and now > self.end_at:
            return False, "This coupon code has expired."

        if self.usage_limit is not None and self.usage_count >= self.usage_limit:
            return False, "This coupon code has reached its maximum total usage limit."

        # Check course scoping
        if self.courses.exists():
            if not self.courses.filter(id=course.id).exists():
                return False, f"This coupon is not valid for '{course.title}'."

        # Check minimum purchase
        course_price = getattr(course, 'price', Decimal('0.00')) or Decimal('0.00')
        if self.minimum_purchase > 0 and course_price < self.minimum_purchase:
            return False, f"This coupon requires a minimum course price of {self.minimum_purchase:,.0f} MMK."

        # Check per-user limit
        if user and getattr(user, 'is_authenticated', False):
            user_usages = self.usages.filter(user=user).count()
            if user_usages >= self.per_user_limit:
                return False, f"You have already redeemed this coupon the maximum allowed times ({self.per_user_limit})."

        return True, ""

    def calculate_discount(self, original_price: Decimal):
        """
        Calculates (discount_amount, final_price) given original_price.
        Final price will never be negative.
        """
        orig = Decimal(str(original_price))
        if orig <= Decimal('0.00'):
            return Decimal('0.00'), Decimal('0.00')

        if self.discount_type == self.DiscountType.PERCENTAGE:
            pct = Decimal(str(self.discount_value))
            if pct >= Decimal('100.00'):
                discount = orig
            elif pct <= Decimal('0.00'):
                discount = Decimal('0.00')
            else:
                discount = (orig * (pct / Decimal('100.00'))).quantize(Decimal('0.01'))
            
            # Apply maximum discount cap if configured
            if self.maximum_discount is not None and self.maximum_discount > Decimal('0.00'):
                discount = min(discount, self.maximum_discount)
        else:
            # Fixed discount
            discount = Decimal(str(self.discount_value))

        # Ensure discount does not exceed original price
        discount = min(discount, orig)
        discount = max(discount, Decimal('0.00')).quantize(Decimal('0.01'))
        final_price = max(orig - discount, Decimal('0.00')).quantize(Decimal('0.01'))
        return discount, final_price


class PromotionUsage(BaseModel):
    """
    Audit log of each coupon redemption by a student.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='promotion_usages')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='promotion_usages')
    payment = models.ForeignKey('billing.Payment', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotion_usages')

    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['promotion', 'user']),
            models.Index(fields=['course', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} used {self.promotion.code} for {self.course.title} (-{self.discount_amount} MMK)"


