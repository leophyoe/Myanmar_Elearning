from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from apps.labs.models import LabInstance

class TerminalView(LoginRequiredMixin, DetailView):
    model = LabInstance
    template_name = 'terminal/terminal.html'
    context_object_name = 'instance'
    pk_url_kwarg = 'instance_id'

    def get_queryset(self):
        # Only allow students to view their own running instances (or super admins)
        if self.request.user.is_admin:
            return LabInstance.objects.all()
        return LabInstance.objects.filter(user=self.request.user)

