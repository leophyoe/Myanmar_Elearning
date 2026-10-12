from django.urls import path
from .exam_views import (
    StandaloneExamListView,
    StandaloneExamDetailView,
    StandaloneExamCreateView,
    StandaloneExamUpdateView,
    ExamCheckoutView,
    ExamSessionView,
    ExamSubmitView,
    ExamResultView,
    ExamGradingQueueView,
    ExamGradingDetailView,
)

urlpatterns = [
    # Exam Catalog
    path('', StandaloneExamListView.as_view(), name='standalone-exam-list'),
    path('new/', StandaloneExamCreateView.as_view(), name='standalone-exam-create'),

    # Instructor / Evaluator Manual Grading
    path('grading-queue/', ExamGradingQueueView.as_view(), name='exam-grading-queue'),
    path('grading/<uuid:attempt_id>/', ExamGradingDetailView.as_view(), name='exam-grading-detail'),

    # Specific Exam Lifecycle
    path('<uuid:exam_id>/', StandaloneExamDetailView.as_view(), name='standalone-exam-detail'),
    path('<uuid:exam_id>/edit/', StandaloneExamUpdateView.as_view(), name='standalone-exam-edit'),
    path('<uuid:exam_id>/checkout/', ExamCheckoutView.as_view(), name='exam-checkout'),
    path('<uuid:exam_id>/take/', ExamSessionView.as_view(), name='exam-session'),
    path('<uuid:exam_id>/submit/', ExamSubmitView.as_view(), name='exam-submit'),
    path('<uuid:exam_id>/result/<uuid:attempt_id>/', ExamResultView.as_view(), name='exam-result'),
]

