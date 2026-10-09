from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Sum, F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View, ListView, CreateView, UpdateView, DetailView

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import RoleRequiredMixin
from apps.courses.models import Course, Enrollment
from .forms import (
    PaymentDecisionForm, PaymentSubmitForm, SubscriptionSubmitForm,
    PaymentMethodForm, PromotionForm,
)
from .models import (
    Payment, PaymentMethod, Promotion, PromotionUsage, SubscriptionPlan, UserSubscription, Invoice,
    active_payment_for, active_subscription_for
)
from .serializers import (
    SubscriptionPlanSerializer, UserSubscriptionSerializer, SubscriptionCheckoutSerializer
)


class AdminRequiredMixin(RoleRequiredMixin):
    """Restricts a view to ADMIN accounts (administrators always pass)."""
    allowed_roles = ['admin']


def _next_period_end(course, start):
    """Month-long window for monthly billing, None for one-time access."""
    if not course or course.billing_period != Course.BillingPeriod.MONTHLY:
        return None
    try:
        return start.replace(month=start.month % 12 + 1) if start.month != 12 else start.replace(
            year=start.year + 1, month=1
        )
    except ValueError:
        # e.g. 31 January -> 28/29 February
        if start.month == 12:
            return start.replace(year=start.year + 1, month=1, day=1)
        return start.replace(month=start.month + 1, day=28)


class PricingView(TemplateView):
    """
    Public / Student pricing matrix showcasing Starter, Standard (5,000 MMK),
    and Premium (15,000 MMK) tiers.
    """
    template_name = 'billing/pricing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        SubscriptionPlan.ensure_default_plans()
        PaymentMethod.ensure_default_methods()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
        context['plans'] = plans
        plans_by_type = {p.plan_type: p for p in plans}
        context['starter_plan'] = plans_by_type.get('starter')
        context['standard_plan'] = plans_by_type.get('standard')
        context['premium_plan'] = plans_by_type.get('premium')
        context['payment_methods'] = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        if self.request.user.is_authenticated:
            context['current_subscription'] = active_subscription_for(self.request.user)
        return context


class SubscribeView(LoginRequiredMixin, View):
    """
    Student subscription checkout page.
    - Free Starter tier activates instantly.
    - Paid tiers (Standard / Premium) allow choosing Monthly or Annual billing,
      and prompt for KBZ Pay / Wave Pay / Bank receipt upload.
    """
    template_name = 'billing/subscribe.html'

    def get_plan(self):
        plan_type = self.kwargs.get('plan_type')
        SubscriptionPlan.ensure_default_plans()
        PaymentMethod.ensure_default_methods()
        return get_object_or_404(SubscriptionPlan, plan_type=plan_type, is_active=True)

    def get(self, request, plan_type, *args, **kwargs):
        plan = self.get_plan()
        if plan.plan_type == SubscriptionPlan.PlanType.STARTER:
            # Free tier: instant activation
            UserSubscription.objects.filter(user=request.user, is_active=True).update(is_active=False)
            UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                billing_cycle=UserSubscription.BillingCycle.LIFETIME,
                start_date=timezone.localdate(),
                end_date=None,
                is_active=True,
            )
            messages.success(request, f'Welcome to the {plan.name} Membership! Start exploring courses.')
            return redirect('pricing')

        # Check existing active subscription or pending payment
        current_sub = active_subscription_for(request.user)
        pending_payment = Payment.objects.filter(
            student=request.user, plan=plan, status=Payment.Status.PENDING
        ).first()

        form = SubscriptionSubmitForm()
        payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        return render(request, self.template_name, {
            'plan': plan,
            'form': form,
            'current_subscription': current_sub,
            'pending_payment': pending_payment,
            'payment_methods': payment_methods,
        })

    def post(self, request, plan_type, *args, **kwargs):
        plan = self.get_plan()
        if plan.plan_type == SubscriptionPlan.PlanType.STARTER:
            return redirect('pricing')

        existing_pending = Payment.objects.filter(
            student=request.user, plan=plan, status=Payment.Status.PENDING
        ).first()
        if existing_pending:
            messages.info(request, 'Your subscription payment is already awaiting admin review.')
            return redirect('pricing')

        form = SubscriptionSubmitForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Please correct the errors in the form.')
            return render(request, self.template_name, {
                'plan': plan,
                'form': form,
                'current_subscription': active_subscription_for(request.user),
                'payment_methods': PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name'),
            })

        cycle = form.cleaned_data['billing_cycle']
        amount = plan.yearly_price if cycle == UserSubscription.BillingCycle.YEARLY else plan.monthly_price

        payment = form.save(commit=False)
        payment.student = request.user
        payment.plan = plan
        payment.course = None
        payment.amount = amount
        payment.currency = plan.currency
        payment.billing_period = cycle
        payment.platform_fee = amount  # 100% platform revenue for generic platform subscription
        payment.teacher_amount = Decimal('0.00')
        pm = PaymentMethod.objects.filter(code=payment.method, is_active=True).first()
        if pm:
            payment.payment_method = pm
        payment.status = Payment.Status.PENDING
        payment.save()

        messages.success(
            request,
            f'Payment of {amount:,.0f} {plan.currency} for {plan.name} membership ({cycle.capitalize()}) '
            f'submitted! An administrator will review and activate your subscription shortly.'
        )
        return redirect('pricing')


