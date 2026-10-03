from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.billing.models import (
    SubscriptionPlan, UserSubscription, Payment, Invoice,
    active_subscription_for
)
from apps.billing.services import create_subscription_payment
from apps.api.serializers.membership import (
    SubscriptionPlanSerializer, UserSubscriptionDetailSerializer,
    SubscribeActionSerializer, PaymentHistorySerializer,
    InvoiceDetailSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class SubscriptionPlansAPIView(APIView):
    """
    GET /api/v1/membership/plans/
    Lists available Myanmar E-Learning membership plans:
    - Starter: 0 MMK
    - Standard: 5,000 MMK / 50,000 MMK
    - Premium: 15,000 MMK / 150,000 MMK
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        SubscriptionPlan.ensure_default_plans()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MySubscriptionStatusAPIView(APIView):
    """
    GET /api/v1/membership/status/
    Returns active membership status, expiration, and plan benefits.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sub = active_subscription_for(request.user)
        if sub and sub.is_current:
            return Response({
                'has_active_subscription': True,
                'subscription': UserSubscriptionDetailSerializer(sub).data
            }, status=status.HTTP_200_OK)

        return Response({
            'has_active_subscription': True,
            'subscription': {
                'plan_type': 'starter',
                'plan_name': 'Starter',
                'billing_cycle': 'lifetime',
                'start_date': request.user.created_at.date(),
                'end_date': None,
                'is_active': True,
                'is_current': True,
            }
        }, status=status.HTTP_200_OK)


class SubscribeAPIView(APIView):
    """
    POST /api/v1/membership/subscribe/
    Subscribes to Starter (instant) or initiates checkout for Standard/Premium.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SubscribeActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_type = serializer.validated_data['plan_type']
        cycle = serializer.validated_data['billing_cycle']
        method = serializer.validated_data['method']
        reference = serializer.validated_data.get('reference', '')
        note = serializer.validated_data.get('note', '')

        SubscriptionPlan.ensure_default_plans()
        plan = get_object_or_404(SubscriptionPlan, plan_type=plan_type, is_active=True)

        # 1. Instant Starter activation
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
                'message': 'Starter membership activated successfully.',
                'subscription': UserSubscriptionDetailSerializer(sub).data
            }, status=status.HTTP_201_CREATED)

        # 2. Paid tiers (Standard / Premium)
        payment, provider_resp = create_subscription_payment(
            student=request.user,
            plan=plan,
            billing_cycle=cycle,
            method=method,
            reference=reference,
            note=note,
            provider_code='manual_transfer',
        )

        return Response({
            'message': 'Subscription payment submitted for review.',
            'payment_id': str(payment.id),
            'amount': str(payment.amount),
            'currency': payment.currency,
            'plan': plan.name,
            'status': payment.status,
            'instruction': provider_resp.get('instruction', ''),
        }, status=status.HTTP_202_ACCEPTED)


class PaymentHistoryAPIView(APIView):
    """
    GET /api/v1/billing/my-payments/
    Lists payments made by the authenticated student.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Payment.objects.filter(student=request.user).select_related('course', 'plan', 'invoice').order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = PaymentHistorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class InvoiceDetailAPIView(APIView):
    """
    GET /api/v1/billing/invoices/<id>/
    Retrieves printable official receipt and itemized transaction data.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice.objects.select_related('student'), pk=pk)
        if invoice.student != request.user and not (request.user.is_admin or request.user.is_superuser):
            return Response(
                {'error': 'You do not have permission to view this invoice.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
