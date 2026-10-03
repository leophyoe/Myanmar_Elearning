from django.urls import path
from .views import (
    CheckoutView, PaymentListView, PaymentReviewView, MyPaymentsView,
    PricingView, SubscribeView, MySubscriptionView, InvoiceDetailView,
    CancelSubscriptionView, PaymentRefundView, PlatformRevenueReportView,
    PartnerRevenueSettlementView, SubscriptionPlanListAPIView,
    MySubscriptionAPIView, SubscribeAPIView, CancelSubscriptionAPIView,
    PaymentWebhookAPIView,
)

urlpatterns = [
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('subscribe/<str:plan_type>/', SubscribeView.as_view(), name='subscribe'),
    path('my-subscription/', MySubscriptionView.as_view(), name='my-subscription'),
    path('subscription/cancel/', CancelSubscriptionView.as_view(), name='cancel-subscription'),
    path('my-payments/', MyPaymentsView.as_view(), name='payment-history'),
    path('review/', PaymentListView.as_view(), name='payment-list'),
    path('review/<uuid:payment_id>/', PaymentReviewView.as_view(), name='payment-review'),
    path('refund/<uuid:payment_id>/', PaymentRefundView.as_view(), name='payment-refund'),
    path('revenue/', PlatformRevenueReportView.as_view(), name='platform-revenue-report'),
    path('revenue/settle/<uuid:record_id>/', PartnerRevenueSettlementView.as_view(), name='partner-revenue-settle'),
    path('invoices/<str:invoice_id>/', InvoiceDetailView.as_view(), name='invoice-detail'),

    # REST APIs
    path('api/plans/', SubscriptionPlanListAPIView.as_view(), name='api-plans'),
    path('api/my-subscription/', MySubscriptionAPIView.as_view(), name='api-my-subscription'),
    path('api/my-subscription/cancel/', CancelSubscriptionAPIView.as_view(), name='api-cancel-subscription'),
    path('api/subscribe/', SubscribeAPIView.as_view(), name='api-subscribe'),
    path('api/webhook/<str:provider_code>/', PaymentWebhookAPIView.as_view(), name='api-payment-webhook'),
]
