from rest_framework import serializers
from apps.certificates.models import Certificate


class CertificateListSerializer(serializers.ModelSerializer):
    verification_code = serializers.CharField(source='certificate_code', read_only=True)
    course_title = serializers.CharField(source='course_name', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id', 'certificate_code', 'verification_code', 'program_title',
            'course_title', 'student_name', 'grade', 'issued_at',
            'completion_date', 'is_revoked'
        ]


class CertificateDetailSerializer(CertificateListSerializer):
    class Meta(CertificateListSerializer.Meta):
        fields = CertificateListSerializer.Meta.fields + ['revocation_reason']


class CertificateVerificationResponseSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
    verification_code = serializers.CharField()
    recipient_name = serializers.CharField()
    program_title = serializers.CharField()
    grade = serializers.CharField()
    issued_at = serializers.DateTimeField()
    is_revoked = serializers.BooleanField()
    institution_name = serializers.CharField(default="Myanmar E-Learning (MEL)")