class MySubscriptionView(LoginRequiredMixin, TemplateView):
    """Displays the student's active subscription tier, features, and billing history."""
    template_name = 'billing/my_subscription.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['subscription'] = active_subscription_for(user)
        context['subscription_history'] = UserSubscription.objects.filter(
            user=user
        ).select_related('plan').order_by('-created_at')
        context['payments'] = Payment.objects.filter(
            student=user, plan__isnull=False
        ).select_related('plan').order_by('-created_at')
        return context


class CheckoutView(LoginRequiredMixin, View):
    """
    Collect proof of payment for a paid course, supporting dynamic coupons,
    promotions, payment methods, and instant enrollment for 100% free discounts.
    """
    template_name = 'billing/checkout.html'

    def get_course(self):
        return get_object_or_404(Course, slug=self.kwargs['slug'], is_published=True)

    def _get_coupon_info(self, request, course, base_price, code):
        """Validates coupon code and returns (promo, error_msg, discount_amount, final_price)."""
        if not code:
            return None, None, Decimal('0.00'), base_price

        code = code.strip().upper()
        promo = Promotion.objects.filter(code__iexact=code).first()
        if not promo:
            return None, f"Coupon code '{code}' is not valid.", Decimal('0.00'), base_price

        is_valid, err_msg = promo.validate_for_course_and_user(course, request.user)
        if not is_valid:
            return promo, err_msg, Decimal('0.00'), base_price

        discount_amount, final_price = promo.calculate_discount(base_price)
        return promo, None, discount_amount, final_price

    def _render(self, request, course, form=None, coupon_code='', coupon_error=None,
                promo=None, discount_amount=Decimal('0.00'), final_price=None, status=200):
        pricing = course.calculate_price_for_user(request.user)
        base_price = pricing['final_price']
        if final_price is None:
            final_price = base_price

        PaymentMethod.ensure_default_methods()
        payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')

        return render(request, self.template_name, {
            'course': course,
            'pricing': pricing,
            'base_price': base_price,
            'effective_price': final_price,
            'form': form or PaymentSubmitForm(),
            'currency': course.currency,
            'coupon_code': coupon_code,
            'coupon_error': coupon_error,
            'promotion': promo,
            'discount_amount': discount_amount,
            'is_free_with_coupon': (final_price <= Decimal('0.00')),
            'payment_methods': payment_methods,
            'pending': Payment.objects.filter(
                student=request.user, course=course,
                status=Payment.Status.PENDING,
            ).first(),
            'existing': active_payment_for(request.user, course),
        }, status=status)

    def get(self, request, *args, **kwargs):
        course = self.get_course()
        pricing = course.calculate_price_for_user(request.user)
        if pricing['is_free']:
            messages.info(request, pricing.get('reason') or 'This course is free — enrol directly.')
            return redirect('course-detail', slug=course.slug)
        if not request.user.is_student:
            messages.info(request, 'Staff accounts do not purchase courses.')
            return redirect('course-detail', slug=course.slug)
        current = active_payment_for(request.user, course)
        if current and current.is_current:
            messages.info(request, 'You already have access to this course.')
            return redirect('course-detail', slug=course.slug)

        raw_coupon = request.GET.get('coupon', '').strip()
        promo, coupon_err, discount, final_price = self._get_coupon_info(
            request, course, pricing['final_price'], raw_coupon
        )
        return self._render(
            request, course,
            coupon_code=promo.code if promo else raw_coupon,
            coupon_error=coupon_err,
            promo=promo,
            discount_amount=discount,
            final_price=final_price,
        )

    def post(self, request, *args, **kwargs):
        course = self.get_course()
        if not request.user.is_student:
            return redirect('course-detail', slug=course.slug)

        pricing = course.calculate_price_for_user(request.user)
        if pricing['is_free']:
            messages.info(request, 'Course is free or covered by active membership. Enrol directly.')
            return redirect('course-detail', slug=course.slug)

        existing = Payment.objects.filter(
            student=request.user, course=course, status=Payment.Status.PENDING
        ).first()
        if existing:
            messages.info(request, 'Your payment for this course is already awaiting review.')
            return redirect('course-detail', slug=course.slug)

        base_price = pricing['final_price']
        raw_coupon = (request.POST.get('coupon_code') or request.GET.get('coupon') or '').strip()

        promo, coupon_err, discount, final_price = self._get_coupon_info(
            request, course, base_price, raw_coupon
        )

        # Action: Apply coupon code preview
        if request.POST.get('action') == 'apply_coupon':
            if coupon_err:
                messages.error(request, coupon_err)
            elif promo:
                messages.success(request, f"Coupon '{promo.code}' applied! Saved {discount:,.0f} {course.currency}.")
            return self._render(
                request, course,
                coupon_code=promo.code if promo else raw_coupon,
                coupon_error=coupon_err,
                promo=promo,
                discount_amount=discount,
                final_price=final_price,
            )

        # If user submitted with an invalid coupon
        if raw_coupon and coupon_err:
            messages.error(request, f"Cannot complete checkout: {coupon_err}")
            return self._render(
                request, course,
                coupon_code=raw_coupon,
                coupon_error=coupon_err,
                discount_amount=Decimal('0.00'),
                final_price=base_price,
            )

        # CASE 1: 100% Free / Free with Coupon (final_price <= 0)
        if final_price <= Decimal('0.00'):
            from apps.courses.services.access import enroll_student_in_course

            with transaction.atomic():
                # Fulfill zero-amount transaction for auditing
                payment = Payment.objects.create(
                    student=request.user,
                    course=course,
                    payment_type=Payment.PaymentType.COURSE_PURCHASE,
                    provider='coupon',
                    method=Payment.Method.OTHER,
                    amount=Decimal('0.00'),
                    original_amount=base_price,
                    discount_amount=discount,
                    coupon_code=promo.code if promo else '',
                    promotion=promo,
                    currency=course.currency,
                    billing_period=course.billing_period,
                    platform_fee=Decimal('0.00'),
                    teacher_amount=Decimal('0.00'),
                    status=Payment.Status.SUCCESS,
                    reviewed_by=None,
                    reviewed_at=timezone.now(),
                    note=f"100% discount redeemed via coupon {promo.code if promo else 'PROMO'}."
                )

                if promo:
                    PromotionUsage.objects.create(
                        promotion=promo,
                        user=request.user,
                        course=course,
                        payment=payment,
                        original_price=base_price,
                        discount_amount=discount,
                        final_price=Decimal('0.00'),
                    )
                    promo.usage_count = promo.usages.count()
                    promo.save(update_fields=['usage_count', 'updated_at'])

                enroll_student_in_course(request.user, course, source=Enrollment.Source.COUPON)

            coupon_str = f" using coupon '{promo.code}'" if promo else ""
            messages.success(
                request,
                f"Successfully enrolled in '{course.title}' for free{coupon_str}! You now have immediate access."
            )
            return redirect('course-detail', slug=course.slug)

        # CASE 2: Payable amount > 0 MMK
        form = PaymentSubmitForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Payment not submitted: ' + ' '.join(
                error for errors in form.errors.values() for error in errors
            ))
            return self._render(
                request, course, form=form,
                coupon_code=promo.code if promo else raw_coupon,
                coupon_error=coupon_err,
                promo=promo,
                discount_amount=discount,
                final_price=final_price,
                status=200
            )

        with transaction.atomic():
            payment = form.save(commit=False)
            payment.student = request.user
            payment.course = course
            payment.plan = None
            payment.payment_type = Payment.PaymentType.COURSE_PURCHASE
            payment.amount = final_price  # Authoritative server-side price!
            payment.original_amount = base_price
            payment.discount_amount = discount
            payment.coupon_code = promo.code if promo else ''
            payment.promotion = promo
            payment.currency = course.currency
            payment.billing_period = course.billing_period
            payment.platform_fee, payment.teacher_amount = Payment.split(final_price)
            payment.status = Payment.Status.PENDING

            pm = PaymentMethod.objects.filter(code=payment.method, is_active=True).first()
            if pm:
                payment.payment_method = pm

            payment.save()

            if promo:
                PromotionUsage.objects.create(
                    promotion=promo,
                    user=request.user,
                    course=course,
                    payment=payment,
                    original_price=base_price,
                    discount_amount=discount,
                    final_price=final_price,
                )
                promo.usage_count = promo.usages.count()
                promo.save(update_fields=['usage_count', 'updated_at'])

        coupon_msg = f" (Coupon '{promo.code}' applied: {discount:,.0f} {course.currency} off)" if promo else ""
        messages.success(
            request,
            f'Payment of {final_price:,.0f} {course.currency}{coupon_msg} submitted — an administrator '
            f'will review it shortly.'
        )
        return redirect('course-detail', slug=course.slug)


