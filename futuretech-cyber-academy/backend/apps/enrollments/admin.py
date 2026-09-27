from django.contrib import admin
from .models import Enrollment

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'progress_percentage', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'enrolled_at', 'course')
    search_fields = ('student__email', 'student__username', 'course__title')

