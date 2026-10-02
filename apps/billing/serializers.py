from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription, Payment


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            'id', 'name', 'plan_type', 'monthly_price', 'yearly_price',
            'currency', 'description', 'has_all_standard_courses',
            'has_premium_courses', 'has_cyber_range', 'has_capstone_projects',
            'has_priority_support', 'live_class_discount_percent', 'order',
        )


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = (
            'id', 'plan', 'billing_cycle', 'start_date', 'end_date',
            'is_active', 'is_current'
        )

    def get_start_date(self, obj):
        return obj.start_date.isoformat() if obj.start_date else None

    def get_end_date(self, obj):
        return obj.end_date.isoformat() if obj.end_date else None


class SubscriptionCheckoutSerializer(serializers.Serializer):
    plan_type = serializers.ChoiceField(choices=SubscriptionPlan.PlanType.choices)
    billing_cycle = serializers.ChoiceField(
        choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')],
        default='monthly'
    )
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.KBZ_PAY
    )
    reference = serializers.CharField(required=False, allow_blank=True, default='')
    note = serializers.CharField(required=False, allow_blank=True, default='')
