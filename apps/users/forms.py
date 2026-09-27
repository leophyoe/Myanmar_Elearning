from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, UserRole, StudentProfile

class RegistrationForm(UserCreationForm):
    """
    Public self-registration for students and teacher applicants.

    Students become active immediately. A teacher application is stored with
    `is_active = False` so an administrator has to activate it in the console
    before the account can sign in — self-declared teachers never get a
    Content Studio on their own.
    """

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=64, required=True)
    last_name = forms.CharField(max_length=64, required=True)
    role = forms.ChoiceField(
        choices=[
            (UserRole.STUDENT, 'Student'),
            (UserRole.TEACHER, 'Teacher'),
        ],
        initial=UserRole.STUDENT,
        widget=forms.RadioSelect,
    )
    department = forms.CharField(max_length=128, required=False)
    title = forms.CharField(max_length=128, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = 'At least 8 characters.'
        self.fields['password2'].help_text = 'Repeat the same password.'
        self.fields['role'].widget.attrs = {'class': 'peer sr-only'}
        self.fields['department'].widget.attrs.update({
            'class': 'w-full px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg '
                     'text-white focus:outline-none focus:border-cyan-500 text-sm',
            'placeholder': 'e.g. Computing Department',
        })
        self.fields['title'].widget.attrs.update({
            'class': 'w-full px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg '
                     'text-white focus:outline-none focus:border-cyan-500 text-sm',
            'placeholder': 'e.g. Lecturer',
        })

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with that email address already exists.'
            )
        return email

    @property
    def is_teacher_application(self):
        return self.data.get('role') == UserRole.TEACHER

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = UserRole(self.cleaned_data['role'])
        if user.role == UserRole.TEACHER:
            user.is_active = False
        if commit:
            user.save()
            if user.role == UserRole.TEACHER:
                profile = user.teacher_profile
                changed = False
                if self.cleaned_data.get('department'):
                    profile.department = self.cleaned_data['department']
                    changed = True
                if self.cleaned_data.get('title'):
                    profile.title = self.cleaned_data['title']
                    changed = True
                if changed:
                    profile.save()
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500',
        'placeholder': 'Username or Student ID'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500',
        'placeholder': '••••••••••••'
    }))


class StudentProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ('bio', 'github_url', 'linkedin_url')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'w-full bg-slate-900 border border-slate-700 rounded p-2 text-white'}),
            'github_url': forms.URLInput(attrs={'class': 'w-full bg-slate-900 border border-slate-700 rounded p-2 text-white'}),
            'linkedin_url': forms.URLInput(attrs={'class': 'w-full bg-slate-900 border border-slate-700 rounded p-2 text-white'}),
        }

