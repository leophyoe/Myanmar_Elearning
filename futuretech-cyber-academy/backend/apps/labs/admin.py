from django.contrib import admin
from .models import (
    LabCategory, Lab, LabVersion, LabInstance, LabAccess,
    LabObjective, LabHint, LabAttachment, LabFlag, LabSubmission,
    ChallengeCategory, Challenge, ChallengeSubmission,
    CTFEvent, CTFEventChallenge, CTFTeam, CTFTeamMember, CTFScore,
    Badge, StudentBadge, ExternalResource
)


class LabObjectiveInline(admin.TabularInline):
    model = LabObjective
    extra = 1
    fields = ('order', 'title', 'points', 'required')


class LabHintInline(admin.TabularInline):
    model = LabHint
    extra = 1
    fields = ('order', 'hint_text', 'penalty_percent')


class LabFlagInline(admin.TabularInline):
    model = LabFlag
    extra = 1
    fields = ('objective', 'flag_type', 'static_flag', 'points')


class LabVersionInline(admin.TabularInline):
    model = LabVersion
    extra = 0
    readonly_fields = ('version_number', 'docker_image', 'created_at')


@admin.register(LabCategory)
class LabCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ('display_order', 'name', 'source_name', 'category', 'type', 'difficulty', 'points', 'access_type', 'is_published')
    list_filter = ('source_name', 'source_type', 'category', 'type', 'difficulty', 'access_type', 'is_published', 'attribution_required')
    search_fields = ('name', 'slug', 'short_description', 'docker_image', 'source_name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [LabObjectiveInline, LabHintInline, LabFlagInline, LabVersionInline]
    fieldsets = (
        ('General Information', {
            'fields': ('name', 'slug', 'short_description', 'description', 'category', 'course', 'module', 'difficulty', 'type', 'points', 'estimated_minutes', 'display_order', 'is_published', 'created_by')
        }),
        ('Source & Attribution Metadata', {
            'fields': ('source_name', 'source_url', 'source_type', 'attribution_required', 'license_name')
        }),
        ('Container Specifications (Allowlisted)', {
            'fields': ('docker_image', 'docker_compose_definition', 'access_type', 'terminal_enabled', 'web_access_enabled')
        }),
        ('Resource Quotas & Isolation', {
            'fields': ('max_runtime_minutes', 'cpu_limit', 'memory_limit_mb', 'storage_limit_mb', 'process_limit')
        }),
    )


@admin.register(LabInstance)
class LabInstanceAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'student', 'lab', 'status', 'started_at', 'expires_at', 'container_id')
    list_filter = ('status', 'lab', 'started_at')
    search_fields = ('uuid', 'student__email', 'student__username', 'container_id')
    readonly_fields = ('uuid', 'started_at', 'last_activity')


@admin.register(LabObjective)
class LabObjectiveAdmin(admin.ModelAdmin):
    list_display = ('lab', 'order', 'title', 'points', 'required')
    list_filter = ('lab', 'required')


@admin.register(LabHint)
class LabHintAdmin(admin.ModelAdmin):
    list_display = ('lab', 'order', 'penalty_percent')
    list_filter = ('lab',)


@admin.register(LabFlag)
class LabFlagAdmin(admin.ModelAdmin):
    list_display = ('lab', 'objective', 'flag_type', 'points')
    list_filter = ('flag_type', 'lab')
    search_fields = ('lab__name', 'static_flag')


@admin.register(LabSubmission)
class LabSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'lab', 'is_correct', 'points_awarded', 'submitted_at')
    list_filter = ('is_correct', 'lab', 'submitted_at')
    search_fields = ('student__email', 'student__username', 'lab__name')


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'points', 'is_active', 'solves_count')
    list_filter = ('category', 'difficulty', 'is_active')
    search_fields = ('title', 'slug', 'description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ChallengeSubmission)
class ChallengeSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'challenge', 'is_correct', 'points_awarded', 'submitted_at')
    list_filter = ('is_correct', 'challenge', 'submitted_at')
    search_fields = ('student__email', 'challenge__title')


@admin.register(CTFEvent)
class CTFEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_time', 'end_time', 'max_participants', 'is_team_event')
    list_filter = ('status', 'is_team_event')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CTFTeam)
class CTFTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'leader', 'score', 'join_code')
    list_filter = ('event',)
    search_fields = ('name', 'leader__username')


@admin.register(CTFScore)
class CTFScoreAdmin(admin.ModelAdmin):
    list_display = ('student', 'points', 'lab_points', 'challenge_points', 'solves_count', 'labs_completed_count')
    search_fields = ('student__email', 'student__username')
    ordering = ('-points',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'points')
    search_fields = ('code', 'title')


@admin.register(StudentBadge)
class StudentBadgeAdmin(admin.ModelAdmin):
    list_display = ('student', 'badge', 'earned_at')
    list_filter = ('badge',)
    search_fields = ('student__username', 'badge__title')


@admin.register(ExternalResource)
class ExternalResourceAdmin(admin.ModelAdmin):
    list_display = ('display_order', 'name', 'source_type', 'attribution', 'category', 'url', 'is_active')
    list_filter = ('source_type', 'attribution', 'is_active', 'category')
    search_fields = ('name', 'slug', 'description', 'attribution', 'tags')
    prepopulated_fields = {'slug': ('name',)}

