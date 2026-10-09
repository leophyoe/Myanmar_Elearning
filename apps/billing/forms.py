from django import forms
from django.conf import settings
from decimal import Decimal

from apps.courses.forms import INPUT, TEXTAREA
from apps.courses.models import Course
from .models import Payment, PaymentMethod, Promotion, PromotionUsage, UserSubscription


class PaymentSubmitForm(forms.ModelForm):
    """Student hands in proof of payment for a paid course."""

    class Meta:
        model = Payment
        fields = ('method', 'reference', 'receipt', 'note')
        widgets = {
            'method': forms.Select(attrs={'class': INPUT}),
            'reference': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Transaction ID or wallet number'}
            ),
            'receipt': forms.ClearableFileInput(attrs={'class': INPUT}),
            'note': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 3,
                       'placeholder': 'Anything the reviewer should know'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        if active_methods.exists():
            self.fields['method'].choices = [(m.code, m.name) for m in active_methods]

    def clean(self):
        cleaned = super().clean()
        reference = (cleaned.get('reference') or '').strip()
        if not reference and not cleaned.get('receipt'):
            raise forms.ValidationError(
                'Add the transaction reference, upload the receipt, or both.'
            )
        return cleaned

    def clean_receipt(self):
        upload = self.cleaned_data.get('receipt')
        if upload and hasattr(upload, 'size'):
            limit = getattr(settings, 'PAYMENT_RECEIPT_MAX_MB', 10) * 1024 * 1024
            if upload.size > limit:
                raise forms.ValidationError(
                    f'Receipt is {upload.size // (1024 * 1024)} MB — '
                    f'the limit is {getattr(settings, "PAYMENT_RECEIPT_MAX_MB", 10)} MB.'
                )
        return upload


class SubscriptionSubmitForm(forms.ModelForm):
    """Student submits proof of payment for a membership plan."""

    billing_cycle = forms.ChoiceField(
        choices=(
            (UserSubscription.BillingCycle.MONTHLY, 'Monthly Billing'),
            (UserSubscription.BillingCycle.YEARLY, 'Annual Billing (Save ~17%)'),
        ),
        widget=forms.Select(attrs={'class': INPUT}),
        initial=UserSubscription.BillingCycle.MONTHLY,
    )

    class Meta:
        model = Payment
        fields = ('billing_cycle', 'method', 'reference', 'receipt', 'note')
        widgets = {
            'method': forms.Select(attrs={'class': INPUT}),
            'reference': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Transaction ID or wallet phone number'}
            ),
            'receipt': forms.ClearableFileInput(attrs={'class': INPUT}),
            'note': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 3,
                       'placeholder': 'Optional note for administrator review'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        if active_methods.exists():
            self.fields['method'].choices = [(m.code, m.name) for m in active_methods]

    def clean(self):
        cleaned = super().clean()
        reference = (cleaned.get('reference') or '').strip()
        if not reference and not cleaned.get('receipt'):
            raise forms.ValidationError(
                'Add the transaction reference, upload the receipt, or both.'
            )
        return cleaned

    def clean_receipt(self):
        upload = self.cleaned_data.get('receipt')
        if upload and hasattr(upload, 'size'):
            limit = getattr(settings, 'PAYMENT_RECEIPT_MAX_MB', 10) * 1024 * 1024
            if upload.size > limit:
                raise forms.ValidationError(
                    f'Receipt is {upload.size // (1024 * 1024)} MB — '
                    f'the limit is {getattr(settings, "PAYMENT_RECEIPT_MAX_MB", 10)} MB.'
                )
        return upload


class PaymentDecisionForm(forms.Form):
    """Approve or reject a reviewed payment."""

    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTIONS = (ACTION_APPROVE, ACTION_REJECT)

    action = forms.ChoiceField(
        choices=((ACTION_APPROVE, 'Approve'), (ACTION_REJECT, 'Reject')),
        widget=forms.HiddenInput,
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': TEXTAREA, 'rows': 3,
                   'placeholder': 'Required when rejecting — tell the student what went wrong'}
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == self.ACTION_REJECT and not (
            cleaned.get('rejection_reason') or ''
        ).strip():
            self.add_error('rejection_reason', 'Give a reason when rejecting a payment.')
        return cleaned


class PaymentMethodForm(forms.ModelForm):
    """Admin management form for accepted Myanmar payment channels."""
    class Meta:
        model = PaymentMethod
        fields = (
            'name', 'code', 'method_type', 'account_name', 'account_number',
            'qr_image', 'instructions', 'instructions_my', 'display_order', 'is_active'
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. MMQR, KBZPay'}),
            'code': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. mmqr, kbz_pay'}),
            'method_type': forms.Select(attrs={'class': INPUT}),
            'account_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Account holder / merchant name'}),
            'account_number': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Phone number or account number'}),
            'qr_image': forms.ClearableFileInput(attrs={'class': INPUT}),
            'instructions': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'English payment instructions'}),
            'instructions_my': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'မြန်မာဘာသာဖြင့် ငွေပေးချေမှု လမ်းညွှန်'}),
            'display_order': forms.NumberInput(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-cyan-400'}),
        }


