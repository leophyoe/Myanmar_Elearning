from django.urls import path
from .views import (
    CourseListView, CourseDetailView, ModuleDetailView, LessonDetailView, QuizSubmitView,
    EnrollView, MyCoursesView,
    ManageHomeView,
    SubjectCreateView, SubjectUpdateView,
    CourseCreateView, CourseUpdateView,
    ModuleCreateView, ModuleUpdateView,
    LessonCreateView, LessonUpdateView, LessonDeleteView,
    LessonCompleteView,
    QuizBuilderView,
    AssignmentCreateView, AssignmentUpdateView, AssignmentDeleteView,
    AssignmentDetailView, AssignmentSubmitView,
    SubmissionListView, SubmissionGradeView,
    LiveSessionListView, LiveSessionCreateView,
    LiveSessionUpdateView, LiveSessionDeleteView,
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
    path('assignments/<uuid:assignment_id>/', AssignmentDetailView.as_view(), name='assignment-detail'),
    path('assignments/<uuid:assignment_id>/submit/', AssignmentSubmitView.as_view(), name='assignment-submit'),

    # Teacher / admin authoring
    path('manage/', ManageHomeView.as_view(), name='manage-home'),
    path('manage/subjects/new/', SubjectCreateView.as_view(), name='subject-create'),
    path('manage/subjects/<uuid:subject_id>/edit/', SubjectUpdateView.as_view(), name='subject-edit'),
    path('manage/courses/new/', CourseCreateView.as_view(), name='course-create'),
    path('manage/courses/<slug:slug>/edit/', CourseUpdateView.as_view(), name='course-edit'),
    path('manage/modules/new/', ModuleCreateView.as_view(), name='module-create'),
    path('manage/modules/<uuid:module_id>/edit/', ModuleUpdateView.as_view(), name='module-edit'),
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

    # Live sessions (teacher / admin)
    path('manage/live/', LiveSessionListView.as_view(), name='live-session-list'),
    path('manage/live/new/', LiveSessionCreateView.as_view(), name='live-session-create'),
    path('manage/live/<uuid:session_id>/edit/', LiveSessionUpdateView.as_view(), name='live-session-edit'),
    path('manage/live/<uuid:session_id>/delete/', LiveSessionDeleteView.as_view(), name='live-session-delete'),

    # Single-segment catch-all must stay last
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
]
