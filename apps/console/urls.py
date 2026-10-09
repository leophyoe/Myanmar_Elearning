from django.urls import path
from .views import (
    ConsoleHomeView,
    UserListView, UserCreateView, UserDetailView, UserUpdateView,
    UserPasswordResetView, UserToggleActiveView, UserApproveInstructorView,
    AdminCourseListView, FeeOverviewView, PaymentRefundView,
    CredentialReviewView, CredentialActionView,
    AdminLogListView,
    InstructorApplicationListView, InstructorApplicationDetailView, InstructorApplicationActionView,
    PartnerApplicationListView, PartnerApplicationActionView,
)

urlpatterns = [
    path('', ConsoleHomeView.as_view(), name='console-home'),
    path('users/', UserListView.as_view(), name='console-user-list'),
    path('users/new/', UserCreateView.as_view(), name='console-user-create'),
    path('users/<uuid:user_id>/', UserDetailView.as_view(), name='console-user-detail'),
    path('users/<uuid:user_id>/edit/', UserUpdateView.as_view(), name='console-user-edit'),
    path('users/<uuid:user_id>/password/', UserPasswordResetView.as_view(), name='console-user-password'),
    path('users/<uuid:user_id>/toggle/', UserToggleActiveView.as_view(), name='console-user-toggle'),
    path('users/<uuid:user_id>/approve-instructor/', UserApproveInstructorView.as_view(), name='console-user-approve-instructor'),
    path('instructor-applications/', InstructorApplicationListView.as_view(), name='console-instructor-application-list'),
    path('instructor-applications/<uuid:app_id>/', InstructorApplicationDetailView.as_view(), name='console-instructor-application-detail'),
    path('instructor-applications/<uuid:app_id>/<str:action>/', InstructorApplicationActionView.as_view(), name='console-instructor-application-action'),
    path('partner-applications/', PartnerApplicationListView.as_view(), name='console-partner-application-list'),
    path('partner-applications/<uuid:app_id>/<str:action>/', PartnerApplicationActionView.as_view(), name='console-partner-application-action'),
    path('courses/', AdminCourseListView.as_view(), name='console-course-list'),
    path('fees/', FeeOverviewView.as_view(), name='console-fee-overview'),
    path('payments/<uuid:payment_id>/refund/', PaymentRefundView.as_view(), name='console-payment-refund'),
    path('credentials/', CredentialReviewView.as_view(), name='console-credential-list'),
    path('credentials/<uuid:cert_id>/<str:action>/', CredentialActionView.as_view(), name='console-credential-action'),
    path('logs/', AdminLogListView.as_view(), name='console-log-list'),
]
