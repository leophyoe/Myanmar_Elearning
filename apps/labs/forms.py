"""Teacher-facing authoring forms for cyber labs and lab templates."""

import json
from pathlib import Path

from django import forms
from django.conf import settings
from django.utils.text import slugify

from .bundles import BundleError, bundle_dir, extract_bundle, validate_bundle
from .models import Lab, LabCategory, LabTemplate

INPUT = ('w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 '
         'text-sm text-white focus:outline-none focus:border-cyan-500')
TEXTAREA = INPUT + ' min-h-[160px]'
CHECKBOX = 'accent-cyan-500'


def _unique_slug(model, base, instance=None):
    """Slugify ``base`` and append -2, -3... until it is free."""
    base = slugify(base)[:140] or 'item'
    slug, n = base, 1
    while True:
        qs = model.objects.filter(slug=slug)
        if instance is not None and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        if not qs.exists():
            return slug
        n += 1
        slug = f'{base}-{n}'


def _relative_bundle_path(raw: str) -> str:
    """Validate a folder path stored on a LabTemplate (relative to cyber/labs)."""
    raw = (raw or '').strip().strip('/')
    if not raw:
        return raw
    if Path(raw).is_absolute() or '..' in Path(raw).parts or raw.startswith('~'):
        raise forms.ValidationError(
            "Use a folder path inside cyber/labs/, e.g. web/sqli_basics."
        )
    return str(Path(raw))


def _max_bundle_bytes() -> int:
    return getattr(settings, 'CYBER_BUNDLE_MAX_MB', 25) * 1024 * 1024


