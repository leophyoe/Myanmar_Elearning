from django.urls import path
from .views import (
    StudentDashboardView,
    InstructorDashboardView,
    AcademyAdminDashboardView,
    CourseCreateStep1View,
    CourseCreateStep2View,
    CourseCreateStep3View,
    CourseCreateStep4View,
    CourseCreateStep5ReviewView,
    CoursePublishToggleView,
)

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('instructor/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('instructor/courses/new/', CourseCreateStep1View.as_view(), name='instructor-course-step1'),
    path('instructor/courses/<slug:slug>/step2-modules/', CourseCreateStep2View.as_view(), name='instructor-course-step2'),
    path('instructor/courses/<slug:slug>/step3-lessons/', CourseCreateStep3View.as_view(), name='instructor-course-step3'),
    path('instructor/courses/<slug:slug>/step4-resources/', CourseCreateStep4View.as_view(), name='instructor-course-step4'),
    path('instructor/courses/<slug:slug>/step5-review/', CourseCreateStep5ReviewView.as_view(), name='instructor-course-step5'),
    path('instructor/courses/<slug:slug>/toggle-publish/', CoursePublishToggleView.as_view(), name='instructor-course-publish'),
    path('admin-dashboard/', AcademyAdminDashboardView.as_view(), name='academy-admin-dashboard'),
]

