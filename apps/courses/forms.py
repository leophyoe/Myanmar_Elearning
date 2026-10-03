from django import forms
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.utils.text import slugify
from .models import Subject, Course, Module, Lesson, LiveSession

INPUT = 'w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500'
TEXTAREA = INPUT + ' min-h-[160px]'


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ('title', 'slug', 'description', 'icon_name', 'kind', 'order', 'is_active')
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Python Programming, Mathematics, AI'}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Auto-generated from title if blank'}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'Overview of this subject'}),
            'icon_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. book-open, code-slash, shield-check'}),
            'kind': forms.Select(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['icon_name'].required = False

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            title = self.cleaned_data.get('title', '')
            base_slug = slugify(title) or 'subject'
            slug = base_slug
            counter = 2
            qs = Subject.objects.filter(slug=slug)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            while qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                qs = Subject.objects.filter(slug=slug)
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
        return slug

    def clean_icon_name(self):
        icon = (self.cleaned_data.get('icon_name') or '').strip()
        return icon if icon else 'book-open'


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = (
            'title', 'slug', 'subject', 'description', 'level', 'language', 'duration_months',
            'access_type', 'membership_tier_required', 'is_published', 'is_official',
            'thumbnail', 'price', 'billing_period', 'exam_required', 'exam_voucher_price',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Course Title'}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Auto-generated from title if blank'}),
            'subject': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
            'level': forms.Select(attrs={'class': INPUT}),
            'language': forms.Select(attrs={'class': INPUT}),
            'duration_months': forms.NumberInput(attrs={'class': INPUT}),
            'access_type': forms.Select(attrs={'class': INPUT}),
            'membership_tier_required': forms.Select(attrs={'class': INPUT}),
            'is_published': forms.CheckboxInput(attrs={'class': 'accent-blue-600'}),
            'is_official': forms.CheckboxInput(attrs={'class': 'accent-blue-600'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': INPUT}),
            'price': forms.NumberInput(
                attrs={'class': INPUT, 'min': '0', 'step': '100',
                       'placeholder': '0 = free course'}
            ),
            'billing_period': forms.Select(attrs={'class': INPUT}),
            'exam_required': forms.CheckboxInput(attrs={'class': 'accent-blue-600'}),
            'exam_voucher_price': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'step': '100'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Optional fields with sensible defaults for robust form submissions
        self.fields['price'].required = False
        self.fields['slug'].required = False
        self.fields['duration_months'].required = False
        self.fields['exam_voucher_price'].required = False
        if 'subject' in self.fields:
            self.fields['subject'].required = False
        if 'level' in self.fields:
            self.fields['level'].required = False
            self.fields['level'].initial = Course.Level.ALL_LEVELS
        if 'language' in self.fields:
            self.fields['language'].required = False
            self.fields['language'].initial = Course.Language.BURMESE
        if 'access_type' in self.fields:
            self.fields['access_type'].required = False
            self.fields['access_type'].initial = Course.AccessType.FREE
        if 'membership_tier_required' in self.fields:
            self.fields['membership_tier_required'].required = False
            self.fields['membership_tier_required'].initial = Course.MembershipTierRequired.STANDARD
        if 'billing_period' in self.fields:
            self.fields['billing_period'].required = False
            self.fields['billing_period'].initial = Course.BillingPeriod.ONE_TIME

        # If user is not admin, hide administrative publication fields
        is_user_admin = bool(self.user and getattr(self.user, 'is_admin', False))
        if not is_user_admin:
            if 'is_official' in self.fields:
                self.fields['is_official'].widget = forms.HiddenInput()
                self.fields['is_official'].required = False
            if 'is_published' in self.fields:
                self.fields['is_published'].widget = forms.HiddenInput()
                self.fields['is_published'].required = False

    def clean_is_official(self):
        is_user_admin = bool(self.user and getattr(self.user, 'is_admin', False))
        if not is_user_admin:
            return False
        return self.cleaned_data.get('is_official', False)

    def clean_is_published(self):
        is_user_admin = bool(self.user and getattr(self.user, 'is_admin', False))
        if not is_user_admin:
            return getattr(self.instance, 'is_published', False) if self.instance.pk else False
        return self.cleaned_data.get('is_published', False)

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()
        if not slug:
            title = self.cleaned_data.get('title', '')
            base_slug = slugify(title) or 'course'
            slug = base_slug
            counter = 2
            qs = Course.objects.filter(slug=slug)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            while qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                qs = Course.objects.filter(slug=slug)
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
        return slug

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None:
            return 0
        if price < 0:
            raise forms.ValidationError("Price cannot be negative — use 0 for a free course.")
        if price > 1_000_000_000:
            raise forms.ValidationError("That price looks too large for a single course.")
        return price

    def clean_level(self):
        return self.cleaned_data.get('level') or Course.Level.ALL_LEVELS

    def clean_language(self):
        return self.cleaned_data.get('language') or Course.Language.BURMESE

    def clean_access_type(self):
        return self.cleaned_data.get('access_type') or Course.AccessType.FREE

    def clean_membership_tier_required(self):
        return self.cleaned_data.get('membership_tier_required') or Course.MembershipTierRequired.STANDARD

    def clean_billing_period(self):
        return self.cleaned_data.get('billing_period') or Course.BillingPeriod.ONE_TIME

    def clean_duration_months(self):
        return self.cleaned_data.get('duration_months') or 1

    def clean_exam_voucher_price(self):
        return self.cleaned_data.get('exam_voucher_price') or 0


class CourseReviewForm(forms.Form):
    class Action(models.TextChoices):
        APPROVE = 'approve', 'Approve Curriculum'
        PUBLISH = 'publish', 'Approve & Publish Immediately'
        REQUEST_CHANGES = 'request_changes', 'Request Changes'
        REJECT = 'reject', 'Reject Course'
        ARCHIVE = 'archive', 'Archive Course'

    action = forms.ChoiceField(
        choices=Action.choices,
        widget=forms.Select(attrs={'class': INPUT}),
    )
    admin_review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': TEXTAREA,
            'rows': 4,
            'placeholder': 'Provide feedback or reasons for the instructor (mandatory if rejecting or requesting changes)...'
        }),
        help_text="Feedback provided to the instructor."
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        notes = (cleaned_data.get('admin_review_notes') or '').strip()

        if action in [self.Action.REJECT, self.Action.REQUEST_CHANGES] and not notes:
            self.add_error('admin_review_notes', 'Review notes are required when rejecting or requesting changes.')

        return cleaned_data



