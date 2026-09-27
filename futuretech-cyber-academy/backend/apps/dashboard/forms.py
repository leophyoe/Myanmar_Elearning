from django import forms
from apps.courses.models import Course, CourseModule, Lesson, CourseResource, CourseCategory

class CourseCreationForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=CourseCategory.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'text-cyan-500'}),
        required=False
    )

    class Meta:
        model = Course
        fields = ('title', 'slug', 'short_description', 'description', 'level', 'duration', 'language', 'price', 'is_free', 'categories')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'e.g. Linux Security & System Hardening'}),
            'slug': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'linux-security-hardening'}),
            'short_description': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'Brief overview for course cards'}),
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'Full curriculum syllabus and overview in Markdown'}),
            'level': forms.Select(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'duration': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'e.g. 6 Months or 40 Hours'}),
            'language': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'is_free': forms.CheckboxInput(attrs={'class': 'rounded bg-slate-900 border-slate-700 text-cyan-500'}),
        }


class CourseModuleForm(forms.ModelForm):
    class Meta:
        model = CourseModule
        fields = ('title', 'slug', 'description', 'order', 'estimated_hours')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'slug': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
        }


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ('title', 'slug', 'lesson_type', 'content', 'video_url', 'order', 'estimated_minutes', 'is_published')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'slug': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'lesson_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'content': forms.Textarea(attrs={'rows': 6, 'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500 font-mono'}),
            'video_url': forms.URLInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500', 'placeholder': 'https://vimeo.com/... or https://youtube.com/...'}),
            'order': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'rounded bg-slate-900 border-slate-700 text-cyan-500'}),
        }


class CourseResourceForm(forms.ModelForm):
    class Meta:
        model = CourseResource
        fields = ('title', 'file', 'resource_type', 'description', 'external_link')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'resource_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
            'external_link': forms.URLInput(attrs={'class': 'w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-cyan-500'}),
        }

