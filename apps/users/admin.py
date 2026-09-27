from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, StudentProfile, TeacherProfile, AdminProfile

class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Student Profile'
    fk_name = 'user'

class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = 'Teacher Profile'
    fk_name = 'user'

class AdminProfileInline(admin.StackedInline):
    model = AdminProfile
    can_delete = False
    verbose_name_plural = 'Administrator Profile'
    fk_name = 'user'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Roles & Security', {'fields': ('role', 'avatar', 'phone_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Roles & Security', {'fields': ('role', 'email', 'avatar', 'phone_number')}),
    )
    inlines = (StudentProfileInline, TeacherProfileInline, AdminProfileInline)

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'batch', 'points', 'rank', 'created_at')
    search_fields = ('student_id', 'user__username', 'user__email')
    list_filter = ('batch',)

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'department', 'created_at')
    search_fields = ('user__username', 'user__email', 'department', 'title')

@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'department', 'created_at')
    search_fields = ('user__username', 'user__email', 'department', 'title')
