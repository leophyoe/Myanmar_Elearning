from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import (
    User,
    UserRoleAssignment,
    StudentProfile,
    TeacherProfile,
    AdminProfile,
    InstructorApplication,
)

class UserRoleAssignmentInline(admin.TabularInline):
    model = UserRoleAssignment
    extra = 1
    fk_name = 'user'


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
    list_display = ('account_id', 'username', 'email', 'role', 'active_mode', 'is_associate', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'active_mode', 'is_associate', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('account_id', 'username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    readonly_fields = ('account_id', 'created_at', 'updated_at')
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Roles & Identification', {
            'fields': ('account_id', 'role', 'active_mode', 'is_associate', 'associate_awarded_at', 'avatar', 'phone_number')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Roles & Identification', {
            'fields': ('role', 'active_mode', 'email', 'avatar', 'phone_number')
        }),
    )
    inlines = (UserRoleAssignmentInline, StudentProfileInline, TeacherProfileInline, AdminProfileInline)


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active', 'assigned_by', 'assigned_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__email', 'user__account_id')
    raw_id_fields = ('user', 'assigned_by')


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'batch', 'points', 'rank', 'created_at')
    search_fields = ('student_id', 'user__username', 'user__email')
    list_filter = ('batch',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'department', 'level', 'is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'department', 'title')
    list_filter = ('level', 'is_verified', 'department')


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'department', 'created_at')
    search_fields = ('user__username', 'user__email', 'department', 'title')


@admin.register(InstructorApplication)
class InstructorApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'title', 'awarded_level', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status', 'awarded_level', 'department')
    search_fields = ('user__username', 'user__email', 'qualifications', 'teaching_experience')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'reviewed_by')
    actions = ['approve_application', 'reject_application']

    @admin.action(description="Approve selected instructor applications")
    def approve_application(self, request, queryset):
        for app in queryset.filter(status=InstructorApplication.Status.PENDING):
            app.status = InstructorApplication.Status.APPROVED
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            # Promote applicant
            user = app.user
            user.role = UserRole.TEACHER
            user.active_mode = ActiveMode.INSTRUCTOR
            user.save(update_fields=['role', 'active_mode'])
            user.add_role('instructor', assigned_by=request.user)
            tp, _ = TeacherProfile.objects.get_or_create(user=user)
            tp.level = app.awarded_level
            tp.department = app.department
            tp.title = app.title
            tp.qualifications = app.qualifications
            tp.is_verified = True
            tp.save()
        self.message_user(request, "Selected instructor applications have been approved.")

    @admin.action(description="Reject selected instructor applications")
    def reject_application(self, request, queryset):
        queryset.filter(status=InstructorApplication.Status.PENDING).update(
            status=InstructorApplication.Status.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, "Selected instructor applications have been rejected.")
