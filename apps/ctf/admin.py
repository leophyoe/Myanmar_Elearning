from django.contrib import admin
from .models import Challenge, FlagSubmission, SolvedChallenge

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'points', 'is_dynamic', 'is_active')
    list_filter = ('category', 'difficulty', 'is_dynamic', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(FlagSubmission)
class FlagSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'is_correct', 'attempt_number', 'ip_address', 'created_at')
    list_filter = ('is_correct', 'challenge__category')
    search_fields = ('user__username', 'challenge__title', 'submitted_flag_clean')
    readonly_fields = ('submitted_flag_clean', 'ip_address')

@admin.register(SolvedChallenge)
class SolvedChallengeAdmin(admin.ModelAdmin):
    list_display = ('user', 'challenge', 'points_awarded', 'solved_at')
    search_fields = ('user__username', 'challenge__title')

