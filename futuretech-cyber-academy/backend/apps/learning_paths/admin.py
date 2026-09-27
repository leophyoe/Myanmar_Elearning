from django.contrib import admin
from .models import LearningPath, LearningPathCourse, StudentLearningPath


class LearningPathCourseInline(admin.TabularInline):
    model = LearningPathCourse
    extra = 1


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'level', 'estimated_months', 'is_published', 'total_courses']
    list_filter = ['level', 'is_published']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LearningPathCourseInline]


@admin.register(StudentLearningPath)
class StudentLearningPathAdmin(admin.ModelAdmin):
    list_display = ['student', 'learning_path', 'progress_percentage', 'status', 'enrolled_at']
    list_filter = ['status', 'learning_path']
    search_fields = ['student__email', 'learning_path__title']