class MyPaymentsView(LoginRequiredMixin, TemplateView):
    """The student's own payment history."""
    template_name = 'billing/my_payments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = Payment.objects.filter(
            student=self.request.user
        ).select_related('course', 'plan')
        return context


class PaymentListView(AdminRequiredMixin, TemplateView):
    """Administrator review queue for manual payments."""
    template_name = 'billing/payment_list.html'

    def get_status(self):
        status = self.request.GET.get('status', Payment.Status.PENDING)
        return status if status in Payment.Status.values else Payment.Status.PENDING

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.get_status()
        context['status'] = status
        context['payments'] = Payment.objects.filter(status=status).select_related(
            'student', 'course', 'course__owner', 'plan'
        )
        context['status_tabs'] = [
            (value, label, Payment.objects.filter(status=value).count())
            for value, label in Payment.Status.choices
        ]
        context['platform_earnings'] = sum(
            (p.platform_fee for p in Payment.objects.filter(status=Payment.Status.APPROVED)),
            start=Decimal('0.00'),
        )
        return context


class PaymentReviewView(AdminRequiredMixin, View):
    """Approve (which enrols the student or activates subscription) or reject a single payment."""

    template_name = 'billing/payment_review.html'

    def get_payment(self):
        return get_object_or_404(
            Payment.objects.select_related('student', 'course', 'course__owner', 'plan'),
            id=self.kwargs['payment_id'],
        )

    def get(self, request, *args, **kwargs):
        payment = self.get_payment()
        return render(request, self.template_name, {
            'payment': payment,
            'form': PaymentDecisionForm(initial={'action': PaymentDecisionForm.ACTION_APPROVE}),
        })

    def post(self, request, *args, **kwargs):
        payment = self.get_payment()
        if payment.status != Payment.Status.PENDING:
            messages.info(request, 'This payment has already been reviewed.')
            return redirect('payment-list')

        form = PaymentDecisionForm(request.POST)
        if not form.is_valid():
            messages.error(request, ' '.join(
                error for errors in form.errors.values() for error in errors
            ))
            return render(request, self.template_name, {'payment': payment, 'form': form})

        with transaction.atomic():
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()

            if form.cleaned_data['action'] == PaymentDecisionForm.ACTION_REJECT:
                payment.mark_failed(
                    reason=form.cleaned_data['rejection_reason'].strip() or 'Rejected by administrator.',
                    status=Payment.Status.REJECTED,
                )
                messages.warning(
                    request, f'Payment from {payment.student.username} rejected.'
                )
            else:
                from apps.billing.services import fulfill_payment
                payment.status = Payment.Status.APPROVED
                payment.period_start = timezone.localdate()
                payment.save(update_fields=['status', 'period_start', 'reviewed_by', 'reviewed_at', 'updated_at'])
                fulfill_payment(payment)
                messages.success(
                    request,
                    f'Payment approved and fulfilled successfully for {payment.student.username}.'
                )

        return redirect('payment-list')


