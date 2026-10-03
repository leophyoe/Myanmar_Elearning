from django.urls import path

from .views.auth import (
    LoginAPIView, RegisterAPIView, LogoutAPIView, PushDeviceRegisterAPIView
)
from .views.users import (
    UserProfileAPIView, ModeSwitchAPIView, PasswordChangeAPIView
)
from .views.courses import (
    SubjectListAPIView, CourseListAPIView, CourseDetailAPIView,
    CourseCurriculumAPIView, LessonDetailAPIView, CoursePricingAPIView
)
from .views.enrollment import (
    MyEnrollmentsAPIView, EnrollCourseAPIView, EnrollmentStatusAPIView
)
from .views.progress import (
    CourseProgressAPIView, CompleteLessonAPIView, ContinueLearningAPIView
)
from .views.assessments import (
    AssessmentListAPIView, AssessmentDetailAPIView, AssessmentStartAPIView,
    AssessmentSubmitAPIView, MyQuizAttemptsAPIView
)
from .views.certificates import (
    MyCertificatesAPIView, CertificateDetailAPIView, PublicCertificateVerifyAPIView
)
from .views.membership import (
    SubscriptionPlansAPIView, MySubscriptionStatusAPIView, SubscribeAPIView,
    PaymentHistoryAPIView, InvoiceDetailAPIView
)
from .views.instructor import (
    InstructorDashboardStatsAPIView, InstructorCoursesAPIView,
    InstructorCourseSubmitReviewAPIView, InstructorApplicationAPIView
)
from .views.partner import (
    PartnerOrganizationAPIView, PartnerStatsAPIView, PartnerStudentsAPIView,
    PartnerCoursesAPIView, PartnerInviteStudentAPIView
)
from .views.notifications import (
    NotificationListAPIView, NotificationUnreadCountAPIView,
    NotificationMarkReadAPIView, NotificationMarkAllReadAPIView
)
from .views.labs import (
    LabListAPIView, LabDetailAPIView, ActiveLabInstancesAPIView,
    LabStartAPIView, LabStopAPIView
)

