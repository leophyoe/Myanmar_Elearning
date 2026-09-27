from django.urls import path
from .views import CourseListView, CourseDetailView, ModuleDetailView, LessonDetailView, QuizSubmitView

urlpatterns = [
    path('', CourseListView.as_view(), name='course-list'),
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
    path('modules/<uuid:module_id>/', ModuleDetailView.as_view(), name='module-detail'),
    path('lessons/<uuid:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/<uuid:lesson_id>/quiz/submit/', QuizSubmitView.as_view(), name='quiz-submit'),
]

