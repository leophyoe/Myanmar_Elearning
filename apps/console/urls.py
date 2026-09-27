from django.urls import path
from .views import (
    ConsoleHomeView,
    UserListView, UserCreateView, UserDetailView, UserUpdateView,
    UserPasswordResetView, UserToggleActiveView,
    AdminCourseListView, FeeOverviewView, PaymentRefundView,
)

urlpatterns = [
    path('', ConsoleHomeView.as_view(), name='console-home'),
    path('users/', UserListView.as_view(), name='console-user-list'),
    path('users/new/', UserCreateView.as_view(), name='console-user-create'),
    path('users/<uuid:user_id>/', UserDetailView.as_view(), name='console-user-detail'),
    path('users/<uuid:user_id>/edit/', UserUpdateView.as_view(), name='console-user-edit'),
    path('users/<uuid:user_id>/password/', UserPasswordResetView.as_view(), name='console-user-password'),
    path('users/<uuid:user_id>/toggle/', UserToggleActiveView.as_view(), name='console-user-toggle'),
    path('courses/', AdminCourseListView.as_view(), name='console-course-list'),
    path('fees/', FeeOverviewView.as_view(), name='console-fee-overview'),
    path('payments/<uuid:payment_id>/refund/', PaymentRefundView.as_view(), name='console-payment-refund'),
]
