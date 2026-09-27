from django.views.generic import TemplateView
from apps.courses.models import Course, CourseCategory

class HomePageView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['featured_courses'] = Course.objects.filter(status='PUBLISHED').prefetch_related('categories')[:6]
        context['categories'] = CourseCategory.objects.all()[:8]
        context['total_courses'] = Course.objects.filter(status='PUBLISHED').count()
        return context


class PlaceholderView(TemplateView):
    """Clean placeholder for upcoming modules (Labs, CTF, Certificates, Exams)."""
    template_name = 'placeholder.html'