class LabTemplateForm(forms.ModelForm):
    """Blueprint: which image the range runs and with what limits."""

    class Meta:
        model = LabTemplate
        fields = (
            'name', 'slug', 'category', 'description', 'docker_compose_path',
            'image_name', 'cpu_limit', 'mem_limit', 'pids_limit',
            'read_only_root', 'default_duration_minutes', 'flag_pattern',
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'auto from name'}),
            'category': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
            'docker_compose_path': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'web/sqli_basics'}
            ),
            'image_name': forms.TextInput(attrs={'class': INPUT}),
            'cpu_limit': forms.TextInput(attrs={'class': INPUT}),
            'mem_limit': forms.TextInput(attrs={'class': INPUT}),
            'pids_limit': forms.NumberInput(attrs={'class': INPUT}),
            'read_only_root': forms.CheckboxInput(attrs={'class': CHECKBOX}),
            'default_duration_minutes': forms.NumberInput(attrs={'class': INPUT}),
            'flag_pattern': forms.TextInput(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_docker_compose_path(self):
        return _relative_bundle_path(self.cleaned_data.get('docker_compose_path'))

    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def save(self, commit=True):
        if not self.instance.slug:
            self.instance.slug = _unique_slug(
                LabTemplate, self.instance.name, self.instance
            )
        return super().save(commit=commit)


class LabForm(forms.ModelForm):
    """A student-facing lab exercise, optionally shipping a zip bundle."""

    learning_objectives = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
        help_text='One learning objective per line.',
    )
    tasks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TEXTAREA, 'rows': 10}),
        help_text='JSON array: [{"title": "...", "hint": "...", "points": 20, '
                  '"flag_required": true}]',
    )
    bundle = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': INPUT, 'accept': '.zip'}),
        help_text='Optional .zip bundle (Dockerfile, target app, README). '
                  'Unpacked into cyber/labs/<category>/<slug>/.',
    )

    class Meta:
        model = Lab
        fields = (
            'lesson', 'template', 'title', 'slug', 'difficulty', 'lab_type',
            'description', 'learning_objectives', 'prerequisites', 'tasks',
            'points', 'estimated_minutes', 'instructor_notes',
        )
        widgets = {
            'lesson': forms.Select(attrs={'class': INPUT}),
            'template': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'auto from title'}),
            'difficulty': forms.Select(attrs={'class': INPUT}),
            'lab_type': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 5}),
            'prerequisites': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'points': forms.NumberInput(attrs={'class': INPUT}),
            'estimated_minutes': forms.NumberInput(attrs={'class': INPUT}),
            'instructor_notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['template'].required = False
        self.fields['template'].queryset = LabTemplate.objects.order_by('name')
        self.fields['template'].empty_label = '— build one from a bundle —'
        if self.instance and self.instance.pk:
            if self.instance.learning_objectives:
                self.fields['learning_objectives'].initial = '\n'.join(
                    self.instance.learning_objectives
                )
            if self.instance.tasks:
                self.fields['tasks'].initial = json.dumps(
                    self.instance.tasks, indent=2, ensure_ascii=False
                )

    # -- validation -----------------------------------------------------
    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def clean_learning_objectives(self):
        return [line.strip() for line in
                (self.cleaned_data.get('learning_objectives') or '').splitlines()
                if line.strip()]

    def clean_tasks(self):
        raw = (self.cleaned_data.get('tasks') or '').strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("Tasks must be valid JSON.")
        if not isinstance(data, list):
            raise forms.ValidationError("Tasks must be a JSON array.")
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict):
                raise forms.ValidationError(f"Task #{i} must be a JSON object.")
            if not item.get('title'):
                raise forms.ValidationError(f"Task #{i} needs a title.")
        return data

    def clean_bundle(self):
        bundle = self.cleaned_data.get('bundle')
        if not bundle:
            return None
        if bundle.size > _max_bundle_bytes():
            raise forms.ValidationError(
                f"Bundle is too large (limit {settings.CYBER_BUNDLE_MAX_MB} MB)."
            )
        try:
            validate_bundle(bundle)
        except BundleError as exc:
            raise forms.ValidationError(str(exc))
        return bundle

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('bundle') is None and not cleaned.get('template'):
            raise forms.ValidationError(
                "Pick an existing lab template or upload a bundle to create one."
            )
        return cleaned

    # -- save ------------------------------------------------------------
    def save(self, commit=True):
        """Create the Lab (and its LabTemplate) and unpack any bundle."""
        # _post_clean() already copied cleaned_data onto the instance, so the
        # template/slug fix-ups below are written straight onto it.
        if not self.instance.slug:
            self.instance.slug = _unique_slug(Lab, self.instance.title, self.instance)

        template = (
            LabTemplate.objects.filter(pk=self.instance.template_id).first()
            if self.instance.template_id else None
        )
        category = template.category if template else LabCategory.WEB
        bundle = self.cleaned_data.get('bundle')

        if bundle is not None:
            folder = bundle_dir(settings.CYBER_LAB_DIR, category, self.instance.slug)
            extract_bundle(bundle, folder)          # raises BundleError
            if template is None:
                template = LabTemplate.objects.create(
                    name=self.instance.title,
                    slug=self.instance.slug,
                    category=category,
                    description=self.instance.description or '',
                    docker_compose_path=f'{category}/{self.instance.slug}',
                    image_name=f'cyber/{self.instance.slug}:latest',
                )
            elif not template.docker_compose_path:
                template.docker_compose_path = f'{category}/{template.slug}'
                template.save(update_fields=['docker_compose_path'])
            self.instance.template = template

        return super().save(commit=commit)


class LabBundleUploadForm(forms.ModelForm):
    """Standalone "upload a lab" flow: files + LabTemplate in one step."""

    bundle = forms.FileField(
        widget=forms.FileInput(attrs={'class': INPUT, 'accept': '.zip'}),
        help_text='.zip containing the Dockerfile and target source.',
    )

    class Meta:
        model = LabTemplate
        fields = ('name', 'slug', 'category', 'description')
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'SQL Injection Basics'}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'auto from name'}),
            'category': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def clean_bundle(self):
        bundle = self.cleaned_data.get('bundle')
        if bundle.size > _max_bundle_bytes():
            raise forms.ValidationError(
                f"Bundle is too large (limit {settings.CYBER_BUNDLE_MAX_MB} MB)."
            )
        try:
            validate_bundle(bundle)
        except BundleError as exc:
            raise forms.ValidationError(str(exc))
        return bundle

    def save(self, commit=True):
        if not self.instance.slug:
            self.instance.slug = _unique_slug(
                LabTemplate, self.instance.name, self.instance
            )
        slug, category = self.instance.slug, self.instance.category
        self.instance.docker_compose_path = f'{category}/{slug}'
        self.instance.image_name = f'cyber/{slug}:latest'
        extract_bundle(self.cleaned_data['bundle'],
                       bundle_dir(settings.CYBER_LAB_DIR, category, slug))
        return super().save(commit=commit)
