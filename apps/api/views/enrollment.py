from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.courses.models import Course, Enrollment
from apps.courses.services.access import (
    can_access_course, can_enroll_course, enroll_student_in_course,
    can_take_course_exam
)
from apps.courses.services.completion import evaluate_course_completion
from apps.api.serializers.enrollment import (
    EnrolledCourseSerializer, EnrollActionSerializer, EnrollmentStatusSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class MyEnrollmentsAPIView(APIView):
    """
    GET /api/v1/enrollments/my/
    Returns all courses the authenticated student is currently enrolled in,
    including completed lessons and dynamic progress percentage.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Enrollment.objects.filter(student=request.user).select_related('course', 'course__subject').order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = EnrolledCourseSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class EnrollCourseAPIView(APIView):
    """
    POST /api/v1/enrollments/enroll/
    Enrolls the authenticated student into a course.
    Zero-trust validation:
    - Verifies student membership and eligibility.
    - If course is free or covered by membership: instantly enrolls.
    - If course requires monetary payment: returns 402 Payment Required.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = EnrollActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course_slug = serializer.validated_data['course_slug']

        course = get_object_or_404(Course, slug=course_slug, status=Course.Status.PUBLISHED)

        # 1. Check existing enrollment
        existing = Enrollment.objects.filter(student=request.user, course=course).first()
        if existing and existing.status == Enrollment.Status.ACTIVE:
            return Response({
                'message': 'You are already actively enrolled in this course.',
                'enrollment': EnrolledCourseSerializer(existing, context={'request': request}).data
            }, status=status.HTTP_200_OK)

        # 2. Check price & access permissions
        pricing = course.calculate_price_for_user(request.user)
        can_enroll, reason = can_enroll_course(request.user, course)

        if not can_enroll and not pricing['is_free']:
            return Response({
                'error': 'payment_required',
                'message': f"Course requires payment or higher membership tier. {reason}",
                'pricing': pricing,
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

        # 3. Create active enrollment
        enrollment = enroll_student_in_course(user=request.user, course=course)
        return Response({
            'message': 'Successfully enrolled in course.',
            'enrollment': EnrolledCourseSerializer(enrollment, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)


class EnrollmentStatusAPIView(APIView):
    """
    GET /api/v1/enrollments/<slug>/status/
    Checks current student enrollment status and exam/certificate eligibility.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
        access_granted = can_access_course(request.user, course)

        exam_ok, _ = can_take_course_exam(request.user, course)
        eval_result = evaluate_course_completion(request.user, course)

        data = {
            'is_enrolled': bool(enrollment and enrollment.status == Enrollment.Status.ACTIVE),
            'access_granted': access_granted,
            'status': enrollment.status if enrollment else None,
            'reason': "Access granted." if access_granted else "Access entitlement required.",
            'enrolled_at': enrollment.created_at if enrollment else None,
            'can_take_exam': exam_ok,
            'can_get_certificate': eval_result['eligible_for_certificate'],
        }
        serializer = EnrollmentStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
