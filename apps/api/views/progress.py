from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.courses.models import Course, Lesson, Enrollment, UserProgress
from apps.courses.services.completion import evaluate_course_completion
from apps.api.serializers.progress import (
    CourseProgressSerializer, CompleteLessonSerializer, ContinueLearningSerializer
)


class CourseProgressAPIView(APIView):
    """
    GET /api/v1/progress/course/<slug>/
    Retrieves holistic pedagogical progress for a student on a course:
    lecture lessons completed, quizzes passed, assignments submitted,
    overall progress percentage, and remaining graduation requirements.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        eval_result = evaluate_course_completion(request.user, course)

        total_lessons = Lesson.objects.filter(module__course=course).count()
        completed_lessons = UserProgress.objects.filter(
            user=request.user, course=course, is_completed=True, lesson__isnull=False
        ).count()
        is_done = eval_result.get('is_completed', eval_result.get('is_complete', False))
        progress_pct = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else (100 if is_done else 0)

        data = {
            'course_id': course.id,
            'course_slug': course.slug,
            'course_title': course.title,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': min(100, progress_pct),
            'completed_quizzes': eval_result.get('quizzes_passed', eval_result.get('completed_quizzes_count', 0)),
            'total_quizzes': eval_result.get('total_required_quizzes', 0),
            'is_completed': is_done,
            'eligible_for_certificate': eval_result.get('eligible_for_certificate', is_done and getattr(course, 'certificate_eligible', True)),
            'pending_requirements': eval_result.get('pending_requirements', []),
        }
        serializer = CourseProgressSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CompleteLessonAPIView(APIView):
    """
    POST /api/v1/progress/complete-lesson/
    Marks a lecture lesson as completed for the authenticated student.
    Enforces active enrollment check.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CompleteLessonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lesson_id = serializer.validated_data['lesson_id']

        lesson = get_object_or_404(
            Lesson.objects.select_related('module__course'),
            pk=lesson_id
        )
        course = lesson.module.course

        # Enforce enrollment check
        enrollment = Enrollment.objects.filter(
            student=request.user, course=course, status=Enrollment.Status.ACTIVE
        ).first()
        if not enrollment and not (request.user.is_admin or request.user.is_superuser):
            return Response(
                {'error': 'You must be enrolled in this course to record progress.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Mark progress
        progress_record, _ = UserProgress.objects.update_or_create(
            user=request.user,
            lesson=lesson,
            defaults={
                'course': course,
                'module': lesson.module,
                'is_completed': True,
                'completed_at': timezone.now(),
            }
        )

        # Re-evaluate course completion
        eval_result = evaluate_course_completion(request.user, course)
        if eval_result.get('is_completed', eval_result.get('is_complete', False)) and enrollment and enrollment.status != Enrollment.Status.COMPLETED:
            enrollment.status = Enrollment.Status.COMPLETED
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['status', 'completed_at'])

        total_lessons = Lesson.objects.filter(module__course=course).count()
        completed_lessons = UserProgress.objects.filter(
            user=request.user, course=course, is_completed=True, lesson__isnull=False
        ).count()
        progress_pct = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 100

        return Response({
            'message': 'Lesson marked as completed.',
            'lesson_id': lesson.id,
            'progress_percentage': min(100, progress_pct),
            'course_completed': eval_result.get('is_completed', eval_result.get('is_complete', False)),
            'eligible_for_certificate': eval_result.get('eligible_for_certificate', False),
        }, status=status.HTTP_200_OK)


class ContinueLearningAPIView(APIView):
    """
    GET /api/v1/progress/continue/
    Shortcut endpoint for mobile and web dashboards: returns the most active
    enrolled course and the next unfinished lesson.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        latest_enrollment = (
            Enrollment.objects.filter(student=request.user, status=Enrollment.Status.ACTIVE)
            .select_related('course')
            .order_by('-updated_at')
            .first()
        )

        if not latest_enrollment:
            return Response({
                'has_active_course': False,
                'course_slug': None,
                'course_title': None,
                'course_thumbnail': None,
                'next_lesson_id': None,
                'next_lesson_slug': None,
                'next_lesson_title': None,
                'progress_percentage': 0,
            }, status=status.HTTP_200_OK)

        course = latest_enrollment.course
        total_lessons = Lesson.objects.filter(module__course=course).count()
        completed_ids = set(
            UserProgress.objects.filter(user=request.user, course=course, is_completed=True)
            .values_list('lesson_id', flat=True)
        )

        next_lesson = (
            Lesson.objects.filter(module__course=course)
            .exclude(id__in=completed_ids)
            .order_by('module__order', 'order')
            .first()
        )

        progress_pct = int((len(completed_ids) / total_lessons * 100)) if total_lessons > 0 else 100
        thumb_url = course.thumbnail.url if course.thumbnail else None

        data = {
            'has_active_course': True,
            'course_slug': course.slug,
            'course_title': course.title,
            'course_thumbnail': thumb_url,
            'next_lesson_id': next_lesson.id if next_lesson else None,
            'next_lesson_slug': next_lesson.slug if next_lesson else None,
            'next_lesson_title': next_lesson.title if next_lesson else "Course Completed",
            'progress_percentage': min(100, progress_pct),
        }
        serializer = ContinueLearningSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
