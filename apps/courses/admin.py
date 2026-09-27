from django.contrib import admin
from .models import Subject, Course, Module, Lesson, Topic, Quiz, Question, Choice, Assignment, AssignmentSubmission, UserProgress

class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1
    fields = ('order', 'code', 'title', 'summary', 'icon_name')

class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    fields = ('order', 'title', 'estimated_minutes', 'has_lab', 'has_quiz')

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'kind', 'order', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'duration_months', 'is_published', 'created_at')
    list_filter = ('subject', 'is_published')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('code', 'title')
    inlines = [LessonInline]

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order', 'has_lab', 'has_quiz')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'content_markdown')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'order')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'passing_percentage')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'prompt', 'quiz', 'points')
    inlines = [ChoiceInline]

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'max_score', 'due_date')

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'score', 'graded_by', 'graded_at')

@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'module', 'lesson', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'course')

