from django.contrib import admin
from .models import ActivityLog, SystemLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'ip_address', 'path')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'ip_address', 'path')
    readonly_fields = ('created_at', 'user', 'action', 'ip_address', 'user_agent', 'path', 'metadata')

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'level', 'component', 'message')
    list_filter = ('level', 'component', 'created_at')
    search_fields = ('component', 'message')
    readonly_fields = ('created_at',)

