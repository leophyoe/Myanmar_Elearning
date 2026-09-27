from django.contrib import admin
from .models import Achievement, StudentAchievement


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'badge_type', 'points', 'criteria_type']
    list_filter = ['badge_type']
    search_fields = ['code', 'title', 'description']


@admin.register(StudentAchievement)
class StudentAchievementAdmin(admin.ModelAdmin):
    list_display = ['student', 'achievement', 'earned_at']
    list_filter = ['achievement__badge_type', 'earned_at']
    search_fields = ['student__email', 'achievement__title']

