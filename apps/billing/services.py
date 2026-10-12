"""
Centralized Billing, Payment, Subscription, and Partner Revenue Services.
Enforces server-side security, provider abstraction, dynamic revenue sharing,
invoice generation, and full transaction auditing.
"""
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.models import (
    Payment, UserSubscription, SubscriptionPlan,
    PartnerRevenueRecord, Invoice, active_payment_for, active_subscription_for,
    commission_rate,
)
from apps.billing.providers.base import PaymentRequest, PaymentResponse
from apps.billing.providers.registry import get_payment_provider
from apps.courses.models import Course, Enrollment


def calculate_partner_revenue(course: Course, gross_amount: Decimal) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """
    Computes (partner_amount, platform_amount, partner_pct, platform_pct).
    Configurable: reads from course.partner_revenue_share_pct (default 75.00)
    or settings.PARTNER_DEFAULT_REVENUE_SHARE_PCT. Never hardcoded.
    """
    gross = Decimal(str(gross_amount))
    default_pct = getattr(settings, 'PARTNER_DEFAULT_REVENUE_SHARE_PCT', 75.0)
    partner_pct = Decimal(str(getattr(course, 'partner_revenue_share_pct', None) or default_pct))
    platform_pct = Decimal('100.00') - partner_pct

    partner_amount = (gross * (partner_pct / Decimal('100.00'))).quantize(Decimal('0.01'))
    platform_amount = gross - partner_amount
    return partner_amount, platform_amount, partner_pct, platform_pct


def create_or_get_invoice(payment: Payment) -> Invoice:
    """
    Idempotently mints or updates an official Invoice for an approved/successful payment.
    """
    if hasattr(payment, 'invoice') and payment.invoice:
        return payment.invoice

    if payment.payment_type == Payment.PaymentType.EXAM_VOUCHER:
        item_title = f"Proctored Exam Voucher - {payment.course.title if payment.course else 'Certification'}"
    elif payment.payment_type == Payment.PaymentType.CERTIFICATE_FEE:
        item_title = f"Official Certificate Fee - {payment.course.title if payment.course else 'Credential'}"
    elif payment.plan or payment.payment_type == Payment.PaymentType.SUBSCRIPTION:
        item_title = f"Membership: {payment.plan.name if payment.plan else 'Subscription'} Plan ({payment.billing_period.capitalize()})"
    elif payment.course:
        item_title = f"Course: {payment.course.title}"
    else:
        item_title = payment.get_payment_type_display()

    inv_status = Invoice.Status.PAID if payment.is_successful else Invoice.Status.ISSUED
    paid_at = payment.reviewed_at if payment.is_successful else None

    invoice = Invoice.objects.create(
        invoice_number=Invoice.generate_invoice_number(),
        payment=payment,
        student=payment.student,
        item_title=item_title,
        amount=payment.amount,
        currency=payment.currency,
        status=inv_status,
        billing_name=payment.student.get_full_name() or payment.student.username,
        billing_email=payment.student.email or '',
        issue_date=timezone.localdate(),
        paid_at=paid_at,
        notes=payment.note or '',
    )
    return invoice