# -----------------------------------------------------------------------------
# REST API Endpoints (Mobile & Client apps)
# -----------------------------------------------------------------------------

class SubscriptionPlanListAPIView(APIView):
    """
    GET /billing/api/plans/
    List all available subscription plans.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        SubscriptionPlan.ensure_default_plans()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MySubscriptionAPIView(APIView):
    """
    GET /billing/api/my-subscription/
    Returns current student's active subscription tier.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sub = active_subscription_for(request.user)
        if not sub:
            # Fallback to free Starter plan representation if none assigned yet
            SubscriptionPlan.ensure_default_plans()
            starter = SubscriptionPlan.objects.filter(plan_type=SubscriptionPlan.PlanType.STARTER).first()
            return Response({
                'is_active': False,
                'is_current': False,
                'plan': SubscriptionPlanSerializer(starter).data if starter else None,
                'message': 'No paid subscription active. Defaulting to Starter features.'
            }, status=status.HTTP_200_OK)
        return Response(UserSubscriptionSerializer(sub).data, status=status.HTTP_200_OK)


class SubscribeAPIView(APIView):
    """
    POST /billing/api/subscribe/
    Subscribes to Starter (instant) or submits proof for Standard/Premium.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionCheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        plan_type = serializer.validated_data['plan_type']
        cycle = serializer.validated_data['billing_cycle']
        method = serializer.validated_data['method']
        reference = serializer.validated_data.get('reference', '')
        note = serializer.validated_data.get('note', '')

        SubscriptionPlan.ensure_default_plans()
        plan = get_object_or_404(SubscriptionPlan, plan_type=plan_type, is_active=True)

        if plan.plan_type == SubscriptionPlan.PlanType.STARTER:
            UserSubscription.objects.filter(user=request.user, is_active=True).update(is_active=False)
            sub = UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                billing_cycle=UserSubscription.BillingCycle.LIFETIME,
                start_date=timezone.localdate(),
                end_date=None,
                is_active=True,
            )
            return Response({
                'message': 'Starter plan activated.',
                'subscription': UserSubscriptionSerializer(sub).data
            }, status=status.HTTP_201_CREATED)

        amount = plan.yearly_price if cycle == 'yearly' else plan.monthly_price
        payment = Payment.objects.create(
            student=request.user,
            plan=plan,
            course=None,
            amount=amount,
            currency=plan.currency,
            billing_period=cycle,
            method=method,
            reference=reference,
            note=note,
            platform_fee=amount,
            teacher_amount=Decimal('0.00'),
            status=Payment.Status.PENDING,
        )
        return Response({
            'message': 'Subscription payment submitted for admin review.',
            'payment_id': str(payment.id),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'plan': plan.name,
        }, status=status.HTTP_202_ACCEPTED)


class InvoiceDetailView(LoginRequiredMixin, View):
    """
    Renders official printable invoice receipt.
    Accessible only to the student who owns the invoice or administrators/staff.
    """
    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        is_admin_user = (
            getattr(request.user, 'is_staff', False) or
            getattr(request.user, 'is_admin', False) or
            (hasattr(request.user, 'has_role') and request.user.has_role('admin'))
        )
        if invoice.student != request.user and not is_admin_user:
            return HttpResponseForbidden("You do not have permission to view this invoice.")

        return render(request, 'billing/invoice_detail.html', {
            'invoice': invoice,
            'PLATFORM_NAME': 'Myanmar E-Learning',
        })


class CancelSubscriptionView(LoginRequiredMixin, View):
    """
    Allows a student to cancel their active subscription.
    """
    def post(self, request):
        reason = request.POST.get('reason', '').strip()
        from apps.billing.services import cancel_subscription
        sub = cancel_subscription(request.user, reason=reason)
        if sub:
            messages.success(request, f"Your {sub.plan.name} subscription has been cancelled.")
        else:
            messages.info(request, "No active subscription found to cancel.")
        return redirect('my-subscription')


class PaymentRefundView(AdminRequiredMixin, View):
    """
    Processes an administrative refund for a settled payment:
    - Revokes course enrollment or subscription
    - Reverses partner revenue ledger record
    - Updates invoice status to REFUNDED
    """
    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        reason = request.POST.get('refund_reason', '').strip() or 'Administrative refund'
        amount_str = request.POST.get('refund_amount', '').strip()
        refund_amount = Decimal(amount_str) if amount_str else payment.amount

        try:
            from apps.billing.services import process_refund
            process_refund(payment, amount=refund_amount, reason=reason, user=request.user)
            messages.success(request, f"Payment #{payment.id} successfully refunded ({refund_amount:,.0f} {payment.currency}).")
        except Exception as e:
            messages.error(request, f"Refund failed: {str(e)}")

        return redirect(request.META.get('HTTP_REFERER') or reverse('payment-list'))


class PlatformRevenueReportView(AdminRequiredMixin, TemplateView):
    """
    Consolidated financial dashboard for MEL platform administrators:
    - Total Gross Platform Revenue
    - Platform Fee Retained (MEL Share)
    - Instructor Payout Entitlements
    - Partner Institutional Revenue Split
    - Total Refunds Issued
    - Breakdown by Course Purchases, Subscriptions, Exam Vouchers, Certificate Fees
    - Full Transaction Ledger & Exportable Audit Records
    """
    template_name = 'billing/platform_revenue_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.billing.services import get_platform_revenue_summary
        from apps.billing.models import PartnerRevenueRecord
        context['summary'] = get_platform_revenue_summary()
        context['recent_payments'] = Payment.objects.select_related(
            'student', 'course', 'plan', 'reviewed_by'
        ).order_by('-created_at')[:50]
        context['partner_records'] = PartnerRevenueRecord.objects.select_related(
            'partner_institution', 'course', 'payment'
        ).order_by('-created_at')[:50]
        return context


class PartnerRevenueSettlementView(AdminRequiredMixin, View):
    """Marks pending partner revenue records as SETTLED upon bank/transfer disbursement."""
    def post(self, request, record_id):
        from apps.billing.models import PartnerRevenueRecord
        from apps.billing.services import settle_partner_revenue_record
        record = get_object_or_404(PartnerRevenueRecord, id=record_id)
        settle_partner_revenue_record(record, settled_by=request.user)
        messages.success(
            request,
            f"Settlement recorded for {record.partner_institution.name} ({record.partner_amount:,.0f} MMK)."
        )
        return redirect(request.META.get('HTTP_REFERER') or reverse('platform-revenue-report'))


class CancelSubscriptionAPIView(APIView):
    """
    POST /billing/api/my-subscription/cancel/
    Cancels current student's active subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reason = request.data.get('reason', '')
        from apps.billing.services import cancel_subscription
        sub = cancel_subscription(request.user, reason=reason)
        if sub:
            return Response({'message': f'Subscription {sub.plan.name} cancelled successfully.'}, status=status.HTTP_200_OK)
        return Response({'message': 'No active subscription found to cancel.'}, status=status.HTTP_404_NOT_FOUND)


