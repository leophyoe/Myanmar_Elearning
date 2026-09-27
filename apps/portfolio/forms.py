from datetime import date

from django import forms

from apps.courses.forms import INPUT, TEXTAREA
from .models import (
    ExternalCertificate, PortfolioEntry, PortfolioLink, PortfolioProject, Skill,
)

MAX_CERT_MB = 10
ALLOWED_CERT_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg']


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ('name', 'category', 'level', 'order')
        widgets = {
            'name': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Penetration testing'}
            ),
            'category': forms.Select(attrs={'class': INPUT}),
            'level': forms.NumberInput(
                attrs={'class': INPUT, 'min': '1', 'max': '5'}
            ),
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': '0'}),
        }

    def clean_level(self):
        level = self.cleaned_data.get('level')
        if level is None:
            return level
        if not 1 <= level <= 5:
            raise forms.ValidationError('Level must be between 1 and 5.')
        return level


class PortfolioLinkForm(forms.ModelForm):
    class Meta:
        model = PortfolioLink
        fields = ('kind', 'label', 'url', 'order')
        widgets = {
            'kind': forms.Select(attrs={'class': INPUT}),
            'label': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'My GitHub profile'}
            ),
            'url': forms.URLInput(
                attrs={'class': INPUT, 'placeholder': 'https://github.com/username'}
            ),
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': '0'}),
        }

    def clean_url(self):
        url = (self.cleaned_data.get('url') or '').strip()
        if not url.startswith(('http://', 'https://')):
            raise forms.ValidationError('Use a full URL starting with https://')
        return url


class ExternalCertificateForm(forms.ModelForm):
    class Meta:
        model = ExternalCertificate
        fields = (
            'title', 'issuer', 'credential_id', 'credential_url',
            'issued_on', 'expires_on', 'document', 'note',
        )
        widgets = {
            'title': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'CCNA — Routing & Switching'}
            ),
            'issuer': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Cisco Systems'}
            ),
            'credential_id': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'CSCO12345678'}
            ),
            'credential_url': forms.URLInput(
                attrs={'class': INPUT, 'placeholder': 'https://badges.credly.com/…'}
            ),
            'issued_on': forms.DateInput(
                attrs={'class': INPUT, 'type': 'date'}
            ),
            'expires_on': forms.DateInput(
                attrs={'class': INPUT, 'type': 'date'}
            ),
            'document': forms.ClearableFileInput(attrs={'class': INPUT}),
            'note': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
        }

    def clean_issued_on(self):
        issued = self.cleaned_data.get('issued_on')
        if issued and issued > date.today():
            raise forms.ValidationError('Issue date cannot be in the future.')
        return issued

    def clean(self):
        cleaned = super().clean()
        issued = cleaned.get('issued_on')
        expires = cleaned.get('expires_on')
        if issued and expires and expires < issued:
            self.add_error('expires_on', 'Expiry cannot be earlier than the issue date.')
        return cleaned

    def clean_document(self):
        upload = self.cleaned_data.get('document')
        if upload and hasattr(upload, 'size'):
            limit = MAX_CERT_MB * 1024 * 1024
            if upload.size > limit:
                raise forms.ValidationError(
                    f'Document is {upload.size // (1024 * 1024)} MB — the limit is '
                    f'{MAX_CERT_MB} MB.'
                )
            ext = upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else ''
            if ext not in ALLOWED_CERT_EXTENSIONS:
                raise forms.ValidationError(
                    f'Upload a {", ".join(ALLOWED_CERT_EXTENSIONS)} file.'
                )
        return upload


class PortfolioProjectForm(forms.ModelForm):
    class Meta:
        model = PortfolioProject
        fields = (
            'title', 'category', 'excerpt', 'description', 'client', 'role',
            'tools', 'cover', 'external_url', 'completed_on', 'is_published',
            'order',
        )
        widgets = {
            'title': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Company website redesign'}
            ),
            'category': forms.Select(attrs={'class': INPUT}),
            'excerpt': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'One-line summary for the card'}
            ),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
            'client': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Client or company'}
            ),
            'role': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Frontend developer'}
            ),
            'tools': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'Django, Tailwind, Postgres'}
            ),
            'cover': forms.ClearableFileInput(attrs={'class': INPUT}),
            'external_url': forms.URLInput(
                attrs={'class': INPUT, 'placeholder': 'https://…'}
            ),
            'completed_on': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'mr-2'}),
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': '0'}),
        }

    def clean_external_url(self):
        url = (self.cleaned_data.get('external_url') or '').strip()
        if url and not url.startswith(('http://', 'https://')):
            raise forms.ValidationError('Use a full URL starting with https://')
        return url

    def clean_cover(self):
        cover = self.cleaned_data.get('cover')
        if cover and hasattr(cover, 'size'):
            limit = MAX_CERT_MB * 1024 * 1024
            if cover.size > limit:
                raise forms.ValidationError(
                    f'Image is {cover.size // (1024 * 1024)} MB — the limit is '
                    f'{MAX_CERT_MB} MB.'
                )
        return cover


class PortfolioEntryForm(forms.ModelForm):
    class Meta:
        model = PortfolioEntry
        fields = (
            'kind', 'institution', 'title', 'location',
            'start_on', 'end_on', 'is_current', 'details', 'order',
        )
        widgets = {
            'kind': forms.Select(attrs={'class': INPUT}),
            'institution': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'University of Yangon'}
            ),
            'title': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': 'BSc Computer Science'}
            ),
            'location': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Yangon'}),
            'start_on': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'end_on': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'mr-2'}),
            'details': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': INPUT, 'min': '0'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_on')
        end = cleaned.get('end_on')
        if start and end and end < start:
            self.add_error('end_on', 'End date cannot be earlier than the start date.')
        return cleaned
