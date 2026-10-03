from rest_framework import serializers
from apps.courses.models import Enrollment, Lesson, UserProgress
from .courses import CourseListSerializer


class EnrolledCourseSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    progress_percent = serializers.SerializerMethodField()
    completed_lessons_count = serializers.SerializerMethodField()
    total_lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'status', 'created_at', 'completed_at',
            'progress_percent', 'completed_lessons_count', 'total_lessons_count'
        ]

    def get_total_lessons_count(self, obj):
        return Lesson.objects.filter(module__course=obj.course).count()

    def get_completed_lessons_count(self, obj):
        return UserProgress.objects.filter(
            user=obj.student, course=obj.course, is_completed=True, lesson__isnull=False
        ).count()

    def get_progress_percent(self, obj):
        total = self.get_total_lessons_count(obj)
        if total == 0:
            return 100 if obj.status == Enrollment.Status.COMPLETED else 0
        done = self.get_completed_lessons_count(obj)
        return min(100, int((done / total) * 100))


class EnrollActionSerializer(serializers.Serializer):
    course_slug = serializers.SlugField(required=True)


class EnrollmentStatusSerializer(serializers.Serializer):
    is_enrolled = serializers.BooleanField()
    access_granted = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    reason = serializers.CharField()
    enrolled_at = serializers.DateTimeField(allow_null=True)
    can_take_exam = serializers.BooleanField()
    can_get_certificate = serializers.BooleanField()
