from django.urls import path
from .views import (
    CourseListView, CourseDetailView, ModuleDetailView, LessonDetailView, QuizSubmitView,
    EnrollView, MyCoursesView,
    ManageHomeView,
    SubjectCreateView, SubjectUpdateView,
    CourseCreateView, CourseUpdateView, CourseSubmitReviewView, CoursePublishToggleView,
    CourseReviewListView, CourseReviewActionView,
    ModuleCreateView, ModuleUpdateView, ModuleDeleteView,
    LessonCreateView, LessonUpdateView, LessonDeleteView,
    LessonCompleteView,
    QuizBuilderView,
    AssignmentCreateView, AssignmentUpdateView, AssignmentDeleteView,
    AssignmentDetailView, AssignmentSubmitView,
    AssessmentDetailView, AssessmentSubmitView,
    SubmissionListView, SubmissionGradeView,
    LiveSessionListView, LiveSessionCreateView,
    LiveSessionUpdateView, LiveSessionDeleteView, LiveSessionDetailView,
    LiveSessionJoinView, LiveSessionAttendanceView,
    LiveSessionSyncAttendanceView, LiveSessionRecordingSyncView,
    LiveSessionWebhookView,
    CategoryListAPIView, CourseListAPIView, CourseDetailAPIView,
)
from apps.billing.views import CheckoutView

urlpatterns = [
    path('', CourseListView.as_view(), name='course-list'),
    path('my/', MyCoursesView.as_view(), name='my-courses'),

    # Enrolment
    path('<slug:slug>/enroll/', EnrollView.as_view(), name='enroll'),
    path('<slug:slug>/checkout/', CheckoutView.as_view(), name='checkout'),

    # Content
    path('modules/<uuid:module_id>/', ModuleDetailView.as_view(), name='module-detail'),
    path('lessons/<uuid:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/<uuid:lesson_id>/complete/', LessonCompleteView.as_view(), name='lesson-complete'),
    path('lessons/<uuid:lesson_id>/quiz/submit/', QuizSubmitView.as_view(), name='quiz-submit'),

    # Assessment (students)
    path('<slug:slug>/assessments/<uuid:assessment_id>/', AssessmentDetailView.as_view(), name='assessment-detail'),
    path('<slug:slug>/assessments/<uuid:assessment_id>/submit/', AssessmentSubmitView.as_view(), name='assessment-submit'),
    path('assignments/<uuid:assignment_id>/', AssignmentDetailView.as_view(), name='assignment-detail'),
    path('assignments/<uuid:assignment_id>/submit/', AssignmentSubmitView.as_view(), name='assignment-submit'),

    # Teacher / admin authoring
    path('manage/', ManageHomeView.as_view(), name='manage-home'),
    path('manage/subjects/new/', SubjectCreateView.as_view(), name='subject-create'),
    path('manage/subjects/<uuid:subject_id>/edit/', SubjectUpdateView.as_view(), name='subject-edit'),
    path('manage/courses/new/', CourseCreateView.as_view(), name='course-create'),
    path('manage/courses/<slug:slug>/edit/', CourseUpdateView.as_view(), name='course-edit'),
    path('manage/courses/<slug:slug>/submit-review/', CourseSubmitReviewView.as_view(), name='course-submit-review'),
    path('manage/courses/<slug:slug>/publish/', CoursePublishToggleView.as_view(), name='course-publish'),
    path('manage/review/', CourseReviewListView.as_view(), name='course-review-list'),
    path('manage/review/<slug:slug>/', CourseReviewActionView.as_view(), name='course-review-action'),
    path('manage/modules/new/', ModuleCreateView.as_view(), name='module-create'),
    path('manage/modules/<uuid:module_id>/edit/', ModuleUpdateView.as_view(), name='module-edit'),
    path('manage/modules/<uuid:module_id>/delete/', ModuleDeleteView.as_view(), name='module-delete'),
    path('manage/lessons/new/', LessonCreateView.as_view(), name='lesson-create'),
    path('manage/lessons/<uuid:lesson_id>/edit/', LessonUpdateView.as_view(), name='lesson-edit'),
    path('manage/lessons/<uuid:lesson_id>/delete/', LessonDeleteView.as_view(), name='lesson-delete'),

    # Assessment authoring & grading
    path('manage/lessons/<uuid:lesson_id>/quiz/', QuizBuilderView.as_view(), name='quiz-edit'),
    path('manage/assignments/new/', AssignmentCreateView.as_view(), name='assignment-create'),
    path('manage/assignments/<uuid:assignment_id>/edit/', AssignmentUpdateView.as_view(), name='assignment-edit'),
    path('manage/assignments/<uuid:assignment_id>/delete/', AssignmentDeleteView.as_view(), name='assignment-delete'),
    path('manage/submissions/', SubmissionListView.as_view(), name='submission-list'),
    path('manage/submissions/<uuid:submission_id>/grade/', SubmissionGradeView.as_view(), name='submission-grade'),

    # Live sessions
    path('live/<uuid:session_id>/', LiveSessionDetailView.as_view(), name='live-session-detail'),
    path('live/<uuid:session_id>/join/', LiveSessionJoinView.as_view(), name='live-session-join'),
    path('live/<uuid:session_id>/attendance/', LiveSessionAttendanceView.as_view(), name='live-session-attendance'),
    path('live/<uuid:session_id>/sync-attendance/', LiveSessionSyncAttendanceView.as_view(), name='live-session-sync-attendance'),
    path('live/<uuid:session_id>/recording-sync/', LiveSessionRecordingSyncView.as_view(), name='live-session-recording-sync'),
    path('live/webhook/<str:provider>/', LiveSessionWebhookView.as_view(), name='live-session-webhook'),
    path('live/webhook/', LiveSessionWebhookView.as_view(), {'provider': 'bigbluebutton'}, name='live-session-webhook-default'),
    path('manage/live/', LiveSessionListView.as_view(), name='live-session-list'),
    path('manage/live/new/', LiveSessionCreateView.as_view(), name='live-session-create'),
    path('manage/live/<uuid:session_id>/edit/', LiveSessionUpdateView.as_view(), name='live-session-edit'),
    path('manage/live/<uuid:session_id>/delete/', LiveSessionDeleteView.as_view(), name='live-session-delete'),

    # REST APIs (Mobile / SPA clients)
    path('api/categories/', CategoryListAPIView.as_view(), name='api-categories'),
    path('api/courses/', CourseListAPIView.as_view(), name='api-courses'),
    path('api/courses/<slug:slug>/', CourseDetailAPIView.as_view(), name='api-course-detail'),

    # Single-segment catch-all must stay last
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
]
