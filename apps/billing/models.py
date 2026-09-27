from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.courses.models import Course


def commission_rate():
    """Platform share of every approved payment (default 25 %)."""
    return getattr(settings, 'PAYMENT_PLATFORM_COMMISSION_RATE', 0.25)


class Payment(BaseModel):
    """
    A manual payment submitted by a student (KBZ Pay / Wave Pay / bank transfer)
    and reviewed by an administrator.

    Approval activates the student's enrolment on the course; rejection sends
    them back to checkout. The revenue split is frozen at submission time so a
    later commission change never rewrites history.
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
        Course, on_delete=models.PROTECT, related_name='payments'
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
        ]

    def __str__(self):
        return f'{self.amount} {self.currency} - {self.student.username} / {self.course.title}'

    @classmethod
    def split(cls, amount):
        """Return ``(platform_fee, teacher_amount)`` for a gross amount."""
        from decimal import Decimal
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
        return self.period_end >= timezone.now().date()


def active_payment_for(user, course):
    """The approved, unexpired payment that unlocks ``course`` for ``user``."""
    return (
        Payment.objects.filter(student=user, course=course, status=Payment.Status.APPROVED)
        .order_by('-created_at')
        .first()
    )
