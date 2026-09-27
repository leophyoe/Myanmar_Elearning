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
