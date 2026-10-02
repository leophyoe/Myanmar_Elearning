from django.contrib import admin
from .models import Institution, InstitutionCohort, CohortStudent


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution_type', 'contact_person', 'email', 'is_verified', 'mou_signed', 'max_student_seats')
    list_filter = ('institution_type', 'is_verified', 'mou_signed')
    search_fields = ('name', 'email', 'phone')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(InstitutionCohort)
class InstitutionCohortAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'institution', 'course', 'start_date', 'end_date', 'is_active')
    list_filter = ('institution', 'is_active')
    search_fields = ('name', 'code', 'institution__name')


@admin.register(CohortStudent)
class CohortStudentAdmin(admin.ModelAdmin):
    list_display = ('student', 'cohort', 'student_id_number', 'joined_at')
    list_filter = ('cohort__institution', 'cohort')
    search_fields = ('student__username', 'student__email', 'student_id_number')