class PaymentWebhookAPIView(APIView):
    """
    POST /billing/api/webhook/<provider_code>/
    Secure provider callback / webhook endpoint.
    Verifies payload signature, validates reference, and idempotently fulfills payment.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, provider_code):
        from apps.billing.providers.registry import get_payment_provider
        from apps.billing.services import fulfill_payment
        provider = get_payment_provider(provider_code)
        verification = provider.verify_webhook(request.data, dict(request.headers))
        if not verification.get('verified'):
            return Response({'error': 'Webhook signature invalid'}, status=status.HTTP_400_BAD_REQUEST)

        ref = request.data.get('reference') or request.data.get('transaction_id')
        payment_id = request.data.get('payment_id')

        query = Payment.objects.none()
        if payment_id:
            query = Payment.objects.filter(id=payment_id)
        elif ref:
            query = Payment.objects.filter(reference=ref)

        payment = query.first()
        if not payment:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        event_status = request.data.get('status', 'success').lower()
        if event_status in ['success', 'completed', 'paid']:
            if not payment.is_successful:
                payment.mark_success()
                fulfill_payment(payment)
        elif event_status in ['failed', 'error']:
            payment.mark_failed(reason=request.data.get('message', 'Provider reported failure'))
        elif event_status in ['cancelled']:
            payment.mark_cancelled(reason=request.data.get('message', 'Provider reported cancellation'))
        elif event_status in ['processing']:
            payment.mark_processing()

        return Response({'status': 'ok', 'payment_status': payment.status}, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# Payment Method Management Views (Admin)
# ----------------------------------------------------------------------

class PaymentMethodListView(AdminRequiredMixin, ListView):
    model = PaymentMethod
    template_name = 'billing/methods/list.html'
    context_object_name = 'payment_methods'
    ordering = ['display_order', 'name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        PaymentMethod.ensure_default_methods()
        context['payment_methods'] = PaymentMethod.objects.all().order_by('display_order', 'name')
        return context


class PaymentMethodCreateView(AdminRequiredMixin, CreateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'billing/methods/form.html'

    def form_valid(self, form):
        messages.success(self.request, f"Payment channel '{form.instance.name}' added successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('billing:method-list')


class PaymentMethodUpdateView(AdminRequiredMixin, UpdateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'billing/methods/form.html'

    def form_valid(self, form):
        messages.success(self.request, f"Payment channel '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('billing:method-list')


class PaymentMethodToggleView(AdminRequiredMixin, View):
    def post(self, request, pk):
        method = get_object_or_404(PaymentMethod, pk=pk)
        method.is_active = not method.is_active
        method.save(update_fields=['is_active', 'updated_at'])
        state = 'activated' if method.is_active else 'disabled'
        messages.success(request, f"Payment method '{method.name}' is now {state}.")
        return redirect('billing:method-list')

    def get(self, request, pk):
        return self.post(request, pk)


class PaymentMethodDeleteView(AdminRequiredMixin, View):
    def post(self, request, pk):
        method = get_object_or_404(PaymentMethod, pk=pk)
        if method.payments.exists():
            method.is_active = False
            method.save(update_fields=['is_active', 'updated_at'])
            messages.warning(
                request,
                f"Payment method '{method.name}' has recorded transactions and cannot be deleted. It has been deactivated instead."
            )
        else:
            name = method.name
            method.delete()
            messages.success(request, f"Payment method '{name}' deleted.")
        return redirect('billing:method-list')

    def get(self, request, pk):
        return self.post(request, pk)


# ----------------------------------------------------------------------
# Promotion & Coupon Code Management Views (Admin, Teacher, Partner)
# ----------------------------------------------------------------------

class CanManagePromotionsMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Permits Platform Administrators, Teachers, and Institutional Partners.
    Rejects students with HTTP 403 Forbidden.
    """
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return bool(
            getattr(user, 'is_admin', False)
            or getattr(user, 'is_teacher', False)
            or getattr(user, 'is_partner', False)
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You do not have permission to manage promotions or coupons.")
        return super().handle_no_permission()


def get_user_authorized_promotions(user):
    """
    Returns QuerySet of Promotion instances user has authority over:
    - Admin: All promotions
    - Teacher: Promotions created by user or targeting courses owned by user
    - Partner: Promotions created by user or targeting courses of their partner institution
    """
    if getattr(user, 'is_admin', False):
        return Promotion.objects.all().distinct()

    from apps.partner.views import get_user_partner_institutions
    institutions = get_user_partner_institutions(user)

    filters = Q(creator=user)
    if institutions.exists():
        filters |= Q(partner_institution__in=institutions) | Q(courses__partner_institution__in=institutions)
    if getattr(user, 'is_teacher', False):
        filters |= Q(courses__owner=user)

    return Promotion.objects.filter(filters).distinct()


class PromotionListView(CanManagePromotionsMixin, ListView):
    template_name = 'billing/promotions/list.html'
    context_object_name = 'promotions'
    paginate_by = 20

    def get_queryset(self):
        qs = get_user_authorized_promotions(self.request.user).prefetch_related(
            'courses', 'usages'
        ).select_related('creator', 'partner_institution')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))

        status_tab = self.request.GET.get('status', 'all')
        now = timezone.now()
        if status_tab == 'active':
            qs = qs.filter(is_active=True).filter(
                Q(start_at__isnull=True) | Q(start_at__lte=now)
            ).filter(
                Q(end_at__isnull=True) | Q(end_at__gte=now)
            )
        elif status_tab == 'expired':
            qs = qs.filter(end_at__lt=now)
        elif status_tab == 'scheduled':
            qs = qs.filter(start_at__gt=now)
        elif status_tab == 'disabled':
            qs = qs.filter(is_active=False)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = get_user_authorized_promotions(self.request.user)
        now = timezone.now()

        total_promotions = base_qs.count()
        active_promos = base_qs.filter(is_active=True).filter(
            Q(start_at__isnull=True) | Q(start_at__lte=now)
        ).filter(
            Q(end_at__isnull=True) | Q(end_at__gte=now)
        ).count()
        total_usages = PromotionUsage.objects.filter(promotion__in=base_qs).count()
        total_discount = PromotionUsage.objects.filter(promotion__in=base_qs).aggregate(
            total=Sum('discount_amount')
        )['total'] or Decimal('0.00')

        context['stats'] = {
            'total_promotions': total_promotions,
            'active_promotions': active_promos,
            'total_usages': total_usages,
            'total_discount': total_discount,
        }
        context['status_filter'] = self.request.GET.get('status', 'all')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class PromotionCreateView(CanManagePromotionsMixin, CreateView):
    model = Promotion
    form_class = PromotionForm
    template_name = 'billing/promotions/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Promotion '{self.object.code}' created successfully!")
        return response

    def get_success_url(self):
        return reverse('billing:promotion-list')


