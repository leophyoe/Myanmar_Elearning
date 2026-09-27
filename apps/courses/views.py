from django.views.generic import (
    ListView, DetailView, View, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy, reverse

from apps.common.permissions import RoleRequiredMixin, TeacherRequiredMixin
from apps.billing.models import active_payment_for, Payment
from .models import (
    Subject, Course, Module, Lesson, LessonType, Quiz, Question, Choice,
    UserProgress, Enrollment, Assignment, AssignmentSubmission, LiveSession,
)
from .forms import (
    SubjectForm, CourseForm, ModuleForm, LessonForm,
    QuizForm, QuestionFormSet, AssignmentForm, AssignmentSubmitForm,
    SubmissionGradeForm, LiveSessionForm,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def can_access_course(user, course):
    """Teachers/admins always see a course.

    Students need an active enrollment, and on paid courses an approved,
    unexpired payment on top of it (the enrolment alone is not enough).
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_teacher or user.is_admin:
        return True
    if not Enrollment.objects.filter(
        course=course, student=user, status=Enrollment.Status.ACTIVE
    ).exists():
        return False
    if course.is_free:
        return True
    payment = active_payment_for(user, course)
    return bool(payment and payment.is_current)


def course_progress_pct(user, course):
    total = Lesson.objects.filter(module__course=course).count()
    if not total:
        return 0
    done = UserProgress.objects.filter(
        user=user, course=course, is_completed=True, lesson__isnull=False
    ).count()
    return int((done / total) * 100)


def upcoming_live_sessions(course):
    """Published real-time sessions for `course` that have not started yet."""
    return list(
        course.live_sessions.filter(
            is_published=True, starts_at__gte=timezone.now()
        ).order_by('starts_at')
    )


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
        enrollment.completed_at = enrollment.completed_at or timezone.now()
    enrollment.save(update_fields=['progress_pct', 'status', 'completed_at'])

    if enrollment.status == Enrollment.Status.COMPLETED:
        from apps.certificates.services import issue_certificate_for_enrollment
        issue_certificate_for_enrollment(enrollment)
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
            context['has_access'] = can_access_course(user, course)
            context['is_purchased'] = False
            context['pending_payment'] = None
            if not course.is_free:
                payment = active_payment_for(user, course)
                context['is_purchased'] = bool(payment and payment.is_current)
                context['pending_payment'] = Payment.objects.filter(
                    student=user, course=course, status=Payment.Status.PENDING
                ).first()
            context['live_sessions'] = (
                upcoming_live_sessions(course)
                if (user.is_teacher or user.is_admin or context['has_access'])
                else []
            )
        return context


class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module_detail.html'
    context_object_name = 'module'
    pk_url_kwarg = 'module_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.object.course
        context['assignments'] = self.object.assignments.all().order_by('due_date')
        user = self.request.user
        context['can_manage'] = bool(
            user.is_authenticated and (user.is_teacher or user.is_admin)
        )
        return context


class LessonDetailView(LoginRequiredMixin, DetailView):
    model = Lesson
    template_name = 'courses/lesson_detail.html'
    context_object_name = 'lesson'
    pk_url_kwarg = 'lesson_id'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
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
        context['can_manage'] = self.request.user.is_teacher or self.request.user.is_admin
        context['assignments'] = lesson.module.assignments.all().order_by('due_date')
        if self.request.user.is_authenticated:
            context['my_submissions'] = {
                s.assignment_id: s
                for s in AssignmentSubmission.objects.filter(
                    student=self.request.user,
                    assignment__in=context['assignments'],
                )
            }
        else:
            context['my_submissions'] = {}
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

        if not course.is_free:
            payment = active_payment_for(request.user, course)
            if not (payment and payment.is_current):
                messages.info(
                    request,
                    f"{course.title} is a paid course — complete checkout first "
                    f"({course.price} {course.currency} / "
                    f"{course.get_billing_period_display()})."
                )
                return redirect('checkout', slug=slug)

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
class ManageHomeView(TeacherRequiredMixin, TemplateView):
    """Authoring cockpit: subjects, courses, modules and lessons at a glance."""
    template_name = 'courses/manage/manage_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subjects'] = Subject.objects.all().prefetch_related('courses')
        context['courses'] = Course.objects.all().prefetch_related('modules__lessons', 'subject')
        context['ungraded_count'] = AssignmentSubmission.objects.filter(score__isnull=True).count()
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
        form.instance.owner = self.request.user
        messages.success(self.request, f"Course “{form.cleaned_data['title']}” created.")
        return super().form_valid(form)


class CourseUpdateView(TeacherRequiredMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('manage-home')

    def get_queryset(self):
        # Admins edit everything; teachers only their own courses (legacy courses
        # without an owner remain open to every teacher).
        if self.request.user.is_admin:
            return Course.objects.all()
        return Course.objects.filter(owner__isnull=True) | Course.objects.filter(
            owner=self.request.user
        )

    def form_valid(self, form):
        if not form.instance.owner_id:
            form.instance.owner = self.request.user
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


# ----------------------------------------------------------------------
# Phase 3 - quizzes, assignments, submissions and grading
# ----------------------------------------------------------------------
class QuizBuilderView(TeacherRequiredMixin, View):
    """
    One screen for building a lesson's checkpoint quiz: quiz settings plus a
    formset of multiple choice questions, each with four answer slots.
    """

    template_name = 'courses/manage/quiz_form.html'

    def get_object(self, **kwargs):
        return get_object_or_404(Lesson, id=self.kwargs['lesson_id'])

    def _render(self, request, lesson, quiz, quiz_form=None, question_formset=None):
        context = {
            'lesson': lesson,
            'course': lesson.module.course,
            'module': lesson.module,
            'quiz': quiz,
            'form': quiz_form or QuizForm(instance=quiz),
            'question_formset': question_formset or QuestionFormSet(instance=quiz),
        }
        return render(request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        lesson = self.get_object()
        quiz, _ = Quiz.objects.get_or_create(
            lesson=lesson, defaults={'title': f'Checkpoint — {lesson.title}'}
        )
        return self._render(request, lesson, quiz)

    def post(self, request, *args, **kwargs):
        lesson = self.get_object()
        quiz, _ = Quiz.objects.get_or_create(
            lesson=lesson, defaults={'title': f'Checkpoint — {lesson.title}'}
        )
        quiz_form = QuizForm(request.POST, instance=quiz)
        question_formset = QuestionFormSet(request.POST, instance=quiz)

        if quiz_form.is_valid() and question_formset.is_valid():
            saved_quiz = quiz_form.save()
            question_formset.save()
            if not lesson.has_quiz:
                lesson.has_quiz = True
                lesson.save(update_fields=['has_quiz'])
            messages.success(
                request,
                f'Quiz “{saved_quiz.title}” saved with '
                f'{saved_quiz.questions.count()} question(s).'
            )
            return redirect('lesson-detail', lesson_id=lesson.id)

        messages.error(request, 'Please fix the highlighted errors before saving the quiz.')
        return self._render(request, lesson, quiz, quiz_form, question_formset)


class AssignmentCreateView(TeacherRequiredMixin, CreateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'courses/manage/assignment_form.html'
    success_url = reverse_lazy('manage-home')

    def get_initial(self):
        initial = super().get_initial()
        module_pk = self.request.GET.get('module')
        if module_pk:
            initial['module'] = module_pk
        return initial

    def form_valid(self, form):
        messages.success(self.request, f'Assignment “{form.cleaned_data["title"]}” created.')
        return super().form_valid(form)


class AssignmentUpdateView(TeacherRequiredMixin, UpdateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'courses/manage/assignment_form.html'
    pk_url_kwarg = 'assignment_id'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated.')
        return super().form_valid(form)


class AssignmentDeleteView(TeacherRequiredMixin, DeleteView):
    model = Assignment
    template_name = 'courses/manage/assignment_confirm_delete.html'
    pk_url_kwarg = 'assignment_id'
    success_url = reverse_lazy('manage-home')

    def form_valid(self, form):
        messages.success(self.request, 'Assignment deleted.')
        return super().form_valid(form)


def mark_assignment_progress(submission):
    """Passing a graded assignment completes the module's assignment lesson."""
    assignment = submission.assignment
    if submission.score is None or not assignment.max_score:
        return
    if submission.score < assignment.max_score * 0.6:
        return

    module = assignment.module
    lesson = module.lessons.filter(lesson_type=LessonType.ASSIGNMENT).first()
    if not lesson:
        return

    progress, _ = UserProgress.objects.get_or_create(
        user=submission.student,
        course=module.course,
        module=module,
        lesson=lesson,
    )
    if progress.is_completed:
        return
    progress.is_completed = True
    progress.completed_at = timezone.now()
    progress.save(update_fields=['is_completed', 'completed_at'])
    sync_enrollment_progress(submission.student, module.course)


class SubmissionListView(TeacherRequiredMixin, ListView):
    """Grading queue: what still needs a score, and what has been marked."""

    model = AssignmentSubmission
    template_name = 'courses/manage/submission_list.html'
    context_object_name = 'submissions'
    paginate_by = 25

    STATUS_FILTERS = {
        'ungraded': {'score__isnull': True},
        'graded': {'score__isnull': False},
    }

    def get_status(self):
        status = self.request.GET.get('status', 'ungraded')
        return status if status in self.STATUS_FILTERS else 'ungraded'

    def get_queryset(self):
        qs = AssignmentSubmission.objects.select_related(
            'assignment__module__course', 'student', 'graded_by'
        ).order_by('-created_at')
        return qs.filter(**self.STATUS_FILTERS[self.get_status()])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status'] = self.get_status()
        context['ungraded_count'] = AssignmentSubmission.objects.filter(score__isnull=True).count()
        context['graded_count'] = AssignmentSubmission.objects.filter(score__isnull=False).count()
        context['assignments'] = Assignment.objects.select_related('module__course').order_by(
            'module__course__title', 'module__order'
        )
        return context


class SubmissionGradeView(TeacherRequiredMixin, UpdateView):
    model = AssignmentSubmission
    form_class = SubmissionGradeForm
    template_name = 'courses/manage/grade_submission.html'
    pk_url_kwarg = 'submission_id'

    def get_queryset(self):
        return AssignmentSubmission.objects.select_related(
            'assignment__module__course', 'student'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assignment'] = self.object.assignment
        return context

    def form_valid(self, form):
        submission = form.save(commit=False)
        submission.graded_by = self.request.user
        submission.graded_at = timezone.now()
        submission.save()
        mark_assignment_progress(submission)
        messages.success(
            self.request,
            f'Graded {submission.student.get_full_name() or submission.student.username}: '
            f'{submission.score}/{submission.assignment.max_score}.'
        )
        return redirect('submission-list')


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    """Student view of an assignment plus their own hand-in state."""

    model = Assignment
    template_name = 'courses/assignment_detail.html'
    pk_url_kwarg = 'assignment_id'
    context_object_name = 'assignment'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        assignment = self.get_object()
        if not can_access_course(request.user, assignment.module.course):
            messages.info(request, 'Please enrol in this course before opening its assignments.')
            return redirect('course-detail', slug=assignment.module.course.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        context['course'] = assignment.module.course
        context['module'] = assignment.module
        context['submission'] = AssignmentSubmission.objects.filter(
            assignment=assignment, student=self.request.user
        ).first()
        context['submission_form'] = AssignmentSubmitForm(
            instance=context['submission']
        )
        context['total_submissions'] = assignment.submissions.count()
        context['graded_submissions'] = assignment.submissions.filter(score__isnull=False).count()
        return context


class AssignmentSubmitView(LoginRequiredMixin, View):
    """POST-only hand-in; re-submitting replaces the previous attempt."""

    def post(self, request, assignment_id):
        assignment = get_object_or_404(Assignment, id=assignment_id)
        course = assignment.module.course
        if not can_access_course(request.user, course):
            messages.info(request, 'Please enrol in this course first.')
            return redirect('course-detail', slug=course.slug)
        if not request.user.is_student:
            messages.info(request, 'Staff accounts do not submit work.')
            return redirect('assignment-detail', assignment_id=assignment.id)

        submission = AssignmentSubmission.objects.filter(
            assignment=assignment, student=request.user
        ).first()
        created_now = submission is None
        form = AssignmentSubmitForm(
            request.POST, request.FILES, instance=submission
        )
        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = request.user
            submission.save()
            action = 'Submitted' if created_now else 'Updated'
            messages.success(
                request,
                f'{action} “{assignment.title}” — waiting for your teacher to grade it.'
            )
        else:
            messages.error(request, 'Submission not saved: ' + ' '.join(
                error for errors in form.errors.values() for error in errors
            ))
        return redirect('assignment-detail', assignment_id=assignment.id)


# ----------------------------------------------------------------------
# Phase 4 - lesson completion, progress and reporting
# ----------------------------------------------------------------------
class LessonCompleteView(LoginRequiredMixin, View):
    """POST-only toggle that marks a lesson complete and resyncs progress."""

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.module.course

        if not can_access_course(request.user, course):
            messages.info(request, 'Please enrol in this course before tracking progress.')
            return redirect('course-detail', slug=course.slug)

        quiz = getattr(lesson, 'quiz', None)
        if lesson.has_quiz and quiz and quiz.questions.exists():
            messages.info(
                request, 'Pass the checkpoint quiz to complete this lesson.'
            )
            return redirect('lesson-detail', lesson_id=lesson.id)

        if lesson.lesson_type == LessonType.ASSIGNMENT and lesson.module.assignments.exists():
            messages.info(
                request,
                'Submit the assignment for this module — it is completed once your '
                'teacher grades it.'
            )
            return redirect('lesson-detail', lesson_id=lesson.id)

        progress, _ = UserProgress.objects.get_or_create(
            user=request.user,
            course=course,
            module=lesson.module,
            lesson=lesson,
        )

        if progress.is_completed:
            progress.is_completed = False
            progress.completed_at = None
            progress.save(update_fields=['is_completed', 'completed_at'])
            messages.info(request, f'“{lesson.title}” marked as not completed.')
        else:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save(update_fields=['is_completed', 'completed_at'])
            messages.success(request, f'“{lesson.title}” completed. Nice work!')

        sync_enrollment_progress(request.user, course)
        return redirect('lesson-detail', lesson_id=lesson.id)


# ----------------------------------------------------------------------
# Live sessions (Zoom / Google Meet / Teams)
# ----------------------------------------------------------------------
class LiveSessionMixin(TeacherRequiredMixin):
    """Teacher/admin-only live session management with course ownership checks."""

    def owned_courses(self):
        if self.request.user.is_admin:
            return Course.objects.all()
        return Course.objects.filter(owner=self.request.user) | Course.objects.filter(
            owner__isnull=True
        )

    def get_initial(self):
        initial = super().get_initial()
        course_id = self.request.GET.get('course')
        if course_id:
            initial['course'] = course_id
        return initial


class LiveSessionEditorMixin(LiveSessionMixin):
    """Only the ModelForm views need the request (to scope the course queryset)."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class LiveSessionListView(LiveSessionMixin, TemplateView):
    template_name = 'courses/manage/live_session_list.html'

    def get_queryset(self):
        qs = LiveSession.objects.filter(course__in=self.owned_courses()).select_related(
            'course'
        )
        course_id = self.request.GET.get('course')
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sessions'] = self.get_queryset()
        context['courses'] = self.owned_courses().order_by('title')
        context['active_course'] = self.request.GET.get('course', '')
        return context


class LiveSessionCreateView(LiveSessionEditorMixin, CreateView):
    model = LiveSession
    form_class = LiveSessionForm
    template_name = 'courses/manage/live_session_form.html'
    success_url = reverse_lazy('live-session-list')

    def form_valid(self, form):
        if not form.instance.course_id:
            form.instance.course = self.owned_courses().first()
        messages.success(self.request, f"Live session “{form.instance.title}” scheduled.")
        return super().form_valid(form)


class LiveSessionUpdateView(LiveSessionEditorMixin, UpdateView):
    model = LiveSession
    form_class = LiveSessionForm
    template_name = 'courses/manage/live_session_form.html'
    success_url = reverse_lazy('live-session-list')
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        return LiveSession.objects.filter(course__in=self.owned_courses())

    def form_valid(self, form):
        messages.success(self.request, "Live session updated.")
        return super().form_valid(form)


class LiveSessionDeleteView(LiveSessionMixin, DeleteView):
    model = LiveSession
    template_name = 'courses/manage/live_session_confirm_delete.html'
    success_url = reverse_lazy('live-session-list')
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        return LiveSession.objects.filter(course__in=self.owned_courses())

    def form_valid(self, form):
        messages.success(self.request, "Live session removed.")
        return super().form_valid(form)
