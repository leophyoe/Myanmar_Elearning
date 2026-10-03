from django import forms
from .models import ProjectSubmission

class ProjectProposalForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ['proposal_text', 'github_repo_url']
        widgets = {
            'proposal_text': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500',
                'rows': 6,
                'placeholder': 'Describe your proposed capstone project, scope, architecture, lab topology, and expected security deliverables...'
            }),
            'github_repo_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500',
                'placeholder': 'https://github.com/username/project-repo (optional)'
            }),
        }


class ProjectReportSubmissionForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ['report_file', 'github_repo_url']
        widgets = {
            'github_repo_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500',
                'placeholder': 'https://github.com/username/project-repo'
            }),
        }