urlpatterns = [
    # 1. Authentication
    path('auth/login/', LoginAPIView.as_view(), name='api-login'),
    path('auth/register/', RegisterAPIView.as_view(), name='api-register'),
    path('auth/logout/', LogoutAPIView.as_view(), name='api-logout'),
    path('auth/device/register/', PushDeviceRegisterAPIView.as_view(), name='api-device-register'),

    # 2. Users
    path('users/me/', UserProfileAPIView.as_view(), name='api-users-me'),
    path('users/switch-mode/', ModeSwitchAPIView.as_view(), name='api-users-switch-mode'),
    path('users/change-password/', PasswordChangeAPIView.as_view(), name='api-users-change-password'),

    # 3. Courses
    path('courses/subjects/', SubjectListAPIView.as_view(), name='api-courses-subjects'),
    path('courses/', CourseListAPIView.as_view(), name='api-courses-list'),
    path('courses/<slug:slug>/', CourseDetailAPIView.as_view(), name='api-courses-detail'),
    path('courses/<slug:slug>/curriculum/', CourseCurriculumAPIView.as_view(), name='api-courses-curriculum'),
    path('courses/<slug:slug>/lessons/<uuid:lesson_id>/', LessonDetailAPIView.as_view(), name='api-courses-lesson-detail'),
    path('courses/<slug:slug>/pricing/', CoursePricingAPIView.as_view(), name='api-courses-pricing'),

    # 4. Enrollment
    path('enrollments/my/', MyEnrollmentsAPIView.as_view(), name='api-enrollments-my'),
    path('enrollments/enroll/', EnrollCourseAPIView.as_view(), name='api-enrollments-enroll'),
    path('enrollments/<slug:slug>/status/', EnrollmentStatusAPIView.as_view(), name='api-enrollments-status'),

    # 5. Learning Progress
    path('progress/course/<slug:slug>/', CourseProgressAPIView.as_view(), name='api-progress-course'),
    path('progress/complete-lesson/', CompleteLessonAPIView.as_view(), name='api-progress-complete-lesson'),
    path('progress/continue/', ContinueLearningAPIView.as_view(), name='api-progress-continue'),

    # 6. Assessments
    path('assessments/', AssessmentListAPIView.as_view(), name='api-assessments-list'),
    path('assessments/<uuid:pk>/', AssessmentDetailAPIView.as_view(), name='api-assessments-detail'),
    path('assessments/<uuid:pk>/start/', AssessmentStartAPIView.as_view(), name='api-assessments-start'),
    path('assessments/<uuid:pk>/submit/', AssessmentSubmitAPIView.as_view(), name='api-assessments-submit'),
    path('assessments/attempts/<uuid:pk>/submit/', AssessmentSubmitAPIView.as_view(), name='api-assessments-attempt-submit'),
    path('assessments/my-attempts/', MyQuizAttemptsAPIView.as_view(), name='api-assessments-my-attempts'),

    # 7. Certificates
    path('certificates/my/', MyCertificatesAPIView.as_view(), name='api-certificates-my'),
    path('certificates/verify/<str:code>/', PublicCertificateVerifyAPIView.as_view(), name='api-certificates-verify'),
    path('certificates/<str:code>/', CertificateDetailAPIView.as_view(), name='api-certificates-detail'),

    # 8. Membership & Billing
    path('membership/plans/', SubscriptionPlansAPIView.as_view(), name='api-membership-plans'),
    path('membership/status/', MySubscriptionStatusAPIView.as_view(), name='api-membership-status'),
    path('membership/subscribe/', SubscribeAPIView.as_view(), name='api-membership-subscribe'),
    path('billing/my-payments/', PaymentHistoryAPIView.as_view(), name='api-billing-my-payments'),
    path('billing/invoices/<uuid:pk>/', InvoiceDetailAPIView.as_view(), name='api-billing-invoice-detail'),

    # 9. Instructor
    path('instructor/stats/', InstructorDashboardStatsAPIView.as_view(), name='api-instructor-stats'),
    path('instructor/courses/', InstructorCoursesAPIView.as_view(), name='api-instructor-courses'),
    path('instructor/courses/<uuid:pk>/submit-review/', InstructorCourseSubmitReviewAPIView.as_view(), name='api-instructor-submit-review'),
    path('instructor/apply/', InstructorApplicationAPIView.as_view(), name='api-instructor-apply'),

    # 10. Partner
    path('partner/organization/', PartnerOrganizationAPIView.as_view(), name='api-partner-organization'),
    path('partner/stats/', PartnerStatsAPIView.as_view(), name='api-partner-stats'),
    path('partner/students/', PartnerStudentsAPIView.as_view(), name='api-partner-students'),
    path('partner/courses/', PartnerCoursesAPIView.as_view(), name='api-partner-courses'),
    path('partner/invite-student/', PartnerInviteStudentAPIView.as_view(), name='api-partner-invite-student'),

    # 11. Notifications
    path('notifications/', NotificationListAPIView.as_view(), name='api-notifications-list'),
    path('notifications/unread-count/', NotificationUnreadCountAPIView.as_view(), name='api-notifications-unread-count'),
    path('notifications/<uuid:pk>/mark-read/', NotificationMarkReadAPIView.as_view(), name='api-notifications-mark-read'),
    path('notifications/mark-all-read/', NotificationMarkAllReadAPIView.as_view(), name='api-notifications-mark-all-read'),

    # 12. Labs
    path('labs/', LabListAPIView.as_view(), name='api-labs-list'),
    path('labs/instances/active/', ActiveLabInstancesAPIView.as_view(), name='api-labs-active-instances'),
    path('labs/<slug:slug>/', LabDetailAPIView.as_view(), name='api-labs-detail'),
    path('labs/<slug:slug>/start/', LabStartAPIView.as_view(), name='api-labs-start'),
    path('labs/instances/<uuid:pk>/stop/', LabStopAPIView.as_view(), name='api-labs-stop'),
]
