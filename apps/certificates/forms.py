from django import forms
from .models import CertificateTemplate
from apps.courses.forms import INPUT, TEXTAREA


class CertificateTemplateForm(forms.ModelForm):
    """
    Form for authoring and configuring Certificate Templates.
    Supports both:
    1. Built-in aesthetic themes (Classic Gold, Academic Emerald, Cyber Tech, Minimalist Luxury)
    2. Custom background upload (PNG / JPG A4 template) with fine-grained coordinates.
    """
    class Meta:
        model = CertificateTemplate
        fields = (
            'title',
            'design_mode',
            'theme_style',
            'background_image',
            'partner',
            'institution_name',
            'header_title',
            'subtitle',
            'body_text',
            'font_choice',
            'primary_color',
            'accent_color',
            'name_pos_top',
            'name_color',
            'name_font_size',
            'title_pos_top',
            'title_color',
            'title_font_size',
            'date_pos_top',
            'date_pos_left',
            'qr_pos_top',
            'qr_pos_left',
            'serial_pos_top',
            'serial_pos_left',
            'logo_image',
            'partner_logo',
            'signature_1_image',
            'signature_1_name',
            'signature_1_title',
            'signature_2_image',
            'signature_2_name',
            'signature_2_title',
            'show_qr_code',
            'show_seal',
            'is_default',
            'is_active',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Masterclass Python Diploma, UCSP Cyber Certificate'}),
            'design_mode': forms.Select(attrs={'class': INPUT, 'id': 'id_design_mode'}),
            'theme_style': forms.Select(attrs={'class': INPUT, 'id': 'id_theme_style'}),
            'background_image': forms.ClearableFileInput(attrs={'class': INPUT, 'accept': 'image/png, image/jpeg, image/webp'}),
            'partner': forms.Select(attrs={'class': INPUT}),
            'institution_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. MYANMAR E-LEARNING (THUTA)'}),
            'header_title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. CERTIFICATE OF COMPLETION'}),
            'subtitle': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. This is proudly awarded to'}),
            'body_text': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. for successfully mastering the curriculum of'}),
            'font_choice': forms.Select(attrs={'class': INPUT, 'id': 'id_font_choice'}),
            'primary_color': forms.TextInput(attrs={'class': INPUT, 'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'class': INPUT, 'type': 'color'}),

            'name_pos_top': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '44'}),
            'name_color': forms.TextInput(attrs={'class': INPUT, 'type': 'color'}),
            'name_font_size': forms.NumberInput(attrs={'class': INPUT, 'min': '14', 'max': '72', 'placeholder': '34'}),

            'title_pos_top': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '58'}),
            'title_color': forms.TextInput(attrs={'class': INPUT, 'type': 'color'}),
            'title_font_size': forms.NumberInput(attrs={'class': INPUT, 'min': '12', 'max': '48', 'placeholder': '22'}),

            'date_pos_top': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '78'}),
            'date_pos_left': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '22'}),

            'qr_pos_top': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '76'}),
            'qr_pos_left': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '50'}),

            'serial_pos_top': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '88'}),
            'serial_pos_left': forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'max': '100', 'placeholder': '50'}),

            'logo_image': forms.ClearableFileInput(attrs={'class': INPUT, 'accept': 'image/*'}),
            'partner_logo': forms.ClearableFileInput(attrs={'class': INPUT, 'accept': 'image/*'}),

            'signature_1_image': forms.ClearableFileInput(attrs={'class': INPUT, 'accept': 'image/*'}),
            'signature_1_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Academic Director'}),
            'signature_1_title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Board of Academic Affairs'}),

            'signature_2_image': forms.ClearableFileInput(attrs={'class': INPUT, 'accept': 'image/*'}),
            'signature_2_name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Lead Instructor'}),
            'signature_2_title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Faculty Chair'}),

            'show_qr_code': forms.CheckboxInput(attrs={'class': 'accent-cyan-500 h-4 w-4'}),
            'show_seal': forms.CheckboxInput(attrs={'class': 'accent-cyan-500 h-4 w-4'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'accent-cyan-500 h-4 w-4'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'accent-cyan-500 h-4 w-4'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not getattr(self.user, 'is_admin', False) and not self.user.is_superuser:
            # Hide is_default from regular instructors
            self.fields.pop('is_default', None)

