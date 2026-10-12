from decimal import Decimal
from django import forms
from django.db import models
from django.contrib.auth import get_user_model
from apps.courses.forms import INPUT, TEXTAREA
from apps.courses.models import Quiz, Question, QuizAttempt
from apps.partner.models import Institution

User = get_user_model()


class StandaloneExamForm(forms.ModelForm):
    """
    Form for authoring and editing Standalone Exams in THUTA Exam Center.
    """
    class Meta:
        model = Quiz
        fields = (
            'title',
            'course',
            'description',
            'quiz_type',
            'status',
            'price',
            'time_limit_minutes',
            'passing_percentage',
            'max_attempts',
            'certificate_type',
            'requires_manual_grading',
            'randomize_questions',
            'randomize_choices',
            'available_from',
            'available_until',
            'assigned_instructor',
            'institution',
            'certificate_template',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Certified Cyber Defense Practitioner Exam'}),
            'course': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4, 'placeholder': 'Overview, syllabus topics, and examination guidelines...'}),
            'quiz_type': forms.Select(attrs={'class': INPUT}),
            'status': forms.Select(attrs={'class': INPUT}),
            'price': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'step': '1000', 'placeholder': '0 for Free Exam'}),
            'time_limit_minutes': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'placeholder': '0 = Untimed'}),
            'passing_percentage': forms.NumberInput(attrs={'class': INPUT, 'min': '1', 'max': '100'}),
            'max_attempts': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'placeholder': '0 = Unlimited'}),
            'certificate_type': forms.Select(attrs={'class': INPUT}),
            'certificate_template': forms.Select(attrs={'class': INPUT}),
            'requires_manual_grading': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-500'}),
            'randomize_questions': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-500'}),
            'randomize_choices': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-500'}),
            'available_from': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'available_until': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'assigned_instructor': forms.Select(attrs={'class': INPUT}),
            'institution': forms.Select(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if 'certificate_template' in self.fields:
            self.fields['certificate_template'].required = False
            from apps.certificates.models import CertificateTemplate
            if user and not getattr(user, 'is_admin', False) and not getattr(user, 'is_superuser', False):
                self.fields['certificate_template'].queryset = CertificateTemplate.objects.filter(
                    models.Q(created_by=user) | models.Q(is_default=True)
                )
        from apps.courses.models import Course
        if user and not getattr(user, 'is_admin', False):
            self.fields['course'].queryset = Course.objects.filter(owner=user)
        else:
            self.fields['course'].queryset = Course.objects.all()
        self.fields['course'].required = False
        self.fields['course'].empty_label = "None (Independent Standalone Exam)"
        self.fields['assigned_instructor'].queryset = User.objects.filter(role__in=['instructor', 'admin', 'partner'])
        self.fields['assigned_instructor'].required = False
        self.fields['institution'].queryset = Institution.objects.all()
        self.fields['institution'].required = False
        self.fields['available_from'].required = False
        self.fields['available_until'].required = False

    def clean_price(self):
        p = self.cleaned_data.get('price')
        if p is None or p < 0:
            return Decimal('0.00')
        return p


class ExamGradingRubricForm(forms.Form):
    """
    Form for evaluating an attempt with rubric criteria scoring and overall comments.
    """
    overall_feedback = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': TEXTAREA,
            'rows': 4,
            'placeholder': 'Provide comprehensive evaluation feedback, strengths, and areas for improvement...',
        }),
        required=False,
    )
    pass_override = forms.ChoiceField(
        choices=[('auto', 'Auto-determine from total score %'), ('force_pass', 'Pass Candidate'), ('force_fail', 'Fail Candidate')],
        widget=forms.Select(attrs={'class': INPUT}),
        initial='auto',
    )