@transaction.atomic
def fulfill_payment(payment: Payment) -> bool:
    """
    Fulfills educational entitlements once a payment is marked SUCCESS or APPROVED:
    - Enrolls student into course
    - Creates auditable PartnerRevenueRecord if course belongs to an institution
    - Activates / renews student UserSubscription
    - Emits official Invoice
    """
    # Normalize payment_type if needed
    if payment.plan and payment.payment_type != Payment.PaymentType.SUBSCRIPTION:
        payment.payment_type = Payment.PaymentType.SUBSCRIPTION
        payment.save(update_fields=['payment_type'])
    elif payment.course and payment.payment_type not in [
        Payment.PaymentType.COURSE_PURCHASE,
        Payment.PaymentType.EXAM_VOUCHER,
        Payment.PaymentType.CERTIFICATE_FEE,
    ]:
        payment.payment_type = Payment.PaymentType.COURSE_PURCHASE
        payment.save(update_fields=['payment_type'])

    # 1. Course Purchase fulfillment
    if payment.payment_type == Payment.PaymentType.COURSE_PURCHASE and payment.course:
        course = payment.course
        student = payment.student

        # Determine period_end for monthly courses
        if course.billing_period == Course.BillingPeriod.MONTHLY:
            start = payment.period_start or timezone.localdate()
            try:
                period_end = start.replace(month=start.month % 12 + 1) if start.month != 12 else start.replace(year=start.year + 1, month=1)
            except ValueError:
                period_end = start.replace(month=start.month + 1, day=28)
            payment.period_end = period_end
            payment.save(update_fields=['period_end'])

        # Activate enrollment
        enrollment, _ = Enrollment.objects.get_or_create(
            course=course,
            student=student,
            defaults={
                'status': Enrollment.Status.ACTIVE,
                'source': Enrollment.Source.PAID,
                'partner_institution': course.partner_institution,
            }
        )
        if enrollment.status != Enrollment.Status.ACTIVE:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save(update_fields=['status'])

        # Audit partner revenue if partner course
        if course.partner_institution:
            partner_amt, plat_amt, partner_pct, plat_pct = calculate_partner_revenue(course, payment.amount)
            PartnerRevenueRecord.objects.get_or_create(
                payment=payment,
                defaults={
                    'partner_institution': course.partner_institution,
                    'course': course,
                    'gross_amount': payment.amount,
                    'partner_share_pct': partner_pct,
                    'platform_share_pct': plat_pct,
                    'partner_amount': partner_amt,
                    'platform_amount': plat_amt,
                    'status': PartnerRevenueRecord.Status.PENDING,
                }
            )

    # 2. Subscription fulfillment
    elif payment.payment_type == Payment.PaymentType.SUBSCRIPTION and payment.plan:
        plan = payment.plan
        student = payment.student
        start = payment.period_start or timezone.localdate()

        if payment.billing_period == UserSubscription.BillingCycle.YEARLY:
            end_date = start + timezone.timedelta(days=365)
        else:
            end_date = start + timezone.timedelta(days=30)

        payment.period_end = end_date
        payment.save(update_fields=['period_end'])

        # Deactivate previous subscriptions and activate current tier
        UserSubscription.objects.filter(user=student, is_active=True).update(is_active=False)
        UserSubscription.objects.create(
            user=student,
            plan=plan,
            billing_cycle=payment.billing_period,
            start_date=start,
            end_date=end_date,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            payment_reference=payment.reference or '',
        )

    # 3. Exam Voucher & Certificate Fee fulfillment
    elif payment.payment_type in [Payment.PaymentType.EXAM_VOUCHER, Payment.PaymentType.CERTIFICATE_FEE] and payment.course:
        course = payment.course
        if course.partner_institution:
            partner_amt, plat_amt, partner_pct, plat_pct = calculate_partner_revenue(course, payment.amount)
            PartnerRevenueRecord.objects.get_or_create(
                payment=payment,
                defaults={
                    'partner_institution': course.partner_institution,
                    'course': course,
                    'gross_amount': payment.amount,
                    'partner_share_pct': partner_pct,
                    'platform_share_pct': plat_pct,
                    'partner_amount': partner_amt,
                    'platform_amount': plat_amt,
                    'status': PartnerRevenueRecord.Status.PENDING,
                }
            )

    # 4. Generate official invoice
    create_or_get_invoice(payment)
    return True


