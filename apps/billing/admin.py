from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'course', 'amount', 'currency', 'billing_period',
        'status', 'platform_fee', 'teacher_amount', 'created_at',
    )
    list_filter = ('status', 'method', 'billing_period', 'currency')
    search_fields = ('student__username', 'student__email', 'course__title', 'reference')
    readonly_fields = ('platform_fee', 'teacher_amount', 'commission_rate', 'reviewed_at')
    raw_id_fields = ('student', 'reviewed_by')
