from rest_framework import serializers
from apps.courses.models import Course, Enrollment
from apps.users.models import InstructorApplication


class InstructorDashboardStatsSerializer(serializers.Serializer):
    total_courses = serializers.IntegerField()
    published_courses = serializers.IntegerField()
    draft_courses = serializers.IntegerField()
    pending_courses = serializers.IntegerField()
    total_students = serializers.IntegerField()
    instructor_level = serializers.CharField()
    total_recorded_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    total_live_hours = serializers.DecimalField(max_digits=8, decimal_places=2)
    recorded_revenue_share_pct = serializers.IntegerField()
    live_revenue_share_pct = serializers.IntegerField()


class InstructorCourseSerializer(serializers.ModelSerializer):
    enrolled_students_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'status', 'status_display',
            'access_type', 'price', 'currency', 'enrolled_students_count',
            'created_at', 'updated_at'
        ]

    def get_enrolled_students_count(self, obj):
        return Enrollment.objects.filter(course=obj).count()


class InstructorApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    awarded_level_display = serializers.CharField(source='get_awarded_level_display', read_only=True)

    class Meta:
        model = InstructorApplication
        fields = [
            'id', 'department', 'title', 'qualifications',
            'teaching_experience', 'target_subjects', 'sample_lecture_url',
            'status', 'status_display', 'awarded_level', 'awarded_level_display',
            'admin_notes', 'created_at', 'reviewed_at'
        ]
        read_only_fields = ['id', 'status', 'awarded_level', 'admin_notes', 'created_at', 'reviewed_at']
