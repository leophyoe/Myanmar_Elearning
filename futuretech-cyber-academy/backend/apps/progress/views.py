from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from .models import LessonProgress
from apps.courses.models import Lesson

class ToggleLessonCompleteView(LoginRequiredMixin, View):
    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)

        progress, _ = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson
        )

        # Toggle state
        if not progress.completed:
            progress.mark_completed()
        else:
            progress.completed = False
            progress.completed_at = None
            progress.save(update_fields=['completed', 'completed_at', 'updated_at'])
            from .services import ProgressCalculationService
            ProgressCalculationService.update_course_progress(request.user, lesson.module.course)

        # HTMX partial rendering support
        if request.headers.get('HX-Request'):
            return render(request, 'components/_completion_button.html', {
                'lesson': lesson,
                'completed': progress.completed
            })

        return redirect('lesson-learn', course_slug=lesson.module.course.slug, lesson_slug=lesson.slug)

