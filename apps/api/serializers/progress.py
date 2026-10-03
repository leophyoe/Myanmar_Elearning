from rest_framework import serializers


class CourseProgressSerializer(serializers.Serializer):
    course_id = serializers.UUIDField()
    course_slug = serializers.CharField()
    course_title = serializers.CharField()
    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    progress_percentage = serializers.IntegerField()
    completed_quizzes = serializers.IntegerField()
    total_quizzes = serializers.IntegerField()
    is_completed = serializers.BooleanField()
    eligible_for_certificate = serializers.BooleanField()
    pending_requirements = serializers.ListField(child=serializers.CharField())


class CompleteLessonSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField(required=True)


class ContinueLearningSerializer(serializers.Serializer):
    has_active_course = serializers.BooleanField()
    course_slug = serializers.CharField(allow_null=True)
    course_title = serializers.CharField(allow_null=True)
    course_thumbnail = serializers.CharField(allow_null=True)
    next_lesson_id = serializers.UUIDField(allow_null=True)
    next_lesson_slug = serializers.CharField(allow_null=True)
    next_lesson_title = serializers.CharField(allow_null=True)
    progress_percentage = serializers.IntegerField()
