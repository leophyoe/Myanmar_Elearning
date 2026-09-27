from django.urls import path
from .views import CheckoutView, PaymentListView, PaymentReviewView, MyPaymentsView

urlpatterns = [
    path('my-payments/', MyPaymentsView.as_view(), name='payment-history'),
    path('review/', PaymentListView.as_view(), name='payment-list'),
    path('review/<uuid:payment_id>/', PaymentReviewView.as_view(), name='payment-review'),
]
