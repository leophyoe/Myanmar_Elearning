from django.urls import path, include
from .api_views import (
    PlatformStatsAPIView,
    CourseListJsonView,
    CourseDetailJsonView,
    EnrollmentListJsonView,
    CourseModulesJsonView,
    ModuleLessonsJsonView,
    LessonStartJsonView,
    LessonCompleteJsonView,
    QuizStartJsonView,
    QuizSubmitJsonView,
    AssignmentSubmitJsonView,
    ExamStartJsonView,
    ExamSubmitJsonView,
    StudentCoursesJsonView,
    StudentProgressJsonView,
    StudentCourseProgressJsonView,
    StudentModuleProgressJsonView,
    StudentGradesJsonView,
    StudentCertificateEligibilityJsonView
)

try:
    from rest_framework.routers import DefaultRouter
    from .api_views import (
        AuthStatusAPIView, UserViewSet, CourseViewSet,
        CourseModuleViewSet, LessonViewSet, EnrollmentViewSet,
        LessonProgressViewSet,
        QuizViewSet, QuizAttemptViewSet,
        AssignmentViewSet, AssignmentSubmissionViewSet,
        ExamViewSet, ExamAttemptViewSet,
        LearningPathViewSet, CertificateViewSet,
        AchievementViewSet, NotificationViewSet, AnnouncementViewSet,
        StudentCoursesAPIView, StudentProgressAPIView,
        StudentCourseProgressAPIView, StudentModuleProgressAPIView,
        StudentGradesAPIView, StudentCertificateEligibilityAPIView
    )

    router = DefaultRouter()
    router.register(r'users', UserViewSet, basename='api-user')
    router.register(r'courses', CourseViewSet, basename='api-course')
    router.register(r'modules', CourseModuleViewSet, basename='api-module')
    router.register(r'lessons', LessonViewSet, basename='api-lesson')
    router.register(r'enrollments', EnrollmentViewSet, basename='api-enrollment')
    router.register(r'progress', LessonProgressViewSet, basename='api-progress')

    # Phase 2
    router.register(r'quizzes', QuizViewSet, basename='api-quiz')
    router.register(r'quiz-attempts', QuizAttemptViewSet, basename='api-quiz-attempt')
    router.register(r'assignments', AssignmentViewSet, basename='api-assignment')
    router.register(r'submissions', AssignmentSubmissionViewSet, basename='api-submission')
    router.register(r'exams', ExamViewSet, basename='api-exam')
    router.register(r'exam-attempts', ExamAttemptViewSet, basename='api-exam-attempt')
    router.register(r'learning-paths', LearningPathViewSet, basename='api-learning-path')
    router.register(r'certificates', CertificateViewSet, basename='api-certificate')
    router.register(r'achievements', AchievementViewSet, basename='api-achievement')
    router.register(r'notifications', NotificationViewSet, basename='api-notification')
    router.register(r'announcements', AnnouncementViewSet, basename='api-announcement')

    # Phase 3 Cyber Range
    from apps.labs.api_views import (
        LabViewSet, LabInstanceViewSet, ChallengeViewSet,
        CTFEventViewSet, CTFScoreViewSet
    )
    router.register(r'labs', LabViewSet, basename='api-lab')
    router.register(r'lab-instances', LabInstanceViewSet, basename='api-lab-instance')
    router.register(r'challenges', ChallengeViewSet, basename='api-challenge')
    router.register(r'ctf-events', CTFEventViewSet, basename='api-ctf-event')
    router.register(r'ctf-scores', CTFScoreViewSet, basename='api-ctf-score')


    urlpatterns = [
        path('auth/', AuthStatusAPIView.as_view(), name='api-auth-status'),
        path('stats/', PlatformStatsAPIView.as_view(), name='api-platform-stats'),
        path('student/courses/', StudentCoursesAPIView.as_view(), name='api-student-courses'),
        path('student/progress/', StudentProgressAPIView.as_view(), name='api-student-progress'),
        path('student/courses/<str:lookup>/progress/', StudentCourseProgressAPIView.as_view(), name='api-student-course-progress'),
        path('student/modules/<str:pk>/progress/', StudentModuleProgressAPIView.as_view(), name='api-student-module-progress'),
        path('student/grades/', StudentGradesAPIView.as_view(), name='api-student-grades'),
        path('student/certificate-eligibility/', StudentCertificateEligibilityAPIView.as_view(), name='api-student-certificate-eligibility'),
        path('', include(router.urls)),
    ]
except ImportError:
    urlpatterns = [
        path('stats/', PlatformStatsAPIView.as_view(), name='api-platform-stats'),
        path('courses/', CourseListJsonView.as_view(), name='api-course-list'),
        path('courses/<slug:slug>/', CourseDetailJsonView.as_view(), name='api-course-detail'),
        path('courses/<str:slug>/', CourseDetailJsonView.as_view(), name='api-course-detail'),
        path('courses/<str:lookup>/modules/', CourseModulesJsonView.as_view(), name='api-course-modules'),
        path('modules/<str:pk>/lessons/', ModuleLessonsJsonView.as_view(), name='api-module-lessons'),
        path('lessons/<str:pk>/start/', LessonStartJsonView.as_view(), name='api-lesson-start'),
        path('lessons/<str:pk>/complete/', LessonCompleteJsonView.as_view(), name='api-lesson-complete'),
        path('quizzes/<str:pk>/start/', QuizStartJsonView.as_view(), name='api-quiz-start'),
        path('quizzes/<str:pk>/submit/', QuizSubmitJsonView.as_view(), name='api-quiz-submit'),
        path('assignments/<str:pk>/submit/', AssignmentSubmitJsonView.as_view(), name='api-assignment-submit'),
        path('exams/<str:pk>/start/', ExamStartJsonView.as_view(), name='api-exam-start'),
        path('exams/<str:pk>/submit/', ExamSubmitJsonView.as_view(), name='api-exam-submit'),
        path('student/courses/', StudentCoursesJsonView.as_view(), name='api-student-courses'),
        path('student/progress/', StudentProgressJsonView.as_view(), name='api-student-progress'),
        path('student/courses/<str:lookup>/progress/', StudentCourseProgressJsonView.as_view(), name='api-student-course-progress'),
        path('student/modules/<str:pk>/progress/', StudentModuleProgressJsonView.as_view(), name='api-student-module-progress'),
        path('student/grades/', StudentGradesJsonView.as_view(), name='api-student-grades'),
        path('student/certificate-eligibility/', StudentCertificateEligibilityJsonView.as_view(), name='api-student-certificate-eligibility'),
        path('enrollments/', EnrollmentListJsonView.as_view(), name='api-enrollment-list'),
        path('stats/', PlatformStatsAPIView.as_view(), name='api-platform-stats'),
    ]

