from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.courses.models import Course, Enrollment
from apps.users.models import InstructorApplication, TeacherProfile
from apps.common.permissions import IsTeacher
from apps.api.serializers.instructor import (
    InstructorDashboardStatsSerializer, InstructorCourseSerializer,
    InstructorApplicationSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class InstructorDashboardStatsAPIView(APIView):
    """
    GET /api/v1/instructor/stats/
    Provides teaching metrics and pedagogical statistics for authenticated instructors.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def get(self, request):
        courses = Course.objects.filter(owner=request.user)

        published = courses.filter(status=Course.Status.PUBLISHED).count()
        draft = courses.filter(status=Course.Status.DRAFT).count()
        pending = courses.filter(status=Course.Status.PENDING_REVIEW).count()
        total_students = Enrollment.objects.filter(course__in=courses).count()

        tp, _ = TeacherProfile.objects.get_or_create(user=request.user)

        data = {
            'total_courses': courses.count(),
            'published_courses': published,
            'draft_courses': draft,
            'pending_courses': pending,
            'total_students': total_students,
            'instructor_level': tp.get_level_display(),
            'total_recorded_hours': tp.total_recorded_hours,
            'total_live_hours': tp.total_live_hours,
            'recorded_revenue_share_pct': tp.recorded_revenue_share_pct,
            'live_revenue_share_pct': tp.live_revenue_share_pct,
        }
        serializer = InstructorDashboardStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InstructorCoursesAPIView(APIView):
    """
    GET /api/v1/instructor/courses/
    Lists courses owned or instructed by the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        courses = Course.objects.filter(owner=request.user)
        qs = courses.order_by('-created_at')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = InstructorCourseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class InstructorCourseSubmitReviewAPIView(APIView):
    """
    POST /api/v1/instructor/courses/<id>/submit-review/
    Submits a draft course for administrative quality audit and publishing review.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        if course.owner != request.user and course.instructor != request.user and not request.user.is_admin:
            return Response(
                {'error': 'You do not have permission to manage this course.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if course.status != Course.Status.DRAFT:
            return Response(
                {'error': f'Course is already in {course.get_status_display()} state.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        course.status = Course.Status.PENDING
        course.save(update_fields=['status'])

        return Response({
            'message': 'Course successfully submitted for administrator review.',
            'status': course.status,
        }, status=status.HTTP_200_OK)


class InstructorApplicationAPIView(APIView):
    """
    GET /api/v1/instructor/apply/
    POST /api/v1/instructor/apply/
    Allows educators and teachers to apply for official Myanmar E-Learning Instructor certification.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        app = InstructorApplication.objects.filter(user=request.user).first()
        if not app:
            return Response({'has_application': False, 'application': None}, status=status.HTTP_200_OK)
        return Response({
            'has_application': True,
            'application': InstructorApplicationSerializer(app).data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        existing = InstructorApplication.objects.filter(user=request.user, status=InstructorApplication.Status.PENDING).first()
        if existing:
            return Response(
                {'error': 'You already have an instructor application pending review.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = InstructorApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app = serializer.save(user=request.user)

        return Response({
            'message': 'Instructor application submitted successfully for review.',
            'application': InstructorApplicationSerializer(app).data
        }, status=status.HTTP_201_CREATED)
