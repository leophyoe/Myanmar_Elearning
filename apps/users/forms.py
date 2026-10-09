from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, UserRole, StudentProfile, ActiveMode, InstructorApplication

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
        user.is_active = True
        if user.role == UserRole.TEACHER:
            user.active_mode = ActiveMode.STUDENT
            user._keep_student_mode = True
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


class UnifiedProfileForm(forms.Form):
    first_name = forms.CharField(max_length=64, required=False, label="First Name / နာမည်")
    last_name = forms.CharField(max_length=64, required=False, label="Last Name / မျိုးရိုးအမည်")
    phone_number = forms.CharField(max_length=32, required=False, label="Phone Number / ဖုန်းနံပါတ်")
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Biography / ကိုယ်ရေးအကျဉ်း")
    github_url = forms.URLField(required=False, label="GitHub Portfolio URL")
    linkedin_url = forms.URLField(required=False, label="LinkedIn Profile URL")
    department = forms.CharField(max_length=128, required=False, label="Department / ဌာန")
    title = forms.CharField(max_length=128, required=False, label="Academic Title / ရာထူး")
    qualifications = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Qualifications / ပညာအရည်အချင်း")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        initial = kwargs.get('initial', {})
        if user:
            initial.setdefault('first_name', user.first_name)
            initial.setdefault('last_name', user.last_name)
            initial.setdefault('phone_number', user.phone_number)
            if hasattr(user, 'student_profile'):
                initial.setdefault('bio', user.student_profile.bio)
                initial.setdefault('github_url', user.student_profile.github_url)
                initial.setdefault('linkedin_url', user.student_profile.linkedin_url)
            if hasattr(user, 'teacher_profile'):
                initial.setdefault('department', user.teacher_profile.department)
                initial.setdefault('title', user.teacher_profile.title)
                initial.setdefault('qualifications', user.teacher_profile.qualifications)
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, (forms.TextInput, forms.URLInput)):
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500 text-sm'
                })
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500 text-sm'
                })

    def save(self):
        if not self.user:
            return None
        self.user.first_name = self.cleaned_data.get('first_name', '')
        self.user.last_name = self.cleaned_data.get('last_name', '')
        self.user.phone_number = self.cleaned_data.get('phone_number', '')
        self.user.save()

        student_profile, _ = StudentProfile.objects.get_or_create(user=self.user)
        student_profile.bio = self.cleaned_data.get('bio', '')
        student_profile.github_url = self.cleaned_data.get('github_url', '')
        student_profile.linkedin_url = self.cleaned_data.get('linkedin_url', '')
        student_profile.save()

        if self.user.is_teacher or self.user.is_admin or hasattr(self.user, 'teacher_profile'):
            from .models import TeacherProfile
            teacher_profile, _ = TeacherProfile.objects.get_or_create(user=self.user)
            if 'department' in self.cleaned_data:
                teacher_profile.department = self.cleaned_data.get('department', '')
            if 'title' in self.cleaned_data:
                teacher_profile.title = self.cleaned_data.get('title', '')
            if 'qualifications' in self.cleaned_data:
                teacher_profile.qualifications = self.cleaned_data.get('qualifications', '')
            teacher_profile.save()

        return self.user


class InstructorApplicationForm(forms.ModelForm):
    class Meta:
        model = InstructorApplication
        fields = (
            'department',
            'title',
            'target_subjects',
            'qualifications',
            'teaching_experience',
            'bio',
            'sample_lecture_url',
            'website',
            'linkedin_url',
            'github_url',
        )
        widgets = {
            'department': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'e.g. Faculty of Computing / Information Technology',
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'e.g. Senior Lecturer / Technical Instructor',
            }),
            'target_subjects': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'e.g. Python Programming, Cyber Security, Artificial Intelligence',
            }),
            'qualifications': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'rows': 3,
                'placeholder': 'Degrees, professional certifications, awards...',
            }),
            'teaching_experience': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'rows': 3,
                'placeholder': 'Previous lecturing, workshop facilitation, or technical mentoring...',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'rows': 3,
                'placeholder': 'Brief personal biography, teaching philosophy, and background...',
            }),
            'sample_lecture_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'https://youtube.com/... or https://vimeo.com/... sample lecture link',
            }),
            'website': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'https://yourportfolio.com or blog',
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'https://linkedin.com/in/username',
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 text-sm',
                'placeholder': 'https://github.com/username',
            }),
        }