@transaction.atomic
def process_refund(payment: Payment, amount: Optional[Decimal] = None, reason: str = '', user: Optional[Any] = None) -> bool:
    """
    Executes a validated server-side refund:
    - Enforces that only successful/approved payments can be refunded.
    - Prevents double-refunding.
    - Revokes course enrollment or subscription.
    - Reverses partner revenue ledger.
    - Updates invoice status to REFUNDED.
    """
    if payment.status == Payment.Status.REFUNDED:
        raise ValidationError("Payment has already been refunded.")

    if not payment.is_successful:
        raise ValidationError("Only successfully settled payments can be refunded.")

    refund_amt = Decimal(str(amount)) if amount is not None else payment.amount
    if refund_amt <= Decimal('0.00') or refund_amt > payment.amount:
        raise ValidationError(f"Invalid refund amount: {refund_amt}. Must be between 0 and {payment.amount}.")

    # Notify provider
    provider = get_payment_provider(payment.provider)
    refund_res = provider.process_refund(payment, amount=refund_amt, reason=reason)

    payment.status = Payment.Status.REFUNDED
    payment.refunded_amount = refund_amt
    payment.refund_reason = reason
    payment.refunded_at = timezone.now()
    payment.save(update_fields=['status', 'refunded_amount', 'refund_reason', 'refunded_at'])

    # Reversal: Course purchase, Exam Voucher, Certificate Fee
    if payment.payment_type in [Payment.PaymentType.COURSE_PURCHASE, Payment.PaymentType.EXAM_VOUCHER, Payment.PaymentType.CERTIFICATE_FEE] and payment.course:
        if payment.payment_type == Payment.PaymentType.COURSE_PURCHASE:
            Enrollment.objects.filter(
                course=payment.course, student=payment.student, status=Enrollment.Status.ACTIVE
            ).update(status=Enrollment.Status.DROPPED)

        # Reverse partner revenue ledger
        PartnerRevenueRecord.objects.filter(payment=payment).update(
            status=PartnerRevenueRecord.Status.REFUNDED,
            refunded_amount=refund_amt,
        )

    # Reversal: Subscription
    elif payment.payment_type == Payment.PaymentType.SUBSCRIPTION:
        UserSubscription.objects.filter(
            user=payment.student, plan=payment.plan, is_active=True
        ).update(is_active=False, status=UserSubscription.Status.CANCELLED)

    # Reversal: Invoice
    if hasattr(payment, 'invoice') and payment.invoice:
        payment.invoice.status = Invoice.Status.REFUNDED
        payment.invoice.save(update_fields=['status'])

    return True


def create_course_payment(
    student,
    course: Course,
    method: str = Payment.Method.KBZ_PAY,
    reference: str = '',
    receipt=None,
    note: str = '',
    provider_code: str = 'manual_transfer',
) -> Tuple[Payment, PaymentResponse]:
    """
    Creates and processes a Course Payment with strict server-side price calculation.
    Never trusts client-submitted amounts.
    """
    if not student or not getattr(student, 'is_authenticated', False):
        raise PermissionDenied("Authentication required.")

    # Prevent duplicate active enrollment
    if Enrollment.objects.filter(course=course, student=student, status=Enrollment.Status.ACTIVE).exists():
        raise ValidationError("Student is already actively enrolled in this course.")

    # Prevent duplicate pending payment
    if Payment.objects.filter(student=student, course=course, status=Payment.Status.PENDING).exists():
        raise ValidationError("A payment for this course is already awaiting administrative review.")

    # Server-side pricing calculation (Zero trust on client-submitted prices)
    pricing = course.calculate_price_for_user(student)
    final_amount = pricing['final_price']

    if pricing['is_free']:
        raise ValidationError("Course is free or covered by active membership. Enrol directly.")

    # Calculate split (Platform fee / Instructor or Partner amount)
    split_info = Payment.calculate_level_split(final_amount, course=course)
    platform_fee = split_info['platform_fee']
    teacher_amount = split_info['teacher_amount']

    payment = Payment(
        student=student,
        course=course,
        plan=None,
        payment_type=Payment.PaymentType.COURSE_PURCHASE,
        provider=provider_code,
        amount=final_amount,
        currency=course.currency,
        billing_period=course.billing_period,
        platform_fee=platform_fee,
        teacher_amount=teacher_amount,
        platform_commission_pct=split_info['platform_commission_pct'],
        instructor_share_pct=split_info['instructor_share_pct'],
        instructor_level_at_payment=split_info['instructor_level_at_payment'],
        net_financial_basis=final_amount,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
        status=Payment.Status.PENDING,
    )

    # Dispatch to provider abstraction
    provider = get_payment_provider(provider_code)
    req = PaymentRequest(
        student=student,
        amount=final_amount,
        currency=course.currency,
        payment_type=Payment.PaymentType.COURSE_PURCHASE,
        course=course,
        billing_period=course.billing_period,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
    )
    res = provider.process_payment(req)

    # Reflect provider outcome
    if res.status == 'success':
        payment.status = Payment.Status.SUCCESS
        payment.period_start = timezone.localdate()
        payment.reviewed_at = timezone.now()
        payment.save()
        fulfill_payment(payment)
    elif res.status == 'failed':
        payment.status = Payment.Status.FAILED
        payment.rejection_reason = res.message
        payment.save()
    elif res.status == 'processing':
        payment.status = Payment.Status.PROCESSING
        payment.save()
    else:
        payment.status = Payment.Status.PENDING
        payment.save()

    return payment, res


