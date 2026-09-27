from django import forms
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth import get_user_model

from apps.courses.forms import INPUT, TEXTAREA
from apps.users.models import UserRole

User = get_user_model()


class AdminUserCreateForm(UserCreationForm):
    """Provision any role from the administration console."""

    role = forms.ChoiceField(
        choices=UserRole.choices,
        widget=forms.Select(attrs={'class': INPUT}),
        help_text="Students self-register; teachers and admins are created here.",
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role')
        widgets = {
            'username': forms.TextInput(attrs={'class': INPUT, 'autocomplete': 'off'}),
            'first_name': forms.TextInput(attrs={'class': INPUT}),
            'last_name': forms.TextInput(attrs={'class': INPUT}),
            'email': forms.EmailInput(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['password1'].widget.attrs = {'class': INPUT}
        self.fields['password2'].widget.attrs = {'class': INPUT}
        self.fields['password1'].help_text = 'At least 8 characters.'
        self.fields['password2'].help_text = 'Repeat the same password.'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A user with that email address already exists.')
        return email


class AdminUserUpdateForm(forms.ModelForm):
    """Edit identity, role and account status. Password changes use a separate form."""

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': INPUT}),
            'first_name': forms.TextInput(attrs={'class': INPUT}),
            'last_name': forms.TextInput(attrs={'class': INPUT}),
            'email': forms.EmailInput(attrs={'class': INPUT}),
            'role': forms.Select(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        clash = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError('A user with that email address already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        requester = self.request_user
        if requester and requester.pk == self.instance.pk:
            if cleaned.get('role') and cleaned['role'] != UserRole.ADMIN:
                self.add_error('role', 'You cannot change your own role.')
            if cleaned.get('is_active') is False:
                self.add_error('is_active', 'You cannot deactivate your own account.')
            if cleaned.get('username') and cleaned['username'] != requester.username:
                self.add_error('username', 'You cannot rename your own account.')
        return cleaned


class AdminPasswordResetForm(SetPasswordForm):
    """Administrator-initiated password reset for another user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs = {'class': INPUT}
        self.fields['new_password2'].widget.attrs = {'class': INPUT}
        self.fields['new_password1'].help_text = 'At least 8 characters.'
        self.fields['new_password2'].help_text = 'Repeat the same password.'
