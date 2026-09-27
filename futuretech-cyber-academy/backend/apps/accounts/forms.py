from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, StudentProfile, InstructorProfile
from apps.core.permissions import RoleChoices

class StudentRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500',
        'placeholder': '••••••••••••'
    }), min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500',
        'placeholder': '••••••••••••'
    }))

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'phone')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'student@academy.edu'}),
            'username': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'alex_hacker'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'Alex'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'Rivera'}),
            'phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': '+1 555-0199'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = RoleChoices.STUDENT
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500',
        'placeholder': 'student@academy.edu'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500',
        'placeholder': '••••••••••••'
    }))


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ('bio', 'profile_photo', 'date_of_birth')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white text-sm'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-white text-sm'}),
        }

