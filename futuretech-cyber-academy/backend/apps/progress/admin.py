from django.contrib import admin
from .models import LessonProgress
from .models import LessonProgress, ModuleProgress

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'completed', 'completed_at', 'time_spent_seconds')
    list_filter = ('completed', 'lesson__module__course')
    search_fields = ('student__email', 'student__username', 'lesson__title')

@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'module', 'overall_progress', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'module__course')
    search_fields = ('student__email', 'student__username', 'module__title')

