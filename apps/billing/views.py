from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from apps.common.permissions import RoleRequiredMixin
from apps.courses.models import Course, Enrollment
from .forms import PaymentDecisionForm, PaymentSubmitForm
from .models import Payment, active_payment_for


class AdminRequiredMixin(RoleRequiredMixin):
    """Restricts a view to ADMIN accounts (administrators always pass)."""
    allowed_roles = ['admin']


def _next_period_end(course, start):
    """Month-long window for monthly billing, None for one-time access."""
    if course.billing_period != Course.BillingPeriod.MONTHLY:
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
        ).select_related('course')
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
            'student', 'course', 'course__owner'
        )
        context['status_tabs'] = [
            (value, label, Payment.objects.filter(status=value).count())
            for value, label in Payment.Status.choices
        ]
        context['platform_earnings'] = sum(
            (p.platform_fee for p in Payment.objects.filter(status=Payment.Status.APPROVED)),
            start=0,
        )
        return context


class PaymentReviewView(AdminRequiredMixin, View):
    """Approve (which enrols the student) or reject a single payment."""

    template_name = 'billing/payment_review.html'

    def get_payment(self):
        return get_object_or_404(
            Payment.objects.select_related('student', 'course', 'course__owner'),
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
                payment.period_start = timezone.now().date()
                payment.period_end = _next_period_end(payment.course, payment.period_start)
                payment.save()

                Enrollment.objects.get_or_create(
                    course=payment.course, student=payment.student,
                    defaults={'status': Enrollment.Status.ACTIVE},
                )
                messages.success(
                    request,
                    f'Payment approved — {payment.student.username} now has access to '
                    f'{payment.course.title}.'
                )

        return redirect('payment-list')
