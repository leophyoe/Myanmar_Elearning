from django import forms
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.utils.text import slugify
from .models import Subject, Course, Module, Lesson, LiveSession

INPUT = 'w-full bg-white dark:bg-[#0B1220] border border-slate-300 dark:border-[#26364B] rounded-xl px-3.5 py-2.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#0284C7] dark:focus:border-[#38BDF8] focus:ring-1 focus:ring-[#0284C7]'
TEXTAREA = INPUT + ' min-h-[140px]'


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
            'certificate_template',
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
            'certificate_template': forms.Select(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) or kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        # Optional fields with sensible defaults for robust form submissions
        self.fields['price'].required = False
        self.fields['slug'].required = False
        self.fields['duration_months'].required = False
        self.fields['exam_voucher_price'].required = False
        if 'certificate_template' in self.fields:
            self.fields['certificate_template'].required = False
            from apps.certificates.models import CertificateTemplate
            if self.user and not getattr(self.user, 'is_admin', False) and not self.user.is_superuser:
                from apps.partner.views import get_user_partner_institutions
                user_insts = get_user_partner_institutions(self.user)
                self.fields['certificate_template'].queryset = CertificateTemplate.objects.filter(
                    models.Q(created_by=self.user) |
                    models.Q(is_default=True) |
                    models.Q(partner__in=user_insts)
                ).distinct()
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

        if price > 0 and self.user and not getattr(self.user, 'is_admin', False):
            teacher_profile = getattr(self.user, 'teacher_profile', None)
            if teacher_profile and not teacher_profile.can_sell_paid_courses:
                raise forms.ValidationError(
                    "Teachers at the entry-level Teacher rank may only publish free tutorials. "
                    "Promotion to Associate Instructor or higher is required before publishing paid courses."
                )
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

    MAX_VIDEO_MB = 1000  # Supports full HD / 4K lectures up to 1 GB
    MAX_DOC_MB = 50      # Supports high-res slide decks up to 50 MB
    VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogg', 'mov', 'm4v', 'mkv', 'avi']
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
            'video_url': forms.URLInput(attrs={'class': INPUT, 'placeholder': 'https://youtube.com/watch?v=... or https://vimeo.com/... or Bunny CDN'}),
            'video_file': forms.ClearableFileInput(
                attrs={'class': INPUT, 'accept': '.mp4,.webm,.ogg,.mov,.m4v,.mkv,.avi'}
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
    """
    Versatile Assessment Question Form supporting:
    - Multiple Choice (Single Correct Option)
    - Multiple Select (One or More Correct Checkbox Options)
    - True / False
    - Fill in the Blank
    - Short Answer / Open-ended Essay
    - Coding Problems & Hands-on Exercises
    """

    CHOICE_SLOTS = 6
    RADIO = 'accent-cyan-500'

    question_type = forms.ChoiceField(
        label='Question Type',
        choices=Question.QuestionType.choices,
        widget=forms.Select(attrs={'class': INPUT + ' question-type-select'}),
        initial=Question.QuestionType.MULTIPLE_CHOICE,
    )

    choice_1 = forms.CharField(label='Option 1', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_2 = forms.CharField(label='Option 2', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_3 = forms.CharField(label='Option 3', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_4 = forms.CharField(label='Option 4', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_5 = forms.CharField(label='Option 5', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    choice_6 = forms.CharField(label='Option 6', max_length=512, required=False, widget=forms.TextInput(attrs={'class': INPUT}))

    correct_choice = forms.TypedChoiceField(
        label='Correct answer',
        choices=[(i, f'Option {i}') for i in range(1, CHOICE_SLOTS + 1)],
        coerce=int,
        required=False,
        widget=forms.RadioSelect(attrs={'class': RADIO}),
    )

    correct_choices_multi = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    correct_text_answer = forms.CharField(
        label='Accepted Answer(s)',
        max_length=512,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT,
            'placeholder': 'Enter correct answer(s) (pipe "|" separated, e.g. answer1 | answer2)'
        }),
        help_text="Expected answer for Fill in the Blank or exact match."
    )

    rubric_criteria = forms.CharField(
        label='Grading Criteria / Code Test Pattern',
        required=False,
        widget=forms.Textarea(attrs={
            'class': TEXTAREA,
            'rows': 2,
            'placeholder': 'Evaluation instructions, rubric criteria or required code output keywords'
        }),
        help_text="Grading guidance for open-ended or coding challenges."
    )

    class Meta:
        model = Question
        fields = ('order', 'prompt', 'question_type', 'points', 'correct_text_answer', 'rubric_criteria', 'explanation')
        widgets = {
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
            'prompt': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'Enter question prompt, instructions, or scenario'}),
            'points': forms.NumberInput(attrs={'class': INPUT, 'min': 1}),
            'explanation': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'Feedback shown to the student after the attempt'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance') or getattr(self, 'instance', None)
        if instance is not None and instance.pk:
            self.fields['question_type'].initial = instance.question_type
            self.fields['correct_text_answer'].initial = instance.correct_text_answer
            self.fields['rubric_criteria'].initial = instance.rubric_criteria

            existing = list(instance.choices.order_by('id')[: self.CHOICE_SLOTS])
            multi_correct = []
            for index, choice in enumerate(existing, start=1):
                self.fields[f'choice_{index}'].initial = choice.text
                if choice.is_correct:
                    multi_correct.append(str(index))
                    if not self.fields['correct_choice'].initial:
                        self.fields['correct_choice'].initial = index
            if multi_correct:
                self.fields['correct_choices_multi'].initial = ','.join(multi_correct)
        else:
            if not self.initial.get('points'):
                self.initial['points'] = 10
            if not self.initial.get('correct_choice'):
                self.initial['correct_choice'] = 1

    def clean(self):
        cleaned = super().clean()
        prompt = (cleaned.get('prompt') or '').strip()
        if not prompt:
            return cleaned

        q_type = cleaned.get('question_type') or Question.QuestionType.MULTIPLE_CHOICE

        if q_type == Question.QuestionType.MULTIPLE_CHOICE:
            correct = cleaned.get('correct_choice')
            if not correct:
                self.add_error('correct_choice', 'Please mark one option as the correct answer.')
            else:
                text = (cleaned.get(f'choice_{correct}') or '').strip()
                if not text:
                    self.add_error('correct_choice', f'Option {correct} is marked correct but left empty.')
            filled = [
                cleaned.get(f'choice_{i}')
                for i in range(1, self.CHOICE_SLOTS + 1)
                if cleaned.get(f'choice_{i}') and cleaned.get(f'choice_{i}').strip()
            ]
            if len(filled) < 2:
                self.add_error(None, 'Multiple choice requires at least two answer options.')

        elif q_type == Question.QuestionType.MULTIPLE_SELECT:
            raw_multi = cleaned.get('correct_choices_multi') or ''
            multi_indices = [int(x.strip()) for x in raw_multi.split(',') if x.strip().isdigit()]
            if not multi_indices and cleaned.get('correct_choice'):
                multi_indices = [cleaned.get('correct_choice')]
                cleaned['correct_choices_multi'] = str(cleaned.get('correct_choice'))

            if not multi_indices:
                self.add_error(None, 'Please select at least one correct checkbox option for Multiple Select.')
            filled = [
                cleaned.get(f'choice_{i}')
                for i in range(1, self.CHOICE_SLOTS + 1)
                if cleaned.get(f'choice_{i}') and cleaned.get(f'choice_{i}').strip()
            ]
            if len(filled) < 2:
                self.add_error(None, 'Multiple select requires at least two answer options.')

        elif q_type == Question.QuestionType.TRUE_FALSE:
            if not (cleaned.get('choice_1') or '').strip():
                cleaned['choice_1'] = 'True'
            if not (cleaned.get('choice_2') or '').strip():
                cleaned['choice_2'] = 'False'
            correct = cleaned.get('correct_choice')
            if not correct or correct not in (1, 2):
                cleaned['correct_choice'] = 1

        elif q_type == Question.QuestionType.FILL_IN_BLANK:
            correct_text = (cleaned.get('correct_text_answer') or '').strip()
            if not correct_text:
                if (cleaned.get('choice_1') or '').strip():
                    cleaned['correct_text_answer'] = cleaned.get('choice_1').strip()
                else:
                    self.add_error('correct_text_answer', 'Enter the accepted correct answer for Fill in the Blank.')

        elif q_type in (
            Question.QuestionType.SHORT_ANSWER,
            Question.QuestionType.CODING,
            Question.QuestionType.PRACTICAL_LAB,
            Question.QuestionType.FILE_SUBMISSION,
            Question.QuestionType.PROJECT_EVALUATION,
        ):
            pass

        return cleaned

    def save(self, commit=True):
        question = super().save(commit=False)
        q_type = self.cleaned_data.get('question_type') or Question.QuestionType.MULTIPLE_CHOICE
        question.question_type = q_type
        question.correct_text_answer = (self.cleaned_data.get('correct_text_answer') or '').strip()
        question.rubric_criteria = (self.cleaned_data.get('rubric_criteria') or '').strip()

        if commit:
            question.save()
            self._save_choices(question, q_type)
        else:
            def save_m2m():
                self._save_choices(question, q_type)
            self.save_m2m = save_m2m
        return question

    def _save_choices(self, question, q_type):
        existing = list(question.choices.order_by('id'))
        used_ids = []

        if q_type in (Question.QuestionType.MULTIPLE_CHOICE, Question.QuestionType.TRUE_FALSE):
            correct = self.cleaned_data.get('correct_choice') or 1
            max_slots = 2 if q_type == Question.QuestionType.TRUE_FALSE else self.CHOICE_SLOTS
            for index in range(1, max_slots + 1):
                text = (self.cleaned_data.get(f'choice_{index}') or '').strip()
                if not text:
                    continue
                is_correct = (index == correct)
                if index - 1 < len(existing):
                    choice = existing[index - 1]
                    choice.text = text
                    choice.is_correct = is_correct
                    choice.save(update_fields=['text', 'is_correct'])
                else:
                    choice = Choice.objects.create(question=question, text=text, is_correct=is_correct)
                used_ids.append(choice.pk)

        elif q_type == Question.QuestionType.MULTIPLE_SELECT:
            raw_multi = self.cleaned_data.get('correct_choices_multi') or ''
            multi_indices = {int(x.strip()) for x in raw_multi.split(',') if x.strip().isdigit()}
            if not multi_indices and self.cleaned_data.get('correct_choice'):
                multi_indices = {self.cleaned_data.get('correct_choice')}

            for index in range(1, self.CHOICE_SLOTS + 1):
                text = (self.cleaned_data.get(f'choice_{index}') or '').strip()
                if not text:
                    continue
                is_correct = (index in multi_indices)
                if index - 1 < len(existing):
                    choice = existing[index - 1]
                    choice.text = text
                    choice.is_correct = is_correct
                    choice.save(update_fields=['text', 'is_correct'])
                else:
                    choice = Choice.objects.create(question=question, text=text, is_correct=is_correct)
                used_ids.append(choice.pk)

        elif q_type == Question.QuestionType.FILL_IN_BLANK:
            for index in range(1, self.CHOICE_SLOTS + 1):
                text = (self.cleaned_data.get(f'choice_{index}') or '').strip()
                if not text:
                    continue
                if index - 1 < len(existing):
                    choice = existing[index - 1]
                    choice.text = text
                    choice.is_correct = True
                    choice.save(update_fields=['text', 'is_correct'])
                else:
                    choice = Choice.objects.create(question=question, text=text, is_correct=True)
                used_ids.append(choice.pk)

        question.choices.exclude(pk__in=used_ids).delete()


class QuestionBaseInlineFormSet(BaseInlineFormSet):
    """The quiz needs at least one valid question with answer criteria."""

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
            if not (form.cleaned_data.get('prompt') or '').strip():
                continue
            live_questions += 1
        if live_questions == 0:
            raise forms.ValidationError('Add at least one question before saving the quiz.')


QuestionFormSet = inlineformset_factory(
    Quiz,
    Question,
    form=QuestionForm,
    formset=QuestionBaseInlineFormSet,
    extra=1,
    can_delete=True,
)


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ('module', 'title', 'description', 'max_score', 'due_date')
        widgets = {
            'module': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Practical Lab 1: Python Socket Programming'}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 6, 'placeholder': 'Describe assignment tasks, submission deliverables (source code, report, screenshots), and grading criteria...'}),
            'max_score': forms.NumberInput(attrs={'class': INPUT, 'min': 1, 'placeholder': '100'}),
            'due_date': forms.DateTimeInput(
                attrs={'class': INPUT, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) or kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields['due_date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
        self.fields['due_date'].required = False
        if user and not getattr(user, 'is_admin', False) and not getattr(user, 'is_superuser', False):
            self.fields['module'].queryset = Module.objects.filter(
                models.Q(course__owner=user) | models.Q(course__is_official=False)
            ).select_related('course')

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
    """Teacher-facing scheduling of a real-time class (BigBlueButton / Zoom / Google Meet / Teams)."""

    WEEKDAY_CHOICES = [
        ('0', 'Monday (တနင်္လာ)'),
        ('1', 'Tuesday (အင်္ဂါ)'),
        ('2', 'Wednesday (ဗုဒ္ဓဟူး)'),
        ('3', 'Thursday (ကြာသပတေး)'),
        ('4', 'Friday (သောကြာ)'),
        ('5', 'Saturday (စနေ)'),
        ('6', 'Sunday (တနင်္ဂနွေ)'),
    ]

    schedule_type = forms.ChoiceField(
        choices=[
            ('single', 'Single Session (တစ်ရက်တည်း သီးသန့်)'),
            ('recurring', 'Recurring Multi-Day Series (ရက်ရှည်/အကြိမ်ကြိမ် အတန်းစဉ်)'),
        ],
        initial='single',
        widget=forms.Select(attrs={'class': INPUT, 'id': 'id_schedule_type'}),
        required=False,
    )
    recurring_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'recurring-day-check w-4 h-4 text-[#0284C7] rounded border-slate-300 dark:border-slate-700 focus:ring-[#0284C7]'}),
        required=False,
    )
    recurrence_weeks = forms.IntegerField(
        min_value=1,
        max_value=52,
        initial=4,
        required=False,
        widget=forms.NumberInput(attrs={'class': INPUT, 'min': '1', 'max': '52', 'id': 'id_recurrence_weeks', 'placeholder': 'e.g. 4, 8, or 12 weeks'}),
    )
    total_sessions = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=8,
        required=False,
        widget=forms.NumberInput(attrs={'class': INPUT, 'min': '1', 'max': '100', 'id': 'id_total_sessions', 'placeholder': 'e.g. 8 or 16 total sessions'}),
    )

    class Meta:
        model = LiveSession
        fields = ('course', 'title', 'provider', 'join_url', 'starts_at',
                  'duration_minutes', 'record_meeting', 'notes', 'is_published')
        widgets = {
            'course': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'e.g., Cyber Defense Hands-on Lab & Lecture'}
            ),
            'provider': forms.Select(attrs={'class': INPUT, 'id': 'id_provider'}),
            'join_url': forms.URLInput(
                attrs={
                    'class': INPUT,
                    'id': 'id_join_url',
                    'placeholder': 'https://zoom.us/j/... or https://meet.google.com/... (Auto-provisioned for BigBlueButton)',
                }
            ),
            'starts_at': forms.DateTimeInput(
                attrs={'class': INPUT, 'type': 'datetime-local'}
            ),
            'duration_minutes': forms.NumberInput(attrs={'class': INPUT, 'min': '5'}),
            'record_meeting': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-[#0284C7] rounded border-slate-300 dark:border-slate-700 focus:ring-[#0284C7]'}),
            'notes': forms.Textarea(
                attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'Class agenda, prerequisites, lab instructions...'}
            ),
            'is_published': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-[#0284C7] rounded border-slate-300 dark:border-slate-700 focus:ring-[#0284C7]'}),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # BigBlueButton does not require manual external URL; it auto-provisions
        self.fields['join_url'].required = False

        if self.instance.pk and self.instance.series_id:
            self.fields['schedule_type'].initial = 'recurring'

        # Set default provider from settings/DB if creating new session
        if not self.instance.pk:
            try:
                from apps.courses.models import LiveProviderSetting
                default_setting = LiveProviderSetting.objects.filter(is_default=True, is_enabled=True).first()
                if default_setting:
                    self.fields['provider'].initial = default_setting.provider
            except Exception:
                pass

        # Filter out disabled providers from choices for new sessions
        try:
            from apps.courses.models import LiveProviderSetting
            disabled_providers = set(
                LiveProviderSetting.objects.filter(is_enabled=False).values_list('provider', flat=True)
            )
            if disabled_providers:
                curr_p = self.instance.provider if self.instance.pk else None
                self.fields['provider'].choices = [
                    (c, label) for c, label in self.fields['provider'].choices
                    if c not in disabled_providers or c == curr_p
                ]
        except Exception:
            pass

        if request is not None and not request.user.is_admin:
            user = request.user
            course_qs = Course.objects.filter(owner=user, is_official=False)
            if getattr(user, 'is_partner', False):
                try:
                    from apps.partner.models import get_user_partner_institutions
                    from django.db.models import Q
                    institutions = get_user_partner_institutions(user)
                    if institutions:
                        course_qs = Course.objects.filter(
                            Q(owner=user) | Q(partner_institution__in=institutions)
                        ).distinct()
                except Exception:
                    pass
            self.fields['course'].queryset = course_qs

    def clean_starts_at(self):
        starts_at = self.cleaned_data.get('starts_at')
        if starts_at and self.instance._state.adding and starts_at <= timezone.now():
            raise forms.ValidationError('Schedule the session in the future.')
        return starts_at

    def clean_duration_minutes(self):
        minutes = self.cleaned_data.get('duration_minutes')
        if minutes is not None and minutes > 24 * 60:
            raise forms.ValidationError('A session cannot last longer than 24 hours.')
        return minutes

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('provider')
        join_url = (cleaned_data.get('join_url') or '').strip()

        # External providers require a valid meeting link
        if provider in (LiveSession.Provider.ZOOM, LiveSession.Provider.GOOGLE_MEET, LiveSession.Provider.TEAMS, LiveSession.Provider.OTHER):
            if not join_url:
                self.add_error('join_url', 'Meeting URL is required when using external providers (Zoom, Google Meet, Teams).')
            elif provider == LiveSession.Provider.GOOGLE_MEET and 'meet.google.com' not in join_url:
                self.add_error('join_url', 'Please enter a valid Google Meet link (e.g., https://meet.google.com/xxx-xxxx-xxx).')
            elif provider == LiveSession.Provider.ZOOM and 'zoom.' not in join_url:
                self.add_error('join_url', 'Please enter a valid Zoom meeting link (e.g., https://zoom.us/j/...).')

        # Multi-day recurring schedule calculation
        schedule_type = cleaned_data.get('schedule_type')
        starts_at = cleaned_data.get('starts_at')
        if schedule_type == 'recurring' and starts_at and self.instance._state.adding:
            recurring_days = cleaned_data.get('recurring_days') or []
            if not recurring_days:
                recurring_days = [str(starts_at.weekday())]
                cleaned_data['recurring_days'] = recurring_days

            day_ints = sorted([int(d) for d in recurring_days if str(d).isdigit()])
            recurrence_weeks = cleaned_data.get('recurrence_weeks') or 4
            total_sessions = cleaned_data.get('total_sessions') or (len(day_ints) * recurrence_weeks)

            from datetime import timedelta, datetime
            dates = []
            cur_date = starts_at.date()
            start_time = starts_at.time()
            tz = starts_at.tzinfo
            max_search_days = recurrence_weeks * 7 + 14

            for offset in range(max_search_days):
                check_date = cur_date + timedelta(days=offset)
                if check_date.weekday() in day_ints:
                    dt = datetime.combine(check_date, start_time, tzinfo=tz)
                    if dt >= starts_at:
                        dates.append(dt)
                        if total_sessions and len(dates) >= total_sessions:
                            break

            if not dates:
                dates = [starts_at]

            cleaned_data['computed_recurring_dates'] = dates

            DAY_NAMES = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
            day_names_str = ', '.join([DAY_NAMES.get(d, str(d)) for d in day_ints])
            cleaned_data['recurrence_rule_str'] = f"Every {day_names_str} ({len(dates)} sessions)"

        return cleaned_data

