from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from .models import FinalProject, ProjectSubmission
from .forms import ProjectProposalForm, ProjectReportSubmissionForm


class ProjectListView(LoginRequiredMixin, ListView):
    model = FinalProject
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        return FinalProject.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['my_submissions'] = ProjectSubmission.objects.filter(student=self.request.user)
        return context


class ProjectProposalSubmitView(LoginRequiredMixin, View):
    def get(self, request, slug):
        project = get_object_or_404(FinalProject, slug=slug, is_active=True)
        submission = ProjectSubmission.objects.filter(project=project, student=request.user).first()
        form = ProjectProposalForm(instance=submission)
        return render(request, 'projects/proposal_form.html', {
            'project': project,
            'form': form,
            'submission': submission,
        })

    def post(self, request, slug):
        project = get_object_or_404(FinalProject, slug=slug, is_active=True)
        submission = ProjectSubmission.objects.filter(project=project, student=request.user).first()
        form = ProjectProposalForm(request.POST, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.project = project
            sub.student = request.user
            sub.status = ProjectSubmission.Status.SUBMITTED
            sub.save()
            messages.success(request, 'Capstone proposal submitted successfully for evaluation.')
            return redirect(reverse('project-submission-detail', kwargs={'slug': project.slug}))
        return render(request, 'projects/proposal_form.html', {
            'project': project,
            'form': form,
            'submission': submission,
        })


class ProjectSubmissionDetailView(LoginRequiredMixin, View):
    def get(self, request, slug):
        project = get_object_or_404(FinalProject, slug=slug)
        submission = get_object_or_404(ProjectSubmission, project=project, student=request.user)
        report_form = ProjectReportSubmissionForm(instance=submission)
        return render(request, 'projects/submission_detail.html', {
            'project': project,
            'submission': submission,
            'report_form': report_form,
        })


class ProjectReportUploadView(LoginRequiredMixin, View):
    def post(self, request, slug):
        project = get_object_or_404(FinalProject, slug=slug)
        submission = get_object_or_404(ProjectSubmission, project=project, student=request.user)
        form = ProjectReportSubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.status = ProjectSubmission.Status.SUBMITTED_FOR_GRADING
            sub.save()
            messages.success(request, 'Final project audit report submitted for grading.')
        else:
            messages.error(request, 'Error uploading report. Please check file format.')
        return redirect(reverse('project-submission-detail', kwargs={'slug': project.slug}))
