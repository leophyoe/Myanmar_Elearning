from django.contrib import admin
from .models import (
    Payment, PaymentMethod, Promotion, PromotionUsage,
    SubscriptionPlan, UserSubscription, PartnerRevenueRecord, Invoice
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'method_type', 'account_number', 'display_order', 'is_active')
    list_filter = ('method_type', 'is_active')
    list_editable = ('display_order', 'is_active')
    search_fields = ('name', 'code', 'account_name', 'account_number')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'name', 'discount_type', 'discount_value',
        'creator', 'creator_role', 'usage_count', 'usage_limit',
        'computed_status', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'discount_type', 'creator_role', 'start_at', 'end_at')
    search_fields = ('code', 'name', 'creator__username')
    filter_horizontal = ('courses',)
    raw_id_fields = ('creator', 'partner_institution')
    readonly_fields = ('usage_count', 'created_at', 'updated_at')


@admin.register(PromotionUsage)
class PromotionUsageAdmin(admin.ModelAdmin):
    list_display = (
        'promotion', 'user', 'course', 'original_price',
        'discount_amount', 'final_price', 'created_at'
    )
    list_filter = ('promotion', 'created_at')
    search_fields = ('promotion__code', 'user__username', 'course__title')
    raw_id_fields = ('promotion', 'user', 'course', 'payment')
    readonly_fields = ('created_at',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'course', 'amount', 'original_amount', 'discount_amount',
        'coupon_code', 'currency', 'billing_period', 'method',
        'status', 'platform_fee', 'teacher_amount', 'created_at',
    )
    list_filter = ('status', 'method', 'payment_type', 'billing_period', 'currency')
    search_fields = ('student__username', 'student__email', 'course__title', 'reference', 'coupon_code')
    readonly_fields = ('platform_fee', 'teacher_amount', 'commission_rate', 'reviewed_at')
    raw_id_fields = ('student', 'course', 'plan', 'payment_method', 'promotion', 'reviewed_by')

