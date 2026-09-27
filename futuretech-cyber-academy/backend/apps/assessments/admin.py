from django.contrib import admin
from .models import (
    QuestionBank, Quiz, Question, QuestionOption, QuizAttempt, QuizAnswer,
    Assignment, AssignmentSubmission, AssignmentFeedback,
    Exam, ExamQuestion, ExamOption, ExamAttempt, ExamAnswer,
    PracticalLabTask, AssessmentWeight, FinalProject, ProjectSubmission
)


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'quiz', 'question_type', 'points', 'order']
    list_filter = ['question_type', 'quiz__course']
    search_fields = ['question_text']
    inlines = [QuestionOptionInline]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'lesson', 'passing_score', 'time_limit_minutes', 'is_published']
    list_filter = ['course', 'is_published']
    search_fields = ['title', 'description']
    inlines = [QuestionInline]


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'difficulty', 'created_by']
    list_filter = ['category', 'difficulty']
    search_fields = ['title']


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'quiz', 'attempt_number', 'score', 'percentage', 'passed', 'is_completed', 'started_at']
    list_filter = ['passed', 'is_completed', 'quiz__course']
    search_fields = ['student__email', 'quiz__title']


class AssignmentFeedbackInline(admin.StackedInline):
    model = AssignmentFeedback
    extra = 0


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'due_date', 'max_score', 'status']
    list_filter = ['course', 'status']
    search_fields = ['title']


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'student', 'status', 'version', 'submitted_at']
    list_filter = ['status', 'assignment__course']
    search_fields = ['student__email', 'assignment__title']
    inlines = [AssignmentFeedbackInline]


class ExamOptionInline(admin.TabularInline):
    model = ExamOption
    extra = 4


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'exam', 'question_type', 'points', 'order']
    list_filter = ['exam__course', 'question_type']
    inlines = [ExamOptionInline]


class ExamQuestionInline(admin.StackedInline):
    model = ExamQuestion
    extra = 1


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'exam_type', 'duration_minutes', 'passing_score', 'is_published']
    list_filter = ['course', 'exam_type', 'is_published']
    inlines = [ExamQuestionInline]


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'attempt_number', 'score', 'percentage', 'passed', 'is_completed', 'started_at']
    list_filter = ['passed', 'is_completed', 'exam__course']
    search_fields = ['student__email', 'exam__title']


@admin.register(PracticalLabTask)
class PracticalLabTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'exam', 'docker_template_id', 'points', 'verification_method']


@admin.register(AssessmentWeight)
class AssessmentWeightAdmin(admin.ModelAdmin):
    list_display = ['course', 'assignments_weight', 'quizzes_weight', 'labs_weight', 'module_exams_weight', 'practical_exam_weight', 'final_project_weight']


@admin.register(FinalProject)
class FinalProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'max_score', 'passing_score', 'is_required', 'is_published']
    list_filter = ['course', 'is_published', 'is_required']
    search_fields = ['title', 'title_en', 'title_my', 'description']


@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(admin.ModelAdmin):
    list_display = ['project', 'student', 'status', 'score', 'presentation_score', 'submitted_at', 'graded_at']
    list_filter = ['status', 'project__course']
    search_fields = ['student__email', 'project__title', 'title']

