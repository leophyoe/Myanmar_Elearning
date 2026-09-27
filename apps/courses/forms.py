from django import forms
from django.core.validators import FileExtensionValidator
from .models import Subject, Course, Module, Lesson

INPUT = 'w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500'
TEXTAREA = INPUT + ' min-h-[160px]'


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ('title', 'slug', 'description', 'icon_name', 'kind', 'order', 'is_active')
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT}),
            'slug': forms.TextInput(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'icon_name': forms.TextInput(attrs={'class': INPUT}),
            'kind': forms.Select(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('title', 'slug', 'subject', 'description', 'duration_months', 'is_published', 'thumbnail')
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT}),
            'slug': forms.TextInput(attrs={'class': INPUT}),
            'subject': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
            'duration_months': forms.NumberInput(attrs={'class': INPUT}),
            'is_published': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
            'thumbnail': forms.ClearableFileInput(attrs={'class': INPUT}),
        }


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