class PromotionUpdateView(CanManagePromotionsMixin, UpdateView):
    model = Promotion
    form_class = PromotionForm
    template_name = 'billing/promotions/form.html'

    def get_queryset(self):
        return get_user_authorized_promotions(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Promotion '{self.object.code}' updated successfully!")
        return response

    def get_success_url(self):
        return reverse('billing:promotion-list')


class PromotionToggleView(CanManagePromotionsMixin, View):
    def post(self, request, pk):
        promo = get_object_or_404(get_user_authorized_promotions(request.user), pk=pk)
        promo.is_active = not promo.is_active
        promo.save(update_fields=['is_active', 'updated_at'])
        state = 'activated' if promo.is_active else 'disabled'
        messages.success(request, f"Promotion '{promo.code}' has been {state}.")
        return redirect('billing:promotion-list')

    def get(self, request, pk):
        return self.post(request, pk)


class PromotionDeleteView(CanManagePromotionsMixin, View):
    def post(self, request, pk):
        promo = get_object_or_404(get_user_authorized_promotions(request.user), pk=pk)
        if promo.usages.exists():
            promo.is_active = False
            promo.save(update_fields=['is_active', 'updated_at'])
            messages.warning(
                request,
                f"Promotion '{promo.code}' has {promo.usages.count()} existing redemption(s) and cannot be permanently deleted. It has been deactivated."
            )
        else:
            code = promo.code
            promo.delete()
            messages.success(request, f"Promotion '{code}' deleted.")
        return redirect('billing:promotion-list')

    def get(self, request, pk):
        return self.post(request, pk)


class PromotionAnalyticsView(CanManagePromotionsMixin, DetailView):
    model = Promotion
    template_name = 'billing/promotions/analytics.html'
    context_object_name = 'promotion'

    def get_queryset(self):
        return get_user_authorized_promotions(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        promo = self.object
        usages = promo.usages.select_related('user', 'course', 'payment').order_by('-created_at')
        total_discount = usages.aggregate(total=Sum('discount_amount'))['total'] or Decimal('0.00')
        total_gross = usages.aggregate(total=Sum('original_price'))['total'] or Decimal('0.00')
        total_net = usages.aggregate(total=Sum('final_price'))['total'] or Decimal('0.00')

        context['usages'] = usages
        context['stats'] = {
            'total_usages': usages.count(),
            'total_discount': total_discount,
            'total_gross': total_gross,
            'total_net': total_net,
        }
        return context


