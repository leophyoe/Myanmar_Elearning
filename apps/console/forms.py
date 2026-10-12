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

    is_verified_instructor = forms.BooleanField(
        required=False,
        label="Verified Instructor",
        help_text="Grant teaching and course authoring privileges.",
        widget=forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
    )
    free_tutorial_approved = forms.BooleanField(
        required=False,
        label="Free Tutorial Approved",
        help_text="Teacher has satisfied the mandatory qualifying free tutorial requirement.",
        widget=forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
    )
    instructor_level = forms.ChoiceField(
        required=False,
        label="Instructor Rank / Level",
        choices=[
            ('teacher', 'Teacher (Entry Rank - Free Tutorials Only)'),
            ('associate_instructor', 'Associate Instructor (Revenue Split: THUTA 60% / Instructor 40%)'),
            ('instructor', 'Instructor (Revenue Split: THUTA 50% / Instructor 50%)'),
            ('professional_instructor', 'Professional Instructor (Revenue Split: THUTA 40% / Instructor 60%)'),
            ('associate', 'Associate Instructor (Legacy)'),
            ('professional', 'Professional Instructor (Legacy)'),
            ('master', 'Master Instructor (Legacy)'),
        ],
        widget=forms.Select(attrs={'class': INPUT}),
        help_text="Pedagogical rank of the instructor."
    )
    department = forms.CharField(
        max_length=128,
        required=False,
        label="Department",
        widget=forms.TextInput(attrs={'class': INPUT}),
    )
    title = forms.CharField(
        max_length=128,
        required=False,
        label="Academic Title",
        widget=forms.TextInput(attrs={'class': INPUT}),
    )
    qualifications = forms.CharField(
        required=False,
        label="Qualifications & Degrees",
        widget=forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
    )

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

        if self.instance and hasattr(self.instance, 'teacher_profile'):
            tp = self.instance.teacher_profile
            self.fields['is_verified_instructor'].initial = tp.is_verified
            self.fields['free_tutorial_approved'].initial = tp.free_tutorial_approved
            self.fields['instructor_level'].initial = tp.level
            self.fields['department'].initial = tp.department
            self.fields['title'].initial = tp.title
            self.fields['qualifications'].initial = tp.qualifications

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

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            from apps.users.models import TeacherProfile, ActiveMode, InstructorLevelHistory
            from django.contrib.auth.models import Group
            if user.role in (UserRole.TEACHER, UserRole.INSTRUCTOR, UserRole.ADMIN) or hasattr(user, 'teacher_profile'):
                tp, _ = TeacherProfile.objects.get_or_create(user=user)
                if 'is_verified_instructor' in self.cleaned_data:
                    tp.is_verified = self.cleaned_data['is_verified_instructor']
                if 'free_tutorial_approved' in self.cleaned_data:
                    tp.free_tutorial_approved = self.cleaned_data['free_tutorial_approved']

                new_level = self.cleaned_data.get('instructor_level')
                if new_level and new_level != tp.level:
                    InstructorLevelHistory.objects.create(
                        user=user,
                        previous_level=tp.level,
                        new_level=new_level,
                        changed_by=self.request_user,
                        reason="Administrative level adjustment via Console User Update Form."
                    )
                    tp.level = new_level

                if 'department' in self.cleaned_data:
                    tp.department = self.cleaned_data.get('department') or ''
                if 'title' in self.cleaned_data:
                    tp.title = self.cleaned_data.get('title') or ''
                if 'qualifications' in self.cleaned_data:
                    tp.qualifications = self.cleaned_data.get('qualifications') or ''
                tp.save()

                if tp.is_verified:
                    grp, _ = Group.objects.get_or_create(name='Instructor')
                    user.groups.add(grp)
                    if user.role in (UserRole.TEACHER, UserRole.ADMIN) and user.active_mode == ActiveMode.STUDENT:
                        user.active_mode = ActiveMode.INSTRUCTOR
                        user.save(update_fields=['active_mode'])
                else:
                    user.groups.filter(name='Instructor').delete()
                    if user.active_mode == ActiveMode.INSTRUCTOR:
                        user.active_mode = ActiveMode.STUDENT
                        user.save(update_fields=['active_mode'])
        return user


class AdminPasswordResetForm(SetPasswordForm):
    """Administrator-initiated password reset for another user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs = {'class': INPUT}
        self.fields['new_password2'].widget.attrs = {'class': INPUT}
        self.fields['new_password1'].help_text = 'At least 8 characters.'
        self.fields['new_password2'].help_text = 'Repeat the same password.'
