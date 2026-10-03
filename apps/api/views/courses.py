from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.courses.models import Course, Module, Lesson, Subject
from apps.api.serializers.courses import (
    SubjectSerializer, CourseListSerializer, CourseDetailSerializer,
    ModuleSerializer, LessonDetailSerializer, CoursePricingSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class SubjectListAPIView(APIView):
    """
    GET /api/v1/courses/subjects/
    Lists academic and technical subjects.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Subject.ensure_default_subjects()
        subjects = Subject.objects.filter(is_active=True).order_by('order')
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CourseListAPIView(APIView):
    """
    GET /api/v1/courses/
    Lists published courses. Supports query parameters:
      - search: keyword search in title, description, or tagline
      - subject: subject slug
      - access_type: free, starter, standard, premium, partner
      - difficulty: beginner, intermediate, advanced
      - is_featured: true/false
    """
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Course.objects.filter(status=Course.Status.PUBLISHED).select_related('subject', 'owner').order_by('-created_at')

        # Filters
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(tagline__icontains=search) |
                Q(description__icontains=search)
            )

        subject = request.query_params.get('subject')
        if subject:
            qs = qs.filter(subject__slug=subject)

        access_type = request.query_params.get('access_type')
        if access_type:
            qs = qs.filter(access_type=access_type)

        difficulty = request.query_params.get('difficulty')
        if difficulty:
            qs = qs.filter(level=difficulty)

        is_featured = request.query_params.get('is_featured')
        if is_featured in ('true', '1'):
            qs = qs.filter(is_featured=True)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CourseListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class CourseDetailAPIView(APIView):
    """
    GET /api/v1/courses/<slug>/
    Retrieves full details for a course, including personalized enrollment and zero-trust pricing calculations.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        course = get_object_or_404(
            Course.objects.select_related('subject', 'owner', 'partner_institution'),
            slug=slug,
            status=Course.Status.PUBLISHED
        )
        serializer = CourseDetailSerializer(course, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CourseCurriculumAPIView(APIView):
    """
    GET /api/v1/courses/<slug>/curriculum/
    Retrieves module and lesson tree for the course player.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug, status=Course.Status.PUBLISHED)
        modules = course.modules.prefetch_related('lessons').order_by('order')
        serializer = ModuleSerializer(modules, many=True, context={'request': request})
        return Response({
            'course_slug': course.slug,
            'course_title': course.title,
            'modules': serializer.data
        }, status=status.HTTP_200_OK)


class LessonDetailAPIView(APIView):
    """
    GET /api/v1/courses/<slug>/lessons/<lesson_id>/
    Retrieves lecture materials.
    Zero-trust security: Non-preview lessons are locked unless the student is actively enrolled.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug, lesson_id):
        course = get_object_or_404(Course, slug=slug)
        lesson = get_object_or_404(Lesson.objects.select_related('module__course'), pk=lesson_id, module__course=course)
        serializer = LessonDetailSerializer(lesson, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CoursePricingAPIView(APIView):
    """
    GET /api/v1/courses/<slug>/pricing/
    Zero-trust pricing engine. Calculates final price based on:
    - Course list price
    - User's active membership (Starter, Standard, Premium)
    - Flash special discounts
    - Partner organization student affiliation
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        pricing = course.calculate_price_for_user(request.user)
        serializer = CoursePricingSerializer(pricing)
        return Response(serializer.data, status=status.HTTP_200_OK)
