from django.urls import path
from .views import CourseListView, CourseDetailView, LessonLearnView, CourseReviewCreateView

urlpatterns = [

    path('', CourseListView.as_view(), name='course-list'),
    path('<slug:slug>/', CourseDetailView.as_view(), name='course-detail'),
    path('<slug:slug>/reviews/create/', CourseReviewCreateView.as_view(), name='course-review-create'),
    path('<slug:course_slug>/learn/<slug:lesson_slug>/', LessonLearnView.as_view(), name='lesson-learn'),
]


