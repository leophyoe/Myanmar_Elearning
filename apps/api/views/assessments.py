from datetime import timedelta
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.courses.models import Course, Quiz, Question, QuizAttempt
from apps.courses.services.assessment import (
    check_assessment_attempt_eligibility, grade_assessment_attempt
)
from apps.api.serializers.assessments import (
    AssessmentListSerializer, QuestionStudentSerializer,
    AssessmentSubmitRequestSerializer, AssessmentResultSerializer,
    QuizAttemptHistorySerializer
)
from apps.api.throttling import AssessmentRateThrottle
from apps.api.pagination import StandardResultsSetPagination


class AssessmentListAPIView(APIView):
    """
    GET /api/v1/assessments/?course=<slug>
    Lists assessments (quizzes, practice exams, course exams, practicals) for a course.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        course_slug = request.query_params.get('course')
        qs = Quiz.objects.all().select_related('course')
        if course_slug:
            qs = qs.filter(course__slug=course_slug)

        serializer = AssessmentListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssessmentDetailAPIView(APIView):
    """
    GET /api/v1/assessments/<id>/
    Retrieves assessment guidelines, rules, and passing threshold.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)
        serializer = AssessmentListSerializer(quiz, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssessmentStartAPIView(APIView):
    """
    POST /api/v1/assessments/<id>/start/
    Initiates an assessment attempt.
    Sanitized output: Questions and choices are returned WITHOUT exposing correct answer keys.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AssessmentRateThrottle]

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)

        is_eligible, reason = check_assessment_attempt_eligibility(request.user, quiz)
        if not is_eligible:
            return Response({'error': reason}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        expires_at = now + timedelta(minutes=quiz.time_limit_minutes) if quiz.time_limit_minutes else None
        questions = quiz.questions.prefetch_related('choices').order_by('order')

        data = {
            'quiz_id': quiz.id,
            'quiz_title': quiz.title,
            'time_limit_minutes': quiz.time_limit_minutes,
            'started_at': now,
            'expires_at': expires_at,
            'questions': QuestionStudentSerializer(questions, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)


class AssessmentSubmitAPIView(APIView):
    """
    POST /api/v1/assessments/<id>/submit/
    Submits student responses for auto-grading via grade_assessment_attempt.
    Zero-trust validation:
    - Object-level security verifies student eligibility.
    - Evaluates each answer server-side.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AssessmentRateThrottle]

    def post(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk)

        serializer = AssessmentSubmitRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = serializer.validated_data['answers']
        time_taken = request.data.get('time_taken_seconds', 0)

        try:
            attempt, msg = grade_assessment_attempt(
                assessment=quiz,
                user=request.user,
                submitted_answers=answers,
                time_taken_seconds=time_taken
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        total_possible = sum(q.points for q in quiz.questions.all()) or 100

        result_data = {
            'attempt_id': attempt.id,
            'score': Decimal(str(attempt.score_percentage)),
            'points_earned': attempt.points_earned,
            'total_possible_points': total_possible,
            'passed': attempt.passed,
            'passing_percentage': quiz.passing_percentage,
            'feedback': msg,
            'completed_at': attempt.completed_at,
        }
        return Response(AssessmentResultSerializer(result_data).data, status=status.HTTP_200_OK)


class MyQuizAttemptsAPIView(APIView):
    """
    GET /api/v1/assessments/my-attempts/
    Lists assessment history and scores for the authenticated student.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = QuizAttempt.objects.filter(student=request.user).select_related('quiz').order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = QuizAttemptHistorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class MyQuizAttemptsAPIView(APIView):
    """
    GET /api/v1/assessments/my-attempts/
    Lists assessment history and scores for the authenticated student.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = QuizAttempt.objects.filter(student=request.user).select_related('quiz').order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = QuizAttemptHistorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
