from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import RoleRequiredMixin
from apps.courses.models import Course, Enrollment
from .forms import PaymentDecisionForm, PaymentSubmitForm, SubscriptionSubmitForm
from .models import Payment, SubscriptionPlan, UserSubscription, active_payment_for, active_subscription_for
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
        context['plans'] = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
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
        return render(request, self.template_name, {
            'plan': plan,
            'form': form,
            'current_subscription': current_sub,
            'pending_payment': pending_payment,
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
    """Collect proof of payment for a paid course. Never enrols the student."""

    template_name = 'billing/checkout.html'

    def get_course(self):
        return get_object_or_404(Course, slug=self.kwargs['slug'], is_published=True)

    def _render(self, request, course, form=None, status=200):
        return render(request, self.template_name, {
            'course': course,
            'form': form or PaymentSubmitForm(),
            'currency': course.currency,
            'pending': Payment.objects.filter(
                student=request.user, course=course,
                status=Payment.Status.PENDING,
            ).first(),
            'existing': active_payment_for(request.user, course),
        }, status=status)

    def get(self, request, *args, **kwargs):
        course = self.get_course()
        if course.is_free:
            messages.info(request, 'This course is free — enrol directly.')
            return redirect('course-detail', slug=course.slug)
        if not request.user.is_student:
            messages.info(request, 'Staff accounts do not purchase courses.')
            return redirect('course-detail', slug=course.slug)
        current = active_payment_for(request.user, course)
        if current and current.is_current:
            messages.info(request, 'You already have access to this course.')
            return redirect('course-detail', slug=course.slug)
        return self._render(request, course)

    def post(self, request, *args, **kwargs):
        course = self.get_course()
        if course.is_free or not request.user.is_student:
            return redirect('course-detail', slug=course.slug)

        existing = Payment.objects.filter(
            student=request.user, course=course, status=Payment.Status.PENDING
        ).first()
        if existing:
            messages.info(request, 'Your payment for this course is already awaiting review.')
            return redirect('course-detail', slug=course.slug)

        form = PaymentSubmitForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'Payment not submitted: ' + ' '.join(
                error for errors in form.errors.values() for error in errors
            ))
            return self._render(request, course, form, status=200)

        payment = form.save(commit=False)
        payment.student = request.user
        payment.course = course
        payment.plan = None
        payment.amount = course.price
        payment.currency = course.currency
        payment.billing_period = course.billing_period
        payment.platform_fee, payment.teacher_amount = Payment.split(course.price)
        payment.status = Payment.Status.PENDING
        payment.save()

        messages.success(
            request,
            f'Payment of {course.price} {course.currency} submitted — an administrator '
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
                payment.status = Payment.Status.REJECTED
                payment.rejection_reason = form.cleaned_data['rejection_reason'].strip()
                payment.save()
                messages.warning(
                    request, f'Payment from {payment.student.username} rejected.'
                )
            else:
                payment.status = Payment.Status.APPROVED
                payment.period_start = timezone.localdate()

                if payment.plan:
                    # Subscription payment approval
                    if payment.billing_period == UserSubscription.BillingCycle.YEARLY:
                        period_end = payment.period_start + timezone.timedelta(days=365)
                    else:
                        period_end = payment.period_start + timezone.timedelta(days=30)
                    payment.period_end = period_end
                    payment.save()

                    UserSubscription.objects.filter(user=payment.student, is_active=True).update(is_active=False)
                    UserSubscription.objects.create(
                        user=payment.student,
                        plan=payment.plan,
                        billing_cycle=payment.billing_period,
                        start_date=payment.period_start,
                        end_date=period_end,
                        is_active=True,
                    )
                    messages.success(
                        request,
                        f'Subscription approved! {payment.student.username} now has active {payment.plan.name} membership until {period_end}.'
                    )
                else:
                    # Course payment approval
                    payment.period_end = _next_period_end(payment.course, payment.period_start)
                    payment.save()

                    Enrollment.objects.get_or_create(
                        course=payment.course, student=payment.student,
                        defaults={'status': Enrollment.Status.ACTIVE},
                    )
                    messages.success(
                        request,
                        f'Payment approved — {payment.student.username} now has access to {payment.course.title}.'
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
