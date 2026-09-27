from django.contrib import admin
from .models import CertificateTemplate, Certificate, CertificateVerification


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'signatory_name', 'academy_title', 'is_default']


class CertificateVerificationInline(admin.TabularInline):
    model = CertificateVerification
    extra = 0
    readonly_fields = ['verified_at', 'ip_address', 'user_agent']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_number', 'student', 'course', 'issued_date', 'status']
    list_filter = ['status', 'issued_date', 'course']
    search_fields = ['certificate_number', 'student__email', 'student__username', 'course__title']
    readonly_fields = ['verification_token', 'issued_date']
    inlines = [CertificateVerificationInline]


@admin.register(CertificateVerification)
class CertificateVerificationAdmin(admin.ModelAdmin):
    list_display = ['certificate', 'verified_at', 'ip_address']
    list_filter = ['verified_at']
    search_fields = ['certificate__certificate_number', 'ip_address']

