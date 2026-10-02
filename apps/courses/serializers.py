from rest_framework import serializers
from .models import Subject, Course, Module, Lesson


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ('id', 'title', 'slug', 'description', 'icon_name', 'kind', 'order')


class LessonSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ('id', 'order', 'title', 'lesson_type', 'estimated_minutes', 'has_lab', 'has_quiz')


class ModuleSummarySerializer(serializers.ModelSerializer):
    lessons = LessonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ('id', 'order', 'code', 'title', 'summary', 'lessons')


class CourseListSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    is_free = serializers.BooleanField(read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Course
        fields = (
            'id', 'title', 'slug', 'subject', 'description', 'level',
            'level_display', 'language', 'is_premium', 'certificate_eligible',
            'duration_months', 'price', 'currency', 'is_free', 'thumbnail',
        )


class CourseDetailSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    modules = ModuleSummarySerializer(many=True, read_only=True)
    is_free = serializers.BooleanField(read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Course
        fields = (
            'id', 'title', 'slug', 'subject', 'description', 'level',
            'level_display', 'language', 'is_premium', 'certificate_eligible',
            'duration_months', 'price', 'currency', 'is_free', 'thumbnail',
            'modules',
        )
