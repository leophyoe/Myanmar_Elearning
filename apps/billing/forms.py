from django import forms
from django.conf import settings

from apps.courses.forms import INPUT, TEXTAREA
from .models import Payment


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
