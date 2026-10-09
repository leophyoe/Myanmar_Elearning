from django.urls import path
from .views import (
    CheckoutView, PaymentListView, PaymentReviewView, MyPaymentsView,
    PricingView, SubscribeView, MySubscriptionView, InvoiceDetailView,
    CancelSubscriptionView, PaymentRefundView, PlatformRevenueReportView,
    PartnerRevenueSettlementView, SubscriptionPlanListAPIView,
    MySubscriptionAPIView, SubscribeAPIView, CancelSubscriptionAPIView,
    PaymentWebhookAPIView,
    PaymentMethodListView, PaymentMethodCreateView, PaymentMethodUpdateView,
    PaymentMethodToggleView, PaymentMethodDeleteView,
    PromotionListView, PromotionCreateView, PromotionUpdateView,
    PromotionToggleView, PromotionDeleteView, PromotionAnalyticsView,
)

urlpatterns = [
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('subscribe/<str:plan_type>/', SubscribeView.as_view(), name='subscribe'),
    path('my-subscription/', MySubscriptionView.as_view(), name='my-subscription'),
    path('subscription/cancel/', CancelSubscriptionView.as_view(), name='cancel-subscription'),
    path('my-payments/', MyPaymentsView.as_view(), name='payment-history'),
    path('review/', PaymentListView.as_view(), name='payment-list'),
    path('review/<uuid:payment_id>/', PaymentReviewView.as_view(), name='payment-review'),
    path('review/<uuid:payment_id>/detail/', PaymentReviewView.as_view(), name='payment-detail'),
    path('refund/<uuid:payment_id>/', PaymentRefundView.as_view(), name='payment-refund'),
    path('revenue/', PlatformRevenueReportView.as_view(), name='platform-revenue-report'),
    path('revenue/settle/<uuid:record_id>/', PartnerRevenueSettlementView.as_view(), name='partner-revenue-settle'),
    path('invoices/<str:invoice_id>/', InvoiceDetailView.as_view(), name='invoice-detail'),

    # Payment Methods Management (Admin)
    path('methods/', PaymentMethodListView.as_view(), name='method-list'),
    path('methods/create/', PaymentMethodCreateView.as_view(), name='method-create'),
    path('methods/<uuid:pk>/edit/', PaymentMethodUpdateView.as_view(), name='method-edit'),
    path('methods/<uuid:pk>/toggle/', PaymentMethodToggleView.as_view(), name='method-toggle'),
    path('methods/<uuid:pk>/delete/', PaymentMethodDeleteView.as_view(), name='method-delete'),

    # Promotions & Coupons Management (Admin, Teacher, Partner)
    path('promotions/', PromotionListView.as_view(), name='promotion-list'),
    path('promotions/create/', PromotionCreateView.as_view(), name='promotion-create'),
    path('promotions/<uuid:pk>/edit/', PromotionUpdateView.as_view(), name='promotion-edit'),
    path('promotions/<uuid:pk>/toggle/', PromotionToggleView.as_view(), name='promotion-toggle'),
    path('promotions/<uuid:pk>/delete/', PromotionDeleteView.as_view(), name='promotion-delete'),
    path('promotions/<uuid:pk>/analytics/', PromotionAnalyticsView.as_view(), name='promotion-analytics'),

    # REST APIs
    path('api/plans/', SubscriptionPlanListAPIView.as_view(), name='api-plans'),
    path('api/my-subscription/', MySubscriptionAPIView.as_view(), name='api-my-subscription'),
    path('api/my-subscription/cancel/', CancelSubscriptionAPIView.as_view(), name='api-cancel-subscription'),
    path('api/subscribe/', SubscribeAPIView.as_view(), name='api-subscribe'),
    path('api/webhook/<str:provider_code>/', PaymentWebhookAPIView.as_view(), name='api-payment-webhook'),
]