def create_subscription_payment(
    student,
    plan: SubscriptionPlan,
    billing_cycle: str = UserSubscription.BillingCycle.MONTHLY,
    method: str = Payment.Method.KBZ_PAY,
    reference: str = '',
    receipt=None,
    note: str = '',
    provider_code: str = 'manual_transfer',
) -> Tuple[Payment, PaymentResponse]:
    """
    Creates and processes a Membership Subscription payment with server-side price calculation.
    """
    if not student or not getattr(student, 'is_authenticated', False):
        raise PermissionDenied("Authentication required.")

    if plan.plan_type == SubscriptionPlan.PlanType.STARTER:
        raise ValidationError("Starter plan is free. Activate instantly without payment.")

    # Prevent duplicate pending payment
    if Payment.objects.filter(student=student, plan=plan, status=Payment.Status.PENDING).exists():
        raise ValidationError("A subscription payment for this plan is already awaiting review.")

    # Server-side pricing calculation
    if billing_cycle == UserSubscription.BillingCycle.YEARLY:
        amount = plan.yearly_price
    else:
        amount = plan.monthly_price

    payment = Payment(
        student=student,
        course=None,
        plan=plan,
        payment_type=Payment.PaymentType.SUBSCRIPTION,
        provider=provider_code,
        amount=amount,
        currency=plan.currency,
        billing_period=billing_cycle,
        platform_fee=amount,  # 100% platform membership revenue
        teacher_amount=Decimal('0.00'),
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
        status=Payment.Status.PENDING,
    )

    provider = get_payment_provider(provider_code)
    req = PaymentRequest(
        student=student,
        amount=amount,
        currency=plan.currency,
        payment_type=Payment.PaymentType.SUBSCRIPTION,
        plan=plan,
        billing_period=billing_cycle,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
    )
    res = provider.process_payment(req)

    if res.status == 'success':
        payment.status = Payment.Status.SUCCESS
        payment.period_start = timezone.localdate()
        payment.reviewed_at = timezone.now()
        payment.save()
        fulfill_payment(payment)
    elif res.status == 'failed':
        payment.status = Payment.Status.FAILED
        payment.rejection_reason = res.message
        payment.save()
    elif res.status == 'processing':
        payment.status = Payment.Status.PROCESSING
        payment.save()
    else:
        payment.status = Payment.Status.PENDING
        payment.save()

    return payment, res


