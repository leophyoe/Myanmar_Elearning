from rest_framework import serializers
from apps.courses.models import Course, Module, Lesson, Subject, Enrollment, UserProgress
from apps.courses.services.access import can_access_course


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'title', 'slug', 'kind', 'icon_name', 'description']


class CourseListSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source='subject.title', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    is_free = serializers.BooleanField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'subject', 'tagline', 'thumbnail',
            'access_type', 'price', 'discount_price', 'currency', 'difficulty',
            'duration_hours', 'instructor_name', 'is_featured', 'is_free',
            'lessons_count', 'exam_available', 'certificate_available',
        ]

    def get_instructor_name(self, obj):
        if obj.instructor:
            return obj.instructor.get_full_name() or obj.instructor.username
        if obj.owner:
            return obj.owner.get_full_name() or obj.owner.username
        return "Myanmar E-Learning Faculty"

    def get_lessons_count(self, obj):
        return Lesson.objects.filter(module__course=obj).count()


class LessonSummarySerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'slug', 'order', 'lesson_type',
            'duration_minutes', 'is_preview', 'is_completed'
        ]

    def get_is_completed(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return UserProgress.objects.filter(user=user, lesson=obj, is_completed=True).exists()
        return False


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'title', 'order', 'description', 'lessons']


class CourseDetailSerializer(CourseListSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    pricing = serializers.SerializerMethodField()
    partner_institution_name = serializers.CharField(source='partner_institution.name', read_only=True, default=None)
    exam_fee = serializers.DecimalField(source='exam_voucher_price', max_digits=10, decimal_places=2, read_only=True)
    learning_outcomes = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    target_audience = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + [
            'description', 'learning_outcomes', 'prerequisites',
            'target_audience', 'partner_institution_name', 'exam_fee',
            'certificate_fee', 'modules', 'is_enrolled', 'pricing'
        ]

    def get_is_enrolled(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return Enrollment.objects.filter(student=user, course=obj, status=Enrollment.Status.ACTIVE).exists()
        return False

    def get_pricing(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        return obj.calculate_price_for_user(user)

    def get_learning_outcomes(self, obj):
        return []

    def get_prerequisites(self, obj):
        return []

    def get_target_audience(self, obj):
        return []


class LessonDetailSerializer(serializers.ModelSerializer):
    """
    Zero-trust lesson detail serializer.
    Protects proprietary video URLs and markdown lecture contents:
    If the lesson is NOT marked as is_preview and the requesting user
    is not enrolled in the course, content and video_url are redacted.
    """
    is_completed = serializers.SerializerMethodField()
    is_accessible = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'slug', 'order', 'lesson_type',
            'duration_minutes', 'is_preview', 'content', 'video_url',
            'attachment_url', 'is_completed', 'is_accessible'
        ]

    def _check_access(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        if obj.is_preview:
            return True
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_admin', False) or user.is_superuser:
            return True
        if obj.module.course.owner == user or obj.module.course.instructor == user:
            return True

        course = obj.module.course
        return can_access_course(course, user) and Enrollment.objects.filter(
            student=user, course=course, status=Enrollment.Status.ACTIVE
        ).exists()

    def get_is_accessible(self, obj):
        return self._check_access(obj)

    def get_is_completed(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if user and user.is_authenticated:
            return UserProgress.objects.filter(user=user, lesson=obj, is_completed=True).exists()
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._check_access(instance):
            data['content'] = (
                "🔒 This lecture content is locked. You must be actively enrolled "
                "in this course to view lesson materials."
            )
            data['video_url'] = None
            data['attachment_url'] = None
        return data


class CoursePricingSerializer(serializers.Serializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_free = serializers.BooleanField()
    pricing_tier = serializers.CharField()
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    reason = serializers.CharField()
