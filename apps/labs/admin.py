from django.contrib import admin
from .models import LabTemplate, Lab, LabInstance, LabNetwork

@admin.register(LabTemplate)
class LabTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'image_name', 'cpu_limit', 'mem_limit', 'pids_limit', 'default_duration_minutes')
    list_filter = ('category',)
    search_fields = ('name', 'image_name')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ('title', 'template', 'difficulty', 'lab_type', 'points', 'estimated_minutes')
    list_filter = ('difficulty', 'lab_type', 'template__category')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}

@admin.register(LabInstance)
class LabInstanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'lab', 'user', 'status', 'target_ip', 'started_at', 'expires_at')
    list_filter = ('status', 'lab__template__category')
    search_fields = ('id', 'user__username', 'lab__title', 'target_ip')
    readonly_fields = ('container_id', 'dynamic_flag', 'flag_hash')

@admin.register(LabNetwork)
class LabNetworkAdmin(admin.ModelAdmin):
    list_display = ('subnet', 'gateway', 'is_internal_only', 'docker_network_id')