def get_partner_revenue_summary(institution) -> Dict[str, Any]:
    """
    Computes comprehensive revenue metrics for a specific educational partner institution:
    - Sales count
    - Enrollments count
    - Gross revenue
    - MEL platform share
    - Partner share
    - Total refunds
    - Outstanding balance (settleable balance)
    """
    records = PartnerRevenueRecord.objects.filter(partner_institution=institution)
    
    total_sales = records.count()
    settled_records = records.filter(status=PartnerRevenueRecord.Status.SETTLED)
    pending_records = records.filter(status=PartnerRevenueRecord.Status.PENDING)
    refunded_records = records.filter(status=PartnerRevenueRecord.Status.REFUNDED)

    gross_revenue = sum((r.gross_amount for r in records), start=Decimal('0.00'))
    partner_share_total = sum((r.partner_amount for r in records), start=Decimal('0.00'))
    mel_share_total = sum((r.platform_amount for r in records), start=Decimal('0.00'))
    total_refunds = sum((r.refunded_amount for r in records), start=Decimal('0.00'))

    # Net partner earnings pending settlement
    outstanding_balance = sum((r.partner_amount for r in pending_records), start=Decimal('0.00'))

    # Total student enrollments in partner courses
    total_enrollments = Enrollment.objects.filter(
        course__partner_institution=institution
    ).count()

    return {
        'institution': institution,
        'total_sales': total_sales,
        'total_enrollments': total_enrollments,
        'gross_revenue': gross_revenue,
        'partner_share': partner_share_total,
        'mel_share': mel_share_total,
        'total_refunds': total_refunds,
        'outstanding_balance': outstanding_balance,
        'pending_count': pending_records.count(),
        'settled_count': settled_records.count(),
        'refunded_count': refunded_records.count(),
        'records': records.select_related('course', 'payment', 'payment__student'),
    }


def get_platform_revenue_summary() -> Dict[str, Any]:
    """
    Platform-wide aggregate revenue analytics for administrators.
    """
    approved_payments = Payment.objects.filter(
        status__in=[Payment.Status.APPROVED, Payment.Status.SUCCESS]
    )
    refunded_payments = Payment.objects.filter(status=Payment.Status.REFUNDED)

    total_gross = sum((p.amount for p in approved_payments), start=Decimal('0.00'))
    total_platform_fees = sum((p.platform_fee for p in approved_payments), start=Decimal('0.00'))
    total_teacher_shares = sum((p.teacher_amount for p in approved_payments), start=Decimal('0.00'))
    total_refunds = sum((p.refunded_amount or p.amount for p in refunded_payments), start=Decimal('0.00'))

    # Partner shares
    partner_records = PartnerRevenueRecord.objects.all()
    total_partner_shares = sum((r.partner_amount for r in partner_records), start=Decimal('0.00'))

    # Breakdown by payment type
    course_sales = sum((p.amount for p in approved_payments if p.payment_type == Payment.PaymentType.COURSE_PURCHASE), start=Decimal('0.00'))
    subscription_sales = sum((p.amount for p in approved_payments if p.payment_type == Payment.PaymentType.SUBSCRIPTION), start=Decimal('0.00'))
    exam_voucher_sales = sum((p.amount for p in approved_payments if p.payment_type == Payment.PaymentType.EXAM_VOUCHER), start=Decimal('0.00'))
    certificate_fee_sales = sum((p.amount for p in approved_payments if p.payment_type == Payment.PaymentType.CERTIFICATE_FEE), start=Decimal('0.00'))

    return {
        'total_gross': total_gross,
        'total_platform_fees': total_platform_fees,
        'total_teacher_shares': total_teacher_shares,
        'total_partner_shares': total_partner_shares,
        'total_refunds': total_refunds,
        'course_sales': course_sales,
        'subscription_sales': subscription_sales,
        'exam_voucher_sales': exam_voucher_sales,
        'certificate_fee_sales': certificate_fee_sales,
        'total_transactions': approved_payments.count(),
        'refunded_transactions': refunded_payments.count(),
    }