class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ('course', 'order', 'code', 'title', 'summary', 'learning_objectives', 'icon_name')
        widgets = {
            'course': forms.Select(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'code': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'MOD-01'}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'summary': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'learning_objectives': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 4, 'placeholder': 'One objective per line'}
            ),
            'icon_name': forms.TextInput(attrs={'class': INPUT}),
        }

    def clean_learning_objectives(self):
        value = self.cleaned_data.get('learning_objectives')
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        return value or []


class LessonForm(forms.ModelForm):
    """Teacher-facing lesson authoring form including video / document uploads."""

    MAX_VIDEO_MB = 200
    MAX_DOC_MB = 25
    VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogg', 'mov', 'm4v']
    DOC_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'md', 'zip']

    class Meta:
        model = Lesson
        fields = (
            'module', 'order', 'title', 'lesson_type',
            'content_markdown', 'video_url', 'video_file', 'document_file',
            'estimated_minutes', 'has_lab', 'has_quiz',
        )
        widgets = {
            'module': forms.Select(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'lesson_type': forms.Select(attrs={'class': INPUT}),
            'content_markdown': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 12}),
            'video_url': forms.URLInput(attrs={'class': INPUT, 'placeholder': 'https://youtube.com/watch?v=...'}),
            'video_file': forms.ClearableFileInput(
                attrs={'class': INPUT, 'accept': '.mp4,.webm,.ogg,.mov,.m4v'}
            ),
            'document_file': forms.ClearableFileInput(
                attrs={'class': INPUT, 'accept': '.pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.zip'}
            ),
            'estimated_minutes': forms.NumberInput(attrs={'class': INPUT}),
            'has_lab': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
            'has_quiz': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # JSONField stores a list; the textarea wants newline-separated text.
        objectives = getattr(self.instance, 'learning_objectives', None)
        if isinstance(objectives, list):
            self.initial['learning_objectives'] = "\n".join(objectives)

        self.fields['video_file'].validators.append(
            FileExtensionValidator(allowed_extensions=self.VIDEO_EXTENSIONS)
        )
        self.fields['document_file'].validators.append(
            FileExtensionValidator(allowed_extensions=self.DOC_EXTENSIONS)
        )

    def clean_video_file(self):
        upload = self.cleaned_data.get('video_file')
        if upload and hasattr(upload, 'size'):
            if upload.size > self.MAX_VIDEO_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"Video is {upload.size // (1024 * 1024)} MB — the limit is {self.MAX_VIDEO_MB} MB."
                )
        return upload

    def clean_document_file(self):
        upload = self.cleaned_data.get('document_file')
        if upload and hasattr(upload, 'size'):
            if upload.size > self.MAX_DOC_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"Document is {upload.size // (1024 * 1024)} MB — the limit is {self.MAX_DOC_MB} MB."
                )
        return upload


