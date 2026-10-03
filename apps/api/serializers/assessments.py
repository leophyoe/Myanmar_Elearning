from rest_framework import serializers
from apps.courses.models import Quiz, Question, Choice, QuizAttempt


class ChoiceStudentSerializer(serializers.ModelSerializer):
    """
    Sanitized choice representation for student clients.
    Excludes the correct answer key.
    """
    class Meta:
        model = Choice
        fields = ['id', 'text', 'order']


class QuestionStudentSerializer(serializers.ModelSerializer):
    """
    Sanitized question representation for student clients.
    Excludes correct answer strings and teacher grading explanations.
    """
    choices = ChoiceStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'question_type', 'prompt', 'points', 'order', 'choices']


class AssessmentListSerializer(serializers.ModelSerializer):
    quiz_type_display = serializers.CharField(source='get_quiz_type_display', read_only=True)
    total_questions = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()
    has_passed = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'quiz_type', 'quiz_type_display',
            'time_limit_minutes', 'passing_percentage', 'max_attempts',
            'is_required', 'total_questions', 'attempts_count', 'has_passed',
        ]

    def get_total_questions(self, obj):
        return obj.questions.count()

    def get_attempts_count(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return obj.attempts.filter(student=user).count()
        return 0

    def get_has_passed(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return obj.attempts.filter(student=user, passed=True).exists()
        return False


class AssessmentStartResponseSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()
    quiz_id = serializers.UUIDField()
    quiz_title = serializers.CharField()
    time_limit_minutes = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(allow_null=True)
    questions = QuestionStudentSerializer(many=True)


class AssessmentSubmitRequestSerializer(serializers.Serializer):
    """
    Accepts submission dictionary mapping question IDs to student selections / answers.
    e.g. {"<uuid_or_id>": "<choice_id>", "<uuid_or_id>": ["<c1>", "<c2>"]}
    """
    answers = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Dictionary mapping Question IDs to answers (Choice ID, list of Choice IDs, or text string)."
    )


class AssessmentResultSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField()
    score = serializers.DecimalField(max_digits=5, decimal_places=2)
    points_earned = serializers.IntegerField()
    total_possible_points = serializers.IntegerField()
    passed = serializers.BooleanField()
    passing_percentage = serializers.IntegerField()
    feedback = serializers.CharField()
    completed_at = serializers.DateTimeField()


class QuizAttemptHistorySerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_type = serializers.CharField(source='quiz.quiz_type', read_only=True)
    quiz_type_display = serializers.CharField(source='quiz.get_quiz_type_display', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz_title', 'quiz_type', 'quiz_type_display',
            'score', 'points_earned', 'total_possible_points', 'passed',
            'attempt_number', 'created_at', 'completed_at'
        ]
