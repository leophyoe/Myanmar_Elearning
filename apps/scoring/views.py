from django.views.generic import ListView
from apps.users.models import StudentProfile
from .models import Badge

class LeaderboardView(ListView):
    model = StudentProfile
    template_name = 'leaderboard/leaderboard.html'
    context_object_name = 'students'

    def get_queryset(self):
        return StudentProfile.objects.select_related('user').order_by('-points', 'student_id')[:50]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['badges'] = Badge.objects.all()
        return context