def create_exam_voucher_payment(
    student,
    course: Course,
    method: str = Payment.Method.KBZ_PAY,
    reference: str = '',
    receipt=None,
    note: str = '',
    provider_code: str = 'manual_transfer',
) -> Tuple[Payment, PaymentResponse]:
    """
    Creates and processes an Exam Voucher payment for a proctored examination.
    """
    if not student or not getattr(student, 'is_authenticated', False):
        raise PermissionDenied("Authentication required.")

    amount = getattr(course, 'exam_voucher_price', None)
    if amount is None or amount <= Decimal('0.00'):
        raise ValidationError("This course does not require a paid exam voucher.")

    # Prevent duplicate pending payment
    if Payment.objects.filter(
        student=student, course=course, payment_type=Payment.PaymentType.EXAM_VOUCHER, status=Payment.Status.PENDING
    ).exists():
        raise ValidationError("An exam voucher payment for this course is already awaiting administrative review.")

    platform_fee, teacher_amount = Payment.split(amount)

    payment = Payment(
        student=student,
        course=course,
        plan=None,
        payment_type=Payment.PaymentType.EXAM_VOUCHER,
        provider=provider_code,
        amount=amount,
        currency=course.currency,
        billing_period='one_time',
        platform_fee=platform_fee,
        teacher_amount=teacher_amount,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
        status=Payment.Status.PENDING,
    )

    provider = get_payment_provider(provider_code)
    req = PaymentRequest(
        student=student,
        amount=amount,
        currency=course.currency,
        payment_type=Payment.PaymentType.EXAM_VOUCHER,
        course=course,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
    )
    res = provider.process_payment(req)

    if res.status == 'success':
        payment.status = Payment.Status.SUCCESS
        payment.reviewed_at = timezone.now()
        payment.save()
        fulfill_payment(payment)
    elif res.status == 'failed':
        payment.status = Payment.Status.FAILED
        payment.rejection_reason = res.message
        payment.save()
    elif res.status == 'processing':
        payment.status = Payment.Status.PROCESSING
        payment.save()
    else:
        payment.status = Payment.Status.PENDING
        payment.save()

    return payment, res


def create_certificate_fee_payment(
    student,
    course: Course,
    method: str = Payment.Method.KBZ_PAY,
    reference: str = '',
    receipt=None,
    note: str = '',
    provider_code: str = 'manual_transfer',
) -> Tuple[Payment, PaymentResponse]:
    """
    Creates and processes an Official Certificate Fee payment.
    """
    if not student or not getattr(student, 'is_authenticated', False):
        raise PermissionDenied("Authentication required.")

    amount = getattr(course, 'certificate_fee', None)
    if amount is None or amount <= Decimal('0.00'):
        raise ValidationError("This course does not require an additional certificate fee.")

    # Prevent duplicate pending payment
    if Payment.objects.filter(
        student=student, course=course, payment_type=Payment.PaymentType.CERTIFICATE_FEE, status=Payment.Status.PENDING
    ).exists():
        raise ValidationError("A certificate fee payment for this course is already awaiting administrative review.")

    platform_fee, teacher_amount = Payment.split(amount)

    payment = Payment(
        student=student,
        course=course,
        plan=None,
        payment_type=Payment.PaymentType.CERTIFICATE_FEE,
        provider=provider_code,
        amount=amount,
        currency=course.currency,
        billing_period='one_time',
        platform_fee=platform_fee,
        teacher_amount=teacher_amount,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
        status=Payment.Status.PENDING,
    )

    provider = get_payment_provider(provider_code)
    req = PaymentRequest(
        student=student,
        amount=amount,
        currency=course.currency,
        payment_type=Payment.PaymentType.CERTIFICATE_FEE,
        course=course,
        method=method,
        reference=reference,
        receipt=receipt,
        note=note,
    )
    res = provider.process_payment(req)

    if res.status == 'success':
        payment.status = Payment.Status.SUCCESS
        payment.reviewed_at = timezone.now()
        payment.save()
        fulfill_payment(payment)
    elif res.status == 'failed':
        payment.status = Payment.Status.FAILED
        payment.rejection_reason = res.message
        payment.save()
    elif res.status == 'processing':
        payment.status = Payment.Status.PROCESSING
        payment.save()
    else:
        payment.status = Payment.Status.PENDING
        payment.save()

    return payment, res


