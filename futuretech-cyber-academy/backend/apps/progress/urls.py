from django.urls import path
from .views import ToggleLessonCompleteView

urlpatterns = [
    path('lessons/<uuid:lesson_id>/toggle/', ToggleLessonCompleteView.as_view(), name='toggle-lesson-complete'),
]