# ----------------------------------------------------------------------
# Phase 3 - assessment authoring, submission and grading
# ----------------------------------------------------------------------
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quiz, Question, Choice, Assignment, AssignmentSubmission


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ('title', 'passing_percentage', 'max_attempts')
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Checkpoint quiz'}),
            'passing_percentage': forms.NumberInput(attrs={'class': INPUT, 'min': 1, 'max': 100}),
            'max_attempts': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
        }


class QuestionForm(forms.ModelForm):
    """One multiple choice question with four answer slots and a correct slot."""

    CHOICE_SLOTS = 4
    RADIO = 'accent-cyan-500'

    choice_1 = forms.CharField(label='Option 1', max_length=512, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_2 = forms.CharField(label='Option 2', max_length=512, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_3 = forms.CharField(label='Option 3', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_4 = forms.CharField(label='Option 4', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    correct_choice = forms.TypedChoiceField(
        label='Correct answer',
        choices=[(i, f'Option {i}') for i in range(1, CHOICE_SLOTS + 1)],
        coerce=int,
        widget=forms.RadioSelect(attrs={'class': RADIO}),
    )

    class Meta:
        model = Question
        fields = ('order', 'prompt', 'points', 'explanation')
        widgets = {
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
            'prompt': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'Question prompt'}),
            'points': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
            'explanation': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'Shown to the student after the attempt'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance') or getattr(self, 'instance', None)
        if instance is not None and instance.pk:
            existing = list(instance.choices.order_by('id')[: self.CHOICE_SLOTS])
            for index, choice in enumerate(existing, start=1):
                self.fields[f'choice_{index}'].initial = choice.text
                if choice.is_correct:
                    self.fields['correct_choice'].initial = index

    def clean(self):
        cleaned = super().clean()
        correct = cleaned.get('correct_choice')
        if correct:
            text = cleaned.get(f'choice_{correct}')
            if not text or not text.strip():
                self.add_error('correct_choice', f'Option {correct} is marked correct but left empty.')
        filled = [
            cleaned.get(f'choice_{i}')
            for i in range(1, self.CHOICE_SLOTS + 1)
            if cleaned.get(f'choice_{i}') and cleaned.get(f'choice_{i}').strip()
        ]
        if len(filled) < 2:
            self.add_error(None, 'Provide at least two answer options.')
        return cleaned

    def save(self, commit=True):
        # The question row must exist before its answer slots can point at it.
        # (BaseModel assigns the primary key eagerly, so a missing row cannot be
        # detected by checking question.pk.)
        question = super().save(commit=False)
        question.save()

        existing = list(question.choices.order_by('id'))
        correct = self.cleaned_data.get('correct_choice')
        used_ids = []
        for index in range(1, self.CHOICE_SLOTS + 1):
            text = (self.cleaned_data.get(f'choice_{index}') or '').strip()
            if not text:
                continue
            is_correct = index == correct
            if index - 1 < len(existing):
                choice = existing[index - 1]
                choice.text = text
                choice.is_correct = is_correct
                choice.save(update_fields=['text', 'is_correct'])
            else:
                choice = Choice.objects.create(
                    question=question, text=text, is_correct=is_correct
                )
            used_ids.append(choice.pk)
        question.choices.exclude(pk__in=used_ids).delete()
        return question


class QuestionBaseInlineFormSet(BaseInlineFormSet):
    """Each question needs a correct answer, and the quiz needs at least one."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        live_questions = 0
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            if not form.cleaned_data.get('prompt', '').strip():
                continue
            if form.cleaned_data.get('correct_choice') in (None, ''):
                raise forms.ValidationError('Each question needs a correct answer selected.')
            live_questions += 1
        if live_questions == 0:
            raise forms.ValidationError('Add at least one question before saving the quiz.')


QuestionFormSet = inlineformset_factory(
    Quiz,
    Question,
    form=QuestionForm,
    formset=QuestionBaseInlineFormSet,
    extra=2,
    can_delete=True,
)


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ('module', 'title', 'description', 'max_score', 'due_date')
        widgets = {
            'module': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 6}),
            'max_score': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
            'due_date': forms.DateTimeInput(
                attrs={'class': INPUT, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['due_date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']

    def clean_description(self):
        value = (self.cleaned_data.get('description') or '').strip()
        if not value:
            raise forms.ValidationError('Describe what the student must deliver.')
        return value


class AssignmentSubmitForm(forms.ModelForm):
    """Student hand-in: written answer plus an optional supporting file."""

    MAX_UPLOAD_MB = 25
    FILE_EXTENSIONS = ['pdf', 'doc', 'docx', 'zip', 'png', 'jpg', 'jpeg', 'txt', 'md', 'py', 'sh', 'json', 'csv']

    class Meta:
        model = AssignmentSubmission
        fields = ('submission_text', 'submission_file')
        widgets = {
            'submission_text': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 8, 'placeholder': 'Paste your answer, write-up or report link here.'}),
            'submission_file': forms.ClearableFileInput(attrs={'class': INPUT}),
        }

    def clean(self):
        cleaned = super().clean()
        text = (cleaned.get('submission_text') or '').strip()
        upload = cleaned.get('submission_file')
        if not text and not upload:
            raise forms.ValidationError('Add a written answer or attach a file before submitting.')
        return cleaned

    def clean_submission_file(self):
        upload = self.cleaned_data.get('submission_file')
        if upload and hasattr(upload, 'size'):
            if upload.size > self.MAX_UPLOAD_MB * 1024 * 1024:
                raise forms.ValidationError(
                    f"File is {upload.size // (1024 * 1024)} MB — the limit is {self.MAX_UPLOAD_MB} MB."
                )
        return upload


class SubmissionGradeForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ('score', 'feedback')
        widgets = {
            'score': forms.NumberInput(attrs={'class': INPUT, 'min': 0}),
            'feedback': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 5, 'placeholder': 'What went well, what to improve.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assignment = getattr(self.instance, 'assignment', None)
        self.max_score = assignment.max_score if assignment else 100
        self.fields['score'].min_value = 0
        self.fields['score'].max_value = self.max_score
        self.fields['score'].label = f'Score (out of {self.max_score})'
        self.fields['feedback'].required = False

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is None:
            raise forms.ValidationError('Enter the score awarded.')
        if score > self.max_score:
            raise forms.ValidationError(f'Score cannot exceed {self.max_score}.')
        return score


class LiveSessionForm(forms.ModelForm):
    """Teacher-facing scheduling of a real-time class (Zoom / Meet / Teams)."""

    class Meta:
        model = LiveSession
        fields = ('course', 'title', 'provider', 'join_url', 'starts_at',
                  'duration_minutes', 'notes', 'is_published')
        widgets = {
            'course': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Module 3 review session'}
            ),
            'provider': forms.Select(attrs={'class': INPUT}),
            'join_url': forms.URLInput(
                attrs={'class': INPUT, 'placeholder': 'https://zoom.us/j/...'}
            ),
            'starts_at': forms.DateTimeInput(
                attrs={'class': INPUT, 'type': 'datetime-local'}
            ),
            'duration_minutes': forms.NumberInput(attrs={'class': INPUT, 'min': '5'}),
            'notes': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'Optional agenda or prerequisites'}
            ),
            'is_published': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request is not None and not request.user.is_admin:
            # Teachers only schedule sessions on courses they own (not official platform courses).
            self.fields['course'].queryset = Course.objects.filter(
                owner=request.user,
                is_official=False,
            )

    def clean_starts_at(self):
        starts_at = self.cleaned_data.get('starts_at')
        # NB: BaseModel assigns the UUID eagerly, so _state.adding is the only
        # reliable "this is a new record" test.
        if starts_at and self.instance._state.adding and starts_at <= timezone.now():
            raise forms.ValidationError('Schedule the session in the future.')
        return starts_at

    def clean_duration_minutes(self):
        minutes = self.cleaned_data.get('duration_minutes')
        if minutes is not None and minutes > 24 * 60:
            raise forms.ValidationError('A session cannot last longer than 24 hours.')
        return minutes
