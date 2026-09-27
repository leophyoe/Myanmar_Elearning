from django.urls import path
from .views import (
    CourseListView, CourseDetailView, ModuleDetailView, LessonDetailView, QuizSubmitView,
    EnrollView, MyCoursesView,
    ManageHomeView,
    SubjectCreateView, SubjectUpdateView,
    CourseCreateView, CourseUpdateView,
    ModuleCreateView, ModuleUpdateView,
    LessonCreateView, LessonUpdateView, LessonDeleteView,
)

urlpatterns = [
    path('', CourseListView.as_view(), name='course-list'),
    path('my/', MyCoursesView.as_view(), name='my-courses'),

    # Enrolment
    path('<slug:slug>/enroll/', EnrollView.as_view(), name='enroll'),

    # Content
    path('modules/<uuid:module_id>/', ModuleDetailView.as_view(), name='module-detail'),
    path('lessons/<uuid:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/<uuid:lesson_id>/quiz/submit/', QuizSubmitView.as_view(), name='quiz-submit'),

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

    # Single-segment catch-all must stay last
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
]
