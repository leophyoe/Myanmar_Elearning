from django.views.generic import (
    ListView, DetailView, View, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy, reverse

from apps.common.permissions import RoleRequiredMixin
from .models import Subject, Course, Module, Lesson, Quiz, Question, Choice, UserProgress, Enrollment
from .forms import SubjectForm, CourseForm, ModuleForm, LessonForm


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def can_access_course(user, course):
    """Teachers/admins always see a course; students must hold an active enrollment."""
    if user.is_teacher or user.is_admin:
        return True
    return Enrollment.objects.filter(
        course=course, student=user, status=Enrollment.Status.ACTIVE
    ).exists()


def course_progress_pct(user, course):
    total = Lesson.objects.filter(module__course=course).count()
    if not total:
        return 0
    done = UserProgress.objects.filter(
        user=user, course=course, is_completed=True, lesson__isnull=False
    ).count()
    return int((done / total) * 100)


def sync_enrollment_progress(user, course):
    """Recompute and persist the stored percentage on the student's enrollment."""
    enrollment = Enrollment.objects.filter(
        course=course, student=user, status=Enrollment.Status.ACTIVE
    ).first()
    if not enrollment:
        return None
    enrollment.progress_pct = course_progress_pct(user, course)
    if enrollment.progress_pct >= 100:
        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=['progress_pct', 'status', 'completed_at'])
    return enrollment


# ----------------------------------------------------------------------
# Catalogue (public)
# ----------------------------------------------------------------------
class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        return Course.objects.filter(is_published=True).prefetch_related('modules__lessons', 'subject')


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        context['modules'] = course.modules.all().prefetch_related('lessons')
        context['total_lessons'] = Lesson.objects.filter(module__course=course).count()

        user = self.request.user
        if user.is_authenticated:
            context['completed_lesson_ids'] = set(
                UserProgress.objects.filter(
                    user=user, is_completed=True, lesson__isnull=False
                ).values_list('lesson_id', flat=True)
            )
            enrollment = Enrollment.objects.filter(course=course, student=user).first()
            context['enrollment'] = enrollment
            context['is_enrolled'] = bool(
                enrollment and enrollment.status == Enrollment.Status.ACTIVE
            )
            context['progress_pct'] = course_progress_pct(user, course) if enrollment else 0
            context['can_manage'] = user.is_teacher or user.is_admin
        return context


class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module_detail.html'
    context_object_name = 'module'
    pk_url_kwarg = 'module_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.object.course
        return context


class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = 'courses/lesson_detail.html'
    context_object_name = 'lesson'
    pk_url_kwarg = 'lesson_id'

    def dispatch(self, request, *args, **kwargs):
        lesson = self.get_object()
        if not can_access_course(request.user, lesson.module.course):
            messages.info(request, "Please enrol in this course before opening its lessons.")
            return redirect('course-detail', slug=lesson.module.course.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.get_object()
        course = lesson.module.course
        context['quiz'] = getattr(lesson, 'quiz', None)
        context['course'] = course
        context['type_label'] = lesson.get_lesson_type_display()

        progress, _ = UserProgress.objects.get_or_create(
            user=self.request.user,
            course=course,
            module=lesson.module,
            lesson=lesson,
        )
        context['progress'] = progress
        context['labs'] = lesson.labs.filter(is_active=True)
        return context


# ----------------------------------------------------------------------
# Enrollment
# ----------------------------------------------------------------------
class EnrollView(LoginRequiredMixin, View):
    """POST-only course enrolment."""

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug, is_published=True)

        if not request.user.is_student:
            messages.info(request, "Staff accounts do not need to enrol.")
            return redirect('course-detail', slug=slug)

        enrollment, created = Enrollment.objects.get_or_create(
            course=course, student=request.user,
            defaults={'status': Enrollment.Status.ACTIVE},
        )
        if not created:
            if enrollment.status == Enrollment.Status.DROPPED:
                enrollment.status = Enrollment.Status.ACTIVE
                enrollment.save(update_fields=['status'])
                messages.success(request, f"Welcome back to {course.title}!")
            else:
                messages.info(request, f"You are already enrolled in {course.title}.")
        else:
            messages.success(request, f"Enrolled in {course.title}. Happy learning!")

        return redirect('course-detail', slug=slug)