@transaction.atomic
def cancel_subscription(user, reason: str = '') -> Optional[UserSubscription]:
    """Cancels user's currently active subscription."""
    sub = active_subscription_for(user)
    if sub:
        sub.cancel(reason=reason)
        return sub
    return None


@transaction.atomic
def renew_subscription(user, billing_cycle: Optional[str] = None) -> Optional[UserSubscription]:
    """Renews user's currently active subscription."""
    sub = active_subscription_for(user)
    if sub:
        sub.renew(billing_cycle=billing_cycle)
        return sub
    return None


@transaction.atomic
def expire_subscription(user) -> Optional[UserSubscription]:
    """Marks user's active subscription as expired."""
    sub = active_subscription_for(user)
    if sub:
        sub.expire()
        return sub
    return None


@transaction.atomic
def upgrade_subscription(
    user, new_plan: SubscriptionPlan, billing_cycle: Optional[str] = None, payment_reference: str = ''
) -> UserSubscription:
    """Upgrades user's membership tier."""
    sub = active_subscription_for(user)
    if sub:
        return sub.upgrade(new_plan, billing_cycle=billing_cycle, payment_reference=payment_reference)
    cycle = billing_cycle or UserSubscription.BillingCycle.MONTHLY
    days = 365 if cycle == UserSubscription.BillingCycle.YEARLY else 30
    now_date = timezone.localdate()
    return UserSubscription.objects.create(
        user=user,
        plan=new_plan,
        billing_cycle=cycle,
        start_date=now_date,
        end_date=now_date + timezone.timedelta(days=days),
        is_active=True,
        status=UserSubscription.Status.ACTIVE,
        payment_reference=payment_reference,
    )


@transaction.atomic
def downgrade_subscription(
    user, new_plan: SubscriptionPlan, billing_cycle: Optional[str] = None, payment_reference: str = ''
) -> UserSubscription:
    """Downgrades user's membership tier."""
    sub = active_subscription_for(user)
    if sub:
        return sub.downgrade(new_plan, billing_cycle=billing_cycle, payment_reference=payment_reference)
    cycle = billing_cycle or (
        UserSubscription.BillingCycle.LIFETIME if new_plan.plan_type == SubscriptionPlan.PlanType.STARTER else UserSubscription.BillingCycle.MONTHLY
    )
    now_date = timezone.localdate()
    end_date = None if new_plan.plan_type == SubscriptionPlan.PlanType.STARTER or cycle == UserSubscription.BillingCycle.LIFETIME else now_date + timezone.timedelta(days=30)
    return UserSubscription.objects.create(
        user=user,
        plan=new_plan,
        billing_cycle=cycle,
        start_date=now_date,
        end_date=end_date,
        is_active=True,
        status=UserSubscription.Status.ACTIVE,
        payment_reference=payment_reference,
    )


@transaction.atomic
def settle_partner_revenue_record(record: PartnerRevenueRecord, settled_by: Optional[Any] = None) -> PartnerRevenueRecord:
    """Marks a single pending partner revenue record as settled."""
    if record.status == PartnerRevenueRecord.Status.REFUNDED:
        raise ValidationError("Cannot settle a refunded partner revenue record.")
    record.status = PartnerRevenueRecord.Status.SETTLED
    record.settled_at = timezone.now()
    record.save(update_fields=['status', 'settled_at', 'updated_at'])
    return record


@transaction.atomic
def settle_partner_records_for_institution(institution, settled_by: Optional[Any] = None) -> int:
    """Batch settles all pending partner revenue records for an institution."""
    now_ts = timezone.now()
    return PartnerRevenueRecord.objects.filter(
        partner_institution=institution,
        status=PartnerRevenueRecord.Status.PENDING,
    ).update(
        status=PartnerRevenueRecord.Status.SETTLED,
        settled_at=now_ts,
    )

