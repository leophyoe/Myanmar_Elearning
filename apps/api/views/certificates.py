from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.certificates.models import Certificate
from apps.api.serializers.certificates import (
    CertificateListSerializer, CertificateDetailSerializer,
    CertificateVerificationResponseSerializer
)
from apps.api.pagination import StandardResultsSetPagination


class MyCertificatesAPIView(APIView):
    """
    GET /api/v1/certificates/my/
    Lists all officially awarded credentials for the authenticated student.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Certificate.objects.filter(student=request.user, is_revoked=False).select_related('course').order_by('-issued_at')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CertificateListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CertificateDetailAPIView(APIView):
    """
    GET /api/v1/certificates/<verification_code>/
    Retrieves full certificate metadata for student or administrative viewing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code):
        cert = get_object_or_404(
            Certificate.objects.select_related('course', 'student'),
            certificate_code=code
        )
        if cert.student != request.user and not (request.user.is_admin or request.user.is_superuser):
            return Response(
                {'error': 'You do not have permission to view this certificate in private mode.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = CertificateDetailSerializer(cert)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicCertificateVerifyAPIView(APIView):
    """
    GET /api/v1/certificates/verify/<verification_code>/
    Public verification endpoint allowing employers and third parties to verify certificate authenticity.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        cert = Certificate.objects.filter(certificate_code=code).first()
        if not cert:
            return Response({
                'is_valid': False,
                'verification_code': code,
                'message': 'No certificate found matching the provided verification code.',
            }, status=status.HTTP_404_NOT_FOUND)

        data = {
            'is_valid': not cert.is_revoked,
            'verification_code': cert.certificate_code,
            'recipient_name': cert.student_name,
            'program_title': cert.program_title or (cert.course.title if cert.course else 'Course Completion'),
            'grade': cert.grade,
            'issued_at': cert.issued_at,
            'is_revoked': cert.is_revoked,
            'institution_name': "Myanmar E-Learning (MEL)",
        }
        serializer = CertificateVerificationResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
