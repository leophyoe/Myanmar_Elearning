from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import FinalProject, ProjectSubmission

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

