from rest_framework import serializers
from apps.billing.models import SubscriptionPlan, UserSubscription, Payment, Invoice


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    annual_savings = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    features = serializers.SerializerMethodField()
    has_cyber_lab_access = serializers.BooleanField(source='has_cyber_range', read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'plan_type', 'monthly_price', 'yearly_price',
            'currency', 'annual_savings', 'description', 'features',
            'has_all_standard_courses', 'has_premium_courses',
            'has_cyber_lab_access', 'is_active', 'order'
        ]

    def get_features(self, obj):
        feats = []
        if obj.has_all_standard_courses:
            feats.append("All standard courses")
        if obj.has_premium_courses:
            feats.append("Premium course library")
        if obj.has_cyber_range:
            feats.append("Cyber Range sandbox access")
        if obj.has_capstone_projects:
            feats.append("Capstone projects")
        if obj.has_priority_support:
            feats.append("Priority academic support")
        if obj.live_class_discount_percent > 0:
            feats.append(f"{obj.live_class_discount_percent}% live class discount")
        return feats


class UserSubscriptionDetailSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_type = serializers.CharField(source='plan.plan_type', read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'plan_type', 'plan_name', 'billing_cycle',
            'start_date', 'end_date', 'is_active', 'is_current'
        ]


class SubscribeActionSerializer(serializers.Serializer):
    plan_type = serializers.ChoiceField(choices=SubscriptionPlan.PlanType.choices)
    billing_cycle = serializers.ChoiceField(
        choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')],
        default='monthly'
    )
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.KBZ_PAY
    )
    reference = serializers.CharField(required=False, default='', allow_blank=True)
    note = serializers.CharField(required=False, default='', allow_blank=True)


class PaymentHistorySerializer(serializers.ModelSerializer):
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    invoice_id = serializers.SerializerMethodField()
    item_title = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'payment_type', 'payment_type_display', 'item_title',
            'amount', 'currency', 'method', 'status', 'status_display',
            'reference', 'invoice_id', 'created_at'
        ]

    def get_invoice_id(self, obj):
        if hasattr(obj, 'invoice') and obj.invoice:
            return str(obj.invoice.id)
        return None

    def get_item_title(self, obj):
        if obj.course:
            return obj.course.title
        if obj.plan:
            return f"{obj.plan.name} Membership"
        return "Educational Service"


class InvoiceDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_account_id = serializers.CharField(source='student.account_id', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'status', 'status_display',
            'student_name', 'student_account_id', 'billing_name', 'billing_email',
            'subtotal', 'tax', 'total', 'currency', 'items',
            'issued_date', 'paid_at', 'notes', 'created_at'
        ]