class PromotionForm(forms.ModelForm):
    """Form to create or update a Promotion / Coupon code with role-based scoping."""
    class Meta:
        model = Promotion
        fields = (
            'name', 'code', 'description', 'discount_type', 'discount_value',
            'courses', 'start_at', 'end_at', 'usage_limit', 'per_user_limit',
            'minimum_purchase', 'maximum_discount', 'is_active',
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Summer Python Bootcamp 2026'}),
            'code': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. PYTHON20 or THUTA-FREE'}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'Optional internal notes or promotion terms'}),
            'discount_type': forms.Select(attrs={'class': INPUT}),
            'discount_value': forms.NumberInput(attrs={'class': INPUT, 'placeholder': 'e.g. 20 (for 20%) or 10000 (for 10,000 MMK)'}),
            'courses': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 text-sm focus:border-cyan-400 focus:outline-none min-h-[140px]'
            }),
            'start_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': INPUT}),
            'end_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': INPUT}),
            'usage_limit': forms.NumberInput(attrs={'class': INPUT, 'placeholder': 'Leave empty for unlimited total uses'}),
            'per_user_limit': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '1'}),
            'minimum_purchase': forms.NumberInput(attrs={'class': INPUT, 'placeholder': '0'}),
            'maximum_discount': forms.NumberInput(attrs={'class': INPUT, 'placeholder': 'Cap for percentage discount in MMK'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-cyan-400'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Filter courses based on user permissions
        if user and user.is_authenticated:
            if getattr(user, 'is_admin', False):
                self.fields['courses'].queryset = Course.objects.all().order_by('title')
                self.fields['courses'].required = False
                self.fields['courses'].help_text = "Select courses to apply discount, or leave blank to apply to all courses platform-wide (Admin privilege)."
            elif getattr(user, 'is_teacher', False) or getattr(user, 'is_partner', False):
                from apps.partner.views import get_user_partner_institutions
                institutions = get_user_partner_institutions(user)
                teacher_courses = Course.objects.filter(owner=user)
                partner_courses = Course.objects.filter(partner_institution__in=institutions)
                allowed_courses = (teacher_courses | partner_courses).distinct().order_by('title')

                self.fields['courses'].queryset = allowed_courses
                self.fields['courses'].required = True
                self.fields['courses'].help_text = "Select one or more of your authorized courses to apply this promotion."
            else:
                self.fields['courses'].queryset = Course.objects.none()
                self.fields['courses'].required = True
        else:
            self.fields['courses'].queryset = Course.objects.none()

        self.fields['minimum_purchase'].required = False
        self.fields['per_user_limit'].required = False
        self.fields['start_at'].required = False
        self.fields['end_at'].required = False
        self.fields['usage_limit'].required = False
        self.fields['maximum_discount'].required = False
        self.fields['description'].required = False

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError("Coupon code is required.")
        qs = Promotion.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Coupon code '{code}' already exists. Please choose a unique code.")
        return code

    def clean_courses(self):
        courses = self.cleaned_data.get('courses')
        user = self.user
        is_admin = getattr(user, 'is_admin', False)

        if not is_admin:
            if not courses:
                raise forms.ValidationError("You must select at least one course. Only administrators can create platform-wide promotions.")

            from apps.partner.views import get_user_partner_institutions
            institutions = get_user_partner_institutions(user)
            allowed_courses = (Course.objects.filter(owner=user) | Course.objects.filter(partner_institution__in=institutions)).distinct()
            allowed_ids = set(allowed_courses.values_list('id', flat=True))

            for course in courses:
                if course.id not in allowed_ids:
                    raise forms.ValidationError(
                        f"Permission denied: You do not own or manage '{course.title}'."
                    )
        return courses

    def clean(self):
        cleaned = super().clean()
        discount_type = cleaned.get('discount_type')
        discount_value = cleaned.get('discount_value')
        start_at = cleaned.get('start_at')
        end_at = cleaned.get('end_at')

        if cleaned.get('minimum_purchase') is None:
            cleaned['minimum_purchase'] = Decimal('0.00')
        if not cleaned.get('per_user_limit'):
            cleaned['per_user_limit'] = 1

        min_purchase = cleaned.get('minimum_purchase')
        max_discount = cleaned.get('maximum_discount')

        if discount_value is not None:
            if discount_type == Promotion.DiscountType.PERCENTAGE:
                if discount_value <= 0 or discount_value > 100:
                    self.add_error('discount_value', 'Percentage discount must be between 1% and 100%.')
            elif discount_type == Promotion.DiscountType.FIXED:
                if discount_value <= 0:
                    self.add_error('discount_value', 'Fixed discount amount must be greater than 0 MMK.')

        if start_at and end_at and end_at <= start_at:
            self.add_error('end_at', 'Expiration date must be after the start date.')

        if min_purchase is not None and min_purchase < 0:
            self.add_error('minimum_purchase', 'Minimum purchase amount cannot be negative.')

        if max_discount is not None and max_discount <= 0:
            self.add_error('maximum_discount', 'Maximum discount cap must be greater than 0.')

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        user = self.user
        if user and not instance.creator_id:
            instance.creator = user

        if user:
            if getattr(user, 'is_admin', False):
                instance.creator_role = Promotion.CreatorRole.ADMIN
            elif getattr(user, 'is_partner', False):
                from apps.partner.views import get_user_partner_institutions
                institutions = get_user_partner_institutions(user)
                instance.creator_role = Promotion.CreatorRole.PARTNER
                if institutions.exists():
                    instance.partner_institution = institutions.first()
            else:
                instance.creator_role = Promotion.CreatorRole.TEACHER

        if commit:
            instance.save()
            self.save_m2m()
        return instance

