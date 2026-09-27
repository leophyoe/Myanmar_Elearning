"""Teacher-facing authoring forms for CTF challenges."""

import json

from django import forms
from django.conf import settings

from apps.labs.bundles import BundleError, bundle_dir, extract_bundle, validate_bundle
from apps.labs.forms import INPUT, TEXTAREA, _unique_slug
from .models import Challenge, ChallengeCategory

class ChallengeForm(forms.ModelForm):
    """Create/edit a CTF challenge, optionally shipping a zip bundle.

    ``static_flag`` is write-only: it is hashed on the way in and never shown
    again. Leave it blank to keep the existing flag / dynamic flags.
    """

    static_flag = forms.CharField(
        required=False,
        label='Static flag (write-only)',
        widget=forms.PasswordInput(attrs={'class': INPUT}, render_value=False),
        help_text='Stored as a SHA-256 hash — the plaintext is never kept. '
                  'Leave blank to keep the current flag.',
    )
    hints = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
        help_text='JSON array: [{"hint": "...", "cost": 10}]',
    )
    bundle = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': INPUT, 'accept': '.zip'}),
        help_text='Optional .zip bundle (task files, fixtures, solver notes). '
                  'Unpacked into cyber/challenges/<category>/<slug>/.',
    )

    class Meta:
        model = Challenge
        fields = (
            'title', 'slug', 'category', 'difficulty', 'description', 'points',
            'is_dynamic', 'lab', 'module', 'hints', 'max_attempts',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'auto from title'}),
            'category': forms.Select(attrs={'class': INPUT}),
            'difficulty': forms.Select(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 6}),
            'points': forms.NumberInput(attrs={'class': INPUT}),
            'is_dynamic': forms.CheckboxInput(attrs={'class': 'accent-cyan-500'}),
            'lab': forms.Select(attrs={'class': INPUT}),
            'module': forms.Select(attrs={'class': INPUT}),
            'max_attempts': forms.NumberInput(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['lab'].required = False
        self.fields['lab'].empty_label = '— none (static flag challenge) —'
        self.fields['module'].required = False
        self.fields['module'].empty_label = '— none —'
        if self.instance and self.instance.pk and self.instance.hints:
            self.fields['hints'].initial = json.dumps(
                self.instance.hints, indent=2, ensure_ascii=False
            )

    # -- validation -----------------------------------------------------
    def clean_slug(self):
        return (self.cleaned_data.get('slug') or '').strip()

    def clean_hints(self):
        raw = (self.cleaned_data.get('hints') or '').strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("Hints must be valid JSON.")
        if not isinstance(data, list):
            raise forms.ValidationError("Hints must be a JSON array.")
        for i, item in enumerate(data, 1):
            if not isinstance(item, dict) or not item.get('hint'):
                raise forms.ValidationError(f"Hint #{i} needs a \"hint\" key.")
        return data

    def clean_static_flag(self):
        value = (self.cleaned_data.get('static_flag') or '').strip()
        if value and not value.startswith('FTCR{'):
            raise forms.ValidationError(
                'Flags start with the platform prefix, e.g. FTCR{...}.'
            )
        return value

    def clean_bundle(self):
        bundle = self.cleaned_data.get('bundle')
        if not bundle:
            return None
        if bundle.size > settings.CYBER_BUNDLE_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Bundle is too large (limit {settings.CYBER_BUNDLE_MAX_MB} MB)."
            )
        try:
            validate_bundle(bundle)
        except BundleError as exc:
            raise forms.ValidationError(str(exc))
        return bundle

    # -- save ------------------------------------------------------------
    def save(self, commit=True):
        if not self.instance.slug:
            self.instance.slug = _unique_slug(
                Challenge, self.instance.title, self.instance
            )

        static_flag = self.cleaned_data.pop('static_flag', '')
        bundle = self.cleaned_data.get('bundle')

        if bundle is not None:
            folder = bundle_dir(settings.CYBER_CHALLENGE_DIR,
                                self.instance.category,
                                self.instance.slug)
            extract_bundle(bundle, folder)

        instance = super().save(commit=False)
        if static_flag:
            instance.set_static_flag(static_flag)
        if commit:
            instance.save()
        return instance
