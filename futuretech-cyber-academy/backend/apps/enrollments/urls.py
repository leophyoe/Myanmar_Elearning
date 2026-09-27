from django.urls import path
from .views import EnrollCourseView

urlpatterns = [
    path('courses/<slug:slug>/enroll/', EnrollCourseView.as_view(), name='enroll-course'),
]

