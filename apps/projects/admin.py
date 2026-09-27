from django.contrib import admin
from .models import FinalProject, ProjectSubmission

@admin.register(FinalProject)
class FinalProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(ProjectSubmission)
class ProjectSubmissionAdmin(admin.ModelAdmin):
    list_display = ('project', 'student', 'viva_score', 'final_grade', 'evaluated_by')
    search_fields = ('student__username', 'project__title')

