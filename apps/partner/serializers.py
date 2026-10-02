from rest_framework import serializers
from .models import Institution, InstitutionCohort, CohortStudent


class InstitutionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_institution_type_display', read_only=True)

    class Meta:
        model = Institution
        fields = (
            'id', 'name', 'slug', 'institution_type', 'type_display',
            'email', 'phone', 'address', 'website', 'is_verified',
            'mou_signed', 'max_student_seats',
        )


class CohortStudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='student.username', read_only=True)
    email = serializers.CharField(source='student.email', read_only=True)
    account_id = serializers.CharField(source='student.account_id', read_only=True)

    class Meta:
        model = CohortStudent
        fields = ('id', 'username', 'email', 'account_id', 'student_id_number', 'joined_at')


class InstitutionCohortSerializer(serializers.ModelSerializer):
    students_count = serializers.IntegerField(source='students.count', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = InstitutionCohort
        fields = (
            'id', 'institution', 'name', 'code', 'course', 'course_title',
            'start_date', 'end_date', 'is_active', 'students_count'
        )