class MyCoursesView(LoginRequiredMixin, ListView):
    template_name = 'courses/my_courses.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        return Enrollment.objects.filter(student=self.request.user).select_related('course__subject')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for enrollment in context['enrollments']:
            enrollment.live_progress = course_progress_pct(self.request.user, enrollment.course)
        return context


# ----------------------------------------------------------------------
# Quiz / progress
# ----------------------------------------------------------------------
class QuizSubmitView(LoginRequiredMixin, View):
    """Evaluates student quiz submissions and updates progress and points."""

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if not can_access_course(request.user, lesson.module.course):
            messages.info(request, "Please enrol in this course first.")
            return redirect('course-detail', slug=lesson.module.course.slug)

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

            sync_enrollment_progress(request.user, lesson.module.course)
            messages.success(request, f"Passed! You scored {score_pct}% ({correct_count}/{total_questions}) and earned {points_earned} points!")
        else:
            messages.error(request, f"Score: {score_pct}%. Passing score is {quiz.passing_percentage}%. Please review the materials and try again.")

        return redirect('lesson-detail', lesson_id=lesson.id)


# ----------------------------------------------------------------------
# Teacher / Administrator authoring (Phase 2)
# ----------------------------------------------------------------------
class TeacherRequiredMixin(RoleRequiredMixin):
    """Restricts a view to TEACHER and ADMIN accounts."""
    allowed_roles = ['teacher']


class ManageHomeView(TeacherRequiredMixin, TemplateView):
    """Authoring cockpit: subjects, courses, modules and lessons at a glance."""
    template_name = 'courses/manage/manage_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subjects'] = Subject.objects.all().prefetch_related('courses')
        context['courses'] = Course.objects.all().prefetch_related('modules__lessons', 'subject')
        return context


class SubjectCreateView(TeacherRequiredMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'courses/manage/subject_form.html'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, f"Subject “{form.cleaned_data['title']}” created.")
        return super().form_valid(form)


class SubjectUpdateView(TeacherRequiredMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'courses/manage/subject_form.html'
    pk_url_kwarg = 'subject_id'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Subject updated.")
        return super().form_valid(form)


class CourseCreateView(TeacherRequiredMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'
    success_url = reverse_lazy('manage-home')

    def get_initial(self):
        initial = super().get_initial()
        subject_id = self.request.GET.get('subject')
        if subject_id:
            initial['subject'] = subject_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, f"Course “{form.cleaned_data['title']}” created.")
        return super().form_valid(form)


class CourseUpdateView(TeacherRequiredMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Course updated.")
        return super().form_valid(form)


class ModuleCreateView(TeacherRequiredMixin, CreateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/manage/module_form.html'
    success_url = reverse_lazy('manage-home')

    def get_initial(self):
        initial = super().get_initial()
        course_pk = self.request.GET.get('course')
        if course_pk:
            initial['course'] = course_pk
        initial['order'] = (Module.objects.count() + 1)
        return initial

    def form_valid(self, form):
        messages.success(self.request, f"Module {form.cleaned_data['code']} created.")
        return super().form_valid(form)


class ModuleUpdateView(TeacherRequiredMixin, UpdateView):
    model = Module
    form_class = ModuleForm
    template_name = 'courses/manage/module_form.html'
    pk_url_kwarg = 'module_id'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Module updated.")
        return super().form_valid(form)


class LessonCreateView(TeacherRequiredMixin, CreateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/manage/lesson_form.html'

    def get_initial(self):
        initial = super().get_initial()
        module_pk = self.request.GET.get('module')
        if module_pk:
            initial['module'] = module_pk
        if module_pk:
            initial['order'] = Lesson.objects.filter(module_id=module_pk).count() + 1
        return initial

    def get_success_url(self):
        return reverse('module-edit', kwargs={'module_id': self.object.module_id})

    def form_valid(self, form):
        messages.success(self.request, f"Lesson “{form.cleaned_data['title']}” created.")
        return super().form_valid(form)


class LessonUpdateView(TeacherRequiredMixin, UpdateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/manage/lesson_form.html'
    pk_url_kwarg = 'lesson_id'

    def get_success_url(self):
        return reverse('module-edit', kwargs={'module_id': self.object.module_id})

    def form_valid(self, form):
        messages.success(self.request, "Lesson updated.")
        return super().form_valid(form)


class LessonDeleteView(TeacherRequiredMixin, DeleteView):
    model = Lesson
    template_name = 'courses/manage/lesson_confirm_delete.html'
    pk_url_kwarg = 'lesson_id'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Lesson deleted.")
        return super().form_valid(form)
