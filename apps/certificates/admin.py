from django.contrib import admin
from .models import Certificate

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_code', 'student_name', 'program_title', 'grade', 'issued_at', 'is_revoked')
    list_filter = ('is_revoked', 'grade')
    search_fields = ('certificate_code', 'student_name', 'student__username')
    readonly_fields = ('issued_at',)

