from django.urls import path
from .views import (
    QuizDetailView, QuizTakeView, QuizSubmitView, QuizResultView,
    AssignmentDetailView, AssignmentSubmitView, InstructorGradingQueueView, InstructorGradeSubmissionView,
    ExamPortalView, ExamDetailView, ExamTakeView, ExamSubmitView, ExamResultView,
    StudentGradebookView, InstructorCourseGradebookView
)

app_name = 'assessments'

urlpatterns = [
    # Quizzes
    path('quizzes/<uuid:pk>/', QuizDetailView.as_view(), name='quiz-detail'),
    path('quizzes/<uuid:pk>/take/', QuizTakeView.as_view(), name='quiz-take'),
    path('quizzes/attempts/<uuid:pk>/submit/', QuizSubmitView.as_view(), name='quiz-submit'),
    path('quizzes/attempts/<uuid:pk>/result/', QuizResultView.as_view(), name='quiz-result'),

    # Assignments
    path('assignments/<uuid:pk>/', AssignmentDetailView.as_view(), name='assignment-detail'),
    path('assignments/<uuid:pk>/submit/', AssignmentSubmitView.as_view(), name='assignment-submit'),
    path('grading/assignments/', InstructorGradingQueueView.as_view(), name='grading-queue'),
    path('grading/assignments/<uuid:pk>/', InstructorGradeSubmissionView.as_view(), name='instructor-grade-submission'),

    # Examinations
    path('exams/', ExamPortalView.as_view(), name='exam-portal'),
    path('exams/<uuid:pk>/', ExamDetailView.as_view(), name='exam-detail'),
    path('exams/<uuid:pk>/take/', ExamTakeView.as_view(), name='exam-take'),
    path('exams/attempts/<uuid:pk>/submit/', ExamSubmitView.as_view(), name='exam-submit'),
    path('exams/attempts/<uuid:pk>/result/', ExamResultView.as_view(), name='exam-result'),

    # Gradebook
    path('gradebook/', StudentGradebookView.as_view(), name='student-gradebook'),
    path('courses/<slug:course_slug>/gradebook/', InstructorCourseGradebookView.as_view(), name='instructor-gradebook'),
]

