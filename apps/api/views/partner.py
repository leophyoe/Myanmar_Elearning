from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.partner.models import Institution, PartnerStudent, PartnerMembership, InstitutionCohort
from apps.courses.models import Course
from apps.common.permissions import IsPartner
from apps.api.serializers.partner import (
    PartnerOrganizationSerializer, PartnerStatsSerializer,
    PartnerStudentSerializer, PartnerCourseSerializer,
    PartnerInviteStudentRequestSerializer
)
from apps.api.pagination import StandardResultsSetPagination

User = get_user_model()


def _get_user_institution(user):
    """Retrieves the partner institution associated with the requesting partner user."""
    inst = Institution.objects.filter(contact_person=user).first()
    if not inst:
        membership = PartnerMembership.objects.filter(user=user, status=PartnerMembership.Status.ACTIVE).first()
        if membership:
            inst = membership.institution
    if not inst and (user.is_admin or user.is_superuser):
        inst = Institution.objects.first()
    return inst


class PartnerOrganizationAPIView(APIView):
    """
    GET /api/v1/partner/organization/
    Retrieves institutional identity and accreditation profile.
    """
    permission_classes = [permissions.IsAuthenticated, IsPartner]

    def get(self, request):
        inst = _get_user_institution(request.user)
        if not inst:
            return Response({'error': 'No affiliated partner organization found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PartnerOrganizationSerializer(inst)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PartnerStatsAPIView(APIView):
    """
    GET /api/v1/partner/stats/
    Returns institutional cohort, student, and curriculum metrics.
    """
    permission_classes = [permissions.IsAuthenticated, IsPartner]

    def get(self, request):
        inst = _get_user_institution(request.user)
        if not inst:
            return Response({'error': 'No affiliated partner organization found.'}, status=status.HTTP_404_NOT_FOUND)

        student_count = PartnerStudent.objects.filter(institution=inst, status=PartnerStudent.Status.ACTIVE).count()
        staff_count = PartnerMembership.objects.filter(institution=inst, status=PartnerMembership.Status.ACTIVE).count()
        cohort_count = InstitutionCohort.objects.filter(institution=inst, is_active=True).count()
        course_count = Course.objects.filter(partner_institution=inst).count()

        data = {
            'student_count': student_count,
            'staff_count': staff_count,
            'cohort_count': cohort_count,
            'course_count': course_count,
        }
        serializer = PartnerStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PartnerStudentsAPIView(APIView):
    """
    GET /api/v1/partner/students/
    Lists students enrolled through this institutional partnership.
    """
    permission_classes = [permissions.IsAuthenticated, IsPartner]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        inst = _get_user_institution(request.user)
        if not inst:
            return Response({'error': 'No affiliated partner organization found.'}, status=status.HTTP_404_NOT_FOUND)

        qs = PartnerStudent.objects.filter(institution=inst).select_related('student').order_by('-enrolled_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = PartnerStudentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PartnerCoursesAPIView(APIView):
    """
    GET /api/v1/partner/courses/
    Lists courses managed or affiliated under this partner institution.
    """
    permission_classes = [permissions.IsAuthenticated, IsPartner]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        inst = _get_user_institution(request.user)
        if not inst:
            return Response({'error': 'No affiliated partner organization found.'}, status=status.HTTP_404_NOT_FOUND)

        qs = Course.objects.filter(partner_institution=inst).order_by('-created_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = PartnerCourseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PartnerInviteStudentAPIView(APIView):
    """
    POST /api/v1/partner/invite-student/
    Links an existing Myanmar E-Learning student to this organization using their permanent Account ID or email.
    """
    permission_classes = [permissions.IsAuthenticated, IsPartner]

    def post(self, request):
        inst = _get_user_institution(request.user)
        if not inst:
            return Response({'error': 'No affiliated partner organization found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PartnerInviteStudentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['mel_account_id'].strip()
        ext_id = serializer.validated_data.get('external_student_id', '')

        # Lookup student by account_id, email, or username
        student = User.objects.filter(account_id__iexact=identifier).first()
        if not student:
            student = User.objects.filter(email__iexact=identifier).first()
        if not student:
            student = User.objects.filter(username__iexact=identifier).first()

        if not student:
            return Response({
                'error': f'No MEL student account found matching identifier "{identifier}".'
            }, status=status.HTTP_404_NOT_FOUND)

        partner_student, created = PartnerStudent.objects.get_or_create(
            institution=inst,
            student=student,
            defaults={
                'external_student_id': ext_id,
                'status': PartnerStudent.Status.ACTIVE,
            }
        )

        return Response({
            'message': 'Student affiliated with partner organization.' if created else 'Student is already affiliated with this organization.',
            'partner_student': PartnerStudentSerializer(partner_student).data,
            'is_newly_affiliated': created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
