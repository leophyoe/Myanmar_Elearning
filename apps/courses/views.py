from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from .models import Course, Module, Lesson, Quiz, Question, Choice, UserProgress

class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        return Course.objects.filter(is_published=True).prefetch_related('modules')


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        modules = course.modules.all().prefetch_related('lessons')
        context['modules'] = modules

        if self.request.user.is_authenticated:
            completed_lesson_ids = set(
                UserProgress.objects.filter(
                    user=self.request.user,
                    is_completed=True,
                    lesson__isnull=False
                ).values_list('lesson_id', flat=True)
            )
            context['completed_lesson_ids'] = completed_lesson_ids
        return context


class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module_detail.html'
    context_object_name = 'module'
    pk_url_kwarg = 'module_id'


class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = 'courses/lesson_detail.html'
    context_object_name = 'lesson'
    pk_url_kwarg = 'lesson_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.get_object()
        context['quiz'] = getattr(lesson, 'quiz', None)

        # Mark lesson viewed / track progress
        progress, created = UserProgress.objects.get_or_create(
            user=self.request.user,
            course=lesson.module.course,
            module=lesson.module,
            lesson=lesson,
        )
        context['progress'] = progress

        # If this lesson has an attached hands-on lab, include it
        context['labs'] = lesson.labs.filter(is_active=True)
        return context


class QuizSubmitView(LoginRequiredMixin, View):
    """Evaluates student quiz submissions and updates progress and points."""

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        quiz = get_object_or_404(Quiz, lesson=lesson)
        questions = quiz.questions.all().prefetch_related('choices')

        total_questions = questions.count()
        if total_questions == 0:
            messages.warning(request, "This quiz contains no questions.")
            return redirect('lesson-detail', lesson_id=lesson.id)

        correct_count = 0
        points_earned = 0

        for question in questions:
            selected_choice_id = request.POST.get(f"question_{question.id}")
            if selected_choice_id:
                try:
                    choice = Choice.objects.get(id=selected_choice_id, question=question)
                    if choice.is_correct:
                        correct_count += 1
                        points_earned += question.points
                except Choice.DoesNotExist:
                    pass

        score_pct = int((correct_count / total_questions) * 100)
        passed = score_pct >= quiz.passing_percentage

        if passed:
            progress, _ = UserProgress.objects.get_or_create(
                user=request.user,
                course=lesson.module.course,
                module=lesson.module,
                lesson=lesson
            )
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()

            profile = getattr(request.user, 'student_profile', None)
            if profile:
                profile.points += points_earned
                profile.save(update_fields=['points'])

            messages.success(request, f"Passed! You scored {score_pct}% ({correct_count}/{total_questions}) and earned {points_earned} points!")
        else:
            messages.error(request, f"Score: {score_pct}%. Passing score is {quiz.passing_percentage}%. Please review the materials and try again.")

        return redirect('lesson-detail', lesson_id=lesson.id)

