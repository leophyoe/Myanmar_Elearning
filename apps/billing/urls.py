from django.urls import path
from .views import (
    CheckoutView, PaymentListView, PaymentReviewView, MyPaymentsView,
    PricingView, SubscribeView, MySubscriptionView,
    SubscriptionPlanListAPIView, MySubscriptionAPIView, SubscribeAPIView,
)

urlpatterns = [
    path('pricing/', PricingView.as_view(), name='pricing'),
    path('subscribe/<str:plan_type>/', SubscribeView.as_view(), name='subscribe'),
    path('my-subscription/', MySubscriptionView.as_view(), name='my-subscription'),
    path('my-payments/', MyPaymentsView.as_view(), name='payment-history'),
    path('review/', PaymentListView.as_view(), name='payment-list'),
    path('review/<uuid:payment_id>/', PaymentReviewView.as_view(), name='payment-review'),

    # REST APIs
    path('api/plans/', SubscriptionPlanListAPIView.as_view(), name='api-plans'),
    path('api/my-subscription/', MySubscriptionAPIView.as_view(), name='api-my-subscription'),
    path('api/subscribe/', SubscribeAPIView.as_view(), name='api-subscribe'),
]
