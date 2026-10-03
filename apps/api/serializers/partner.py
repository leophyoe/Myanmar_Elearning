from rest_framework import serializers
from apps.partner.models import Institution, PartnerStudent, InstitutionCohort
from apps.courses.models import Course


class PartnerOrganizationSerializer(serializers.ModelSerializer):
    institution_type_display = serializers.CharField(source='get_institution_type_display', read_only=True)

    class Meta:
        model = Institution
        fields = [
            'id', 'organization_id', 'name', 'slug', 'institution_type',
            'institution_type_display', 'email', 'phone', 'website',
            'is_verified', 'mou_signed', 'max_student_seats'
        ]


class PartnerStatsSerializer(serializers.Serializer):
    student_count = serializers.IntegerField()
    staff_count = serializers.IntegerField()
    cohort_count = serializers.IntegerField()
    course_count = serializers.IntegerField()


class PartnerStudentSerializer(serializers.ModelSerializer):
    student_account_id = serializers.CharField(source='student.account_id', read_only=True)
    student_username = serializers.CharField(source='student.username', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)

    class Meta:
        model = PartnerStudent
        fields = [
            'id', 'student_account_id', 'student_username', 'student_name',
            'student_email', 'external_student_id', 'status', 'enrolled_at'
        ]


class PartnerCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'access_type', 'price',
            'partner_price', 'currency', 'status', 'created_at'
        ]


class PartnerInviteStudentRequestSerializer(serializers.Serializer):
    mel_account_id = serializers.CharField(
        required=True,
        help_text="Permanent MEL Account ID (e.g. MEL-00012345) or student email."
    )
    external_student_id = serializers.CharField(
        required=False,
        default='',
        allow_blank=True,
        help_text="Optional local institutional roll number or card ID."
    )
