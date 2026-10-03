from django.views.generic import (
    ListView, DetailView, View, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy, reverse

from apps.common.permissions import RoleRequiredMixin, TeacherRequiredMixin, AdminRequiredMixin
from apps.billing.models import active_payment_for, Payment
from .models import (
    Subject, Course, Module, Lesson, LessonType, Quiz, Question, Choice,
    UserProgress, Enrollment, Assignment, AssignmentSubmission, LiveSession,
    QuizAttempt,
)
from .forms import (
    SubjectForm, CourseForm, CourseReviewForm, ModuleForm, LessonForm,
    QuizForm, QuestionFormSet, AssignmentForm, AssignmentSubmitForm,
    SubmissionGradeForm, LiveSessionForm,
)


# ----------------------------------------------------------------------
# Helpers & Access Control
# ----------------------------------------------------------------------
from apps.courses.services.access import (
    can_view_course, can_manage_course, can_submit_for_review,
    can_review_course, can_enroll_course, can_access_course,
    can_start_course, can_take_course_exam, enroll_student_in_course,
)
from apps.courses.selectors import (
    get_published_courses, get_instructor_courses, get_pending_review_courses,
)


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
        category_slug = self.request.GET.get('category')
        level = self.request.GET.get('level')
        access_type = self.request.GET.get('access')
        query = self.request.GET.get('q')

        return get_published_courses(
            subject_slug=category_slug,
            level=level,
            access_type=access_type,
            search_query=query,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        Subject.ensure_default_subjects()
        context['categories'] = Subject.objects.filter(is_active=True).order_by('order')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_level'] = self.request.GET.get('level', '')
        context['selected_access'] = self.request.GET.get('access', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_object(self, queryset=None):
        course = super().get_object(queryset=queryset)
        if not can_view_course(self.request.user, course):
            raise Http404("Course not found or is not currently publicly visible.")
        return course

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        context['modules'] = course.modules.all().prefetch_related('lessons')
        context['total_lessons'] = Lesson.objects.filter(module__course=course).count()

        user = self.request.user
        context['can_manage'] = can_manage_course(user, course)
        can_submit, submit_reason = can_submit_for_review(user, course)
        context['can_submit_for_review'] = can_submit
        context['submit_reason'] = submit_reason
        context['can_review'] = can_review_course(user, course)

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
            context['has_access'] = can_access_course(user, course)
            can_enroll, enroll_reason = can_enroll_course(user, course)
            context['can_enroll'] = can_enroll
            context['enroll_reason'] = enroll_reason
            can_exam, exam_reason = can_take_course_exam(user, course)
            context['can_take_exam'] = can_exam
            context['exam_reason'] = exam_reason

            context['is_purchased'] = False
            context['pending_payment'] = None
            if not course.is_free:
                payment = active_payment_for(user, course)
                context['is_purchased'] = bool(payment and payment.is_current)
                from apps.billing.models import active_subscription_for
                sub = active_subscription_for(user)
                if sub and sub.is_current:
                    if getattr(course, 'is_premium', False):
                        if sub.plan.has_premium_courses:
                            context['is_purchased'] = True
                    else:
                        if sub.plan.has_all_standard_courses:
                            context['is_purchased'] = True
                context['pending_payment'] = Payment.objects.filter(
                    student=user, course=course, status=Payment.Status.PENDING
                ).first()
            context['live_sessions'] = (
                upcoming_live_sessions(course)
                if (user.is_teacher or user.is_admin or context['has_access'])
                else []
            )
        else:
            context['is_enrolled'] = False
            context['has_access'] = False
            can_enroll, enroll_reason = can_enroll_course(user, course)
            context['can_enroll'] = can_enroll
            context['enroll_reason'] = enroll_reason
            context['progress_pct'] = 0
            context['can_take_exam'] = False
            context['exam_reason'] = "Sign in to take the examination."
            context['live_sessions'] = []

        first_module = course.modules.first()
        context['first_lesson'] = first_module.lessons.first() if first_module else None
        return context


class ModuleDetailView(LoginRequiredMixin, DetailView):
    model = Module
    template_name = 'courses/module_detail.html'
    context_object_name = 'module'
    pk_url_kwarg = 'module_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object.course
        context['course'] = course
        context['assignments'] = self.object.assignments.all().order_by('due_date')
        user = self.request.user
        context['can_manage'] = can_manage_course(user, course)
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
        enrollment = Enrollment.objects.filter(student=request.user, course=lesson.module.course).first()
        if enrollment and not enrollment.started_at:
            enrollment.started_at = timezone.now()
            enrollment.save(update_fields=['started_at'])
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
        context['can_manage'] = can_manage_course(self.request.user, course)
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
    """POST-only course enrollment using CourseAccessService."""

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)

        is_eligible, reason = can_enroll_course(request.user, course)
        if not is_eligible:
            if "already actively enrolled" in reason.lower():
                messages.info(request, reason)
                return redirect('course-detail', slug=slug)

            if any(k in reason.lower() for k in ("checkout", "payment", "membership", "subscribe", "paid")):
                messages.info(request, reason)
                return redirect('checkout', slug=slug)

            messages.error(request, reason)
            return redirect('course-detail', slug=slug)

        # Classify enrollment source
        source = Enrollment.Source.SELF
        if course.is_free:
            source = Enrollment.Source.FREE
        elif course.access_type == Course.AccessType.PARTNER_ONLY:
            source = Enrollment.Source.PARTNER
        elif active_payment_for(request.user, course):
            source = Enrollment.Source.PAID
        elif getattr(request.user, 'is_admin', False):
            source = Enrollment.Source.ADMIN
        elif getattr(request.user, 'is_teacher', False):
            source = Enrollment.Source.INSTRUCTOR

        enroll_student_in_course(
            user=request.user,
            course=course,
            source=source,
            partner_institution=course.partner_institution,
        )
        messages.success(request, f"Successfully enrolled in {course.title}. Happy learning!")
        return redirect('course-detail', slug=slug)


class MyCoursesView(LoginRequiredMixin, ListView):
    template_name = 'courses/my_courses.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        return Enrollment.objects.filter(student=self.request.user).select_related('course__subject')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        for enrollment in context['enrollments']:
            enrollment.live_progress = course_progress_pct(user, enrollment.course)

        # Faculty / Teacher workspace data
        if user.is_teacher and not user.is_admin:
            context['is_teacher_view'] = True
            # ONLY courses created and owned by this teacher.
            # Official platform curricula (Diploma in Cyber Security, Full-Stack Web, AI/ML, etc.)
            # are managed centrally by administrators and MUST NOT be shown under personal teaching courses.
            teaching_qs = Course.objects.filter(
                owner=user,
                is_official=False,
                is_published=True,
            ).select_related('subject')

            teaching_list = []
            total_students = 0
            for c in teaching_qs:
                enrolled_cnt = c.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
                pending_cnt = AssignmentSubmission.objects.filter(
                    assignment__module__course=c, score__isnull=True
                ).count()
                sessions = c.live_sessions.all()[:2]
                upcoming_cnt = c.live_sessions.filter(starts_at__gte=timezone.now()).count()
                total_students += enrolled_cnt
                teaching_list.append({
                    'course': c,
                    'enrolled_count': enrolled_cnt,
                    'pending_submissions_count': pending_cnt,
                    'live_sessions': sessions,
                    'upcoming_sessions_count': upcoming_cnt,
                })

            context['teaching_courses'] = teaching_list
            context['total_teaching_students'] = total_students
            context['total_pending_grading'] = AssignmentSubmission.objects.filter(
                assignment__module__course__in=teaching_qs,
                score__isnull=True,
            ).count()
            context['total_live_sessions'] = LiveSession.objects.filter(
                course__in=teaching_qs,
                starts_at__gte=timezone.now(),
            ).count()
            context['student_enrollments'] = context['enrollments']
        elif user.is_admin:
            # Platform administrators viewing My Courses
            context['is_admin_view'] = True
            context['is_teacher_view'] = True
            admin_qs = Course.objects.filter(is_official=True, is_published=True).select_related('subject')
            teaching_list = []
            total_students = 0
            for c in admin_qs:
                enrolled_cnt = c.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
                pending_cnt = AssignmentSubmission.objects.filter(
                    assignment__module__course=c, score__isnull=True
                ).count()
                sessions = c.live_sessions.all()[:2]
                upcoming_cnt = c.live_sessions.filter(starts_at__gte=timezone.now()).count()
                total_students += enrolled_cnt
                teaching_list.append({
                    'course': c,
                    'enrolled_count': enrolled_cnt,
                    'pending_submissions_count': pending_cnt,
                    'live_sessions': sessions,
                    'upcoming_sessions_count': upcoming_cnt,
                })

            context['teaching_courses'] = teaching_list
            context['official_programs'] = teaching_list
            context['total_teaching_students'] = total_students
            context['total_pending_grading'] = AssignmentSubmission.objects.filter(score__isnull=True).count()
            context['total_live_sessions'] = LiveSession.objects.filter(starts_at__gte=timezone.now()).count()
            context['student_enrollments'] = context['enrollments']
        else:
            context['is_teacher_view'] = False

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

        attempt_number = quiz.attempts.filter(student=request.user).count() + 1
        QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            attempt_number=attempt_number,
            score_percentage=score_pct,
            passed=passed,
            points_earned=points_earned if passed else 0,
            answers_data={k: v for k, v in request.POST.items() if k.startswith('question_')},
        )

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


class AssessmentDetailView(LoginRequiredMixin, View):
    """
    Renders an Assessment / Exam page for independent, course-level, or proctored assessments.
    """
    template_name = 'courses/assessment_detail.html'

    def get(self, request, slug, assessment_id):
        course = get_object_or_404(Course, slug=slug)
        assessment = get_object_or_404(Quiz, id=assessment_id)
        if not can_access_course(request.user, course):
            messages.info(request, "Please enrol in this course first.")
            return redirect('course-detail', slug=slug)

        from apps.courses.services.assessment import check_assessment_attempt_eligibility
        can_attempt, reason = check_assessment_attempt_eligibility(request.user, assessment)
        attempts = assessment.attempts.filter(student=request.user)
        best_attempt = attempts.order_by('-score_percentage').first()
        questions = list(assessment.questions.all().prefetch_related('choices'))
        if assessment.randomize_questions:
            import random
            random.shuffle(questions)

        return render(request, self.template_name, {
            'course': course,
            'assessment': assessment,
            'questions': questions,
            'can_attempt': can_attempt,
            'eligibility_reason': reason,
            'attempts': attempts,
            'best_attempt': best_attempt,
            'attempts_left': max(assessment.max_attempts - attempts.count(), 0) if assessment.max_attempts > 0 else 'Unlimited',
        })


class AssessmentSubmitView(LoginRequiredMixin, View):
    """
    Evaluates submissions for independent or course-level assessments / exams.
    """
    def post(self, request, slug, assessment_id):
        course = get_object_or_404(Course, slug=slug)
        assessment = get_object_or_404(Quiz, id=assessment_id)

        from apps.courses.services.assessment import grade_assessment_attempt, check_assessment_attempt_eligibility
        can_attempt, reason = check_assessment_attempt_eligibility(request.user, assessment)
        if not can_attempt:
            messages.error(request, reason)
            return redirect('assessment-detail', slug=slug, assessment_id=assessment.id)

        time_taken = request.POST.get('time_taken_seconds', 0)
        attempt, _ = grade_assessment_attempt(assessment, request.user, request.POST, time_taken_seconds=time_taken)

        if attempt.passed:
            messages.success(
                request,
                f"Congratulations! You passed {assessment.title} with a score of {attempt.score_percentage}%!"
            )
        else:
            messages.error(
                request,
                f"You scored {attempt.score_percentage}%. The passing threshold is {assessment.passing_percentage}%."
            )

        return redirect('assessment-detail', slug=slug, assessment_id=assessment.id)


# ----------------------------------------------------------------------
# Teacher / Administrator authoring (Phase 2)
# ----------------------------------------------------------------------
class ManageHomeView(TeacherRequiredMixin, TemplateView):
    """Authoring cockpit: subjects, courses, modules and lessons at a glance."""
    template_name = 'courses/manage/manage_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_admin:
            context['subjects'] = Subject.objects.all().prefetch_related('courses')
            context['courses'] = Course.objects.all().prefetch_related('modules__lessons', 'subject')
            context['ungraded_count'] = AssignmentSubmission.objects.filter(score__isnull=True).count()
        else:
            context['subjects'] = []
            context['courses'] = Course.objects.filter(
                owner=user,
                is_official=False,
            ).prefetch_related('modules__lessons', 'subject')
            context['ungraded_count'] = AssignmentSubmission.objects.filter(
                assignment__module__course__owner=user,
                score__isnull=True,
            ).count()
        return context


class SubjectCreateView(TeacherRequiredMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'courses/manage/subject_form.html'
    success_url = reverse_lazy('manage-home')

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url:
            separator = '&' if '?' in next_url else '?'
            return f"{next_url}{separator}subject={self.object.id}"
        return reverse('manage-home')

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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        course = form.save(commit=False)
        course.owner = self.request.user

        if self.request.user.is_admin:
            course.is_official = form.cleaned_data.get('is_official', True)
            if form.cleaned_data.get('is_published'):
                course.status = Course.Status.PUBLISHED
                course.is_published = True
            else:
                course.status = Course.Status.DRAFT
                course.is_published = False
        else:
            course.is_official = False
            course.owner_type = Course.OwnerType.INSTRUCTOR
            course.status = Course.Status.DRAFT
            course.is_published = False

        course.save()
        messages.success(self.request, f"Course “{course.title}” created in Draft status.")
        return redirect('course-edit', slug=course.slug)


class CourseUpdateView(TeacherRequiredMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('manage-home')

    def get_queryset(self):
        # Admins edit everything; instructors only their own non-official courses.
        if self.request.user.is_admin:
            return Course.objects.all()
        return Course.objects.filter(
            owner=self.request.user,
            is_official=False,
        )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        course = self.get_object()
        if not request.user.is_admin and course.status == Course.Status.PENDING_REVIEW:
            messages.warning(
                request,
                f"Course “{course.title}” is currently under review by administrators and cannot be modified."
            )
            return redirect('manage-home')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        context['modules'] = course.modules.all().prefetch_related('lessons')
        context['total_lessons'] = Lesson.objects.filter(module__course=course).count()
        can_submit, submit_reason = can_submit_for_review(self.request.user, course)
        context['can_submit_for_review'] = can_submit
        context['submit_reason'] = submit_reason
        return context

    def form_valid(self, form):
        course = form.save(commit=False)
        if not course.owner_id:
            course.owner = self.request.user

        if self.request.user.is_admin:
            if course.owner is None or course.owner.is_admin:
                course.is_official = True
        else:
            course.is_official = False
            # Instructors cannot publish directly: if edited, course remains draft/rejected
            if course.status not in [Course.Status.DRAFT, Course.Status.REJECTED]:
                course.status = Course.Status.DRAFT
            course.is_published = False

        course.save()
        messages.success(self.request, f"Course “{course.title}” updated.")
        return redirect('course-edit', slug=course.slug)


class CourseSubmitReviewView(TeacherRequiredMixin, View):
    """
    POST-only: Instructor or Partner submits a Draft or Rejected course for editorial review.
    Status transitions: DRAFT / REJECTED -> PENDING_REVIEW.
    """
    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        can_submit, reason = can_submit_for_review(request.user, course)
        if not can_submit:
            messages.error(request, reason)
            return redirect('course-edit', slug=course.slug)

        course.status = Course.Status.PENDING_REVIEW
        course.is_published = False
        course.save(update_fields=['status', 'is_published'])
        messages.success(
            request,
            f"Course “{course.title}” has been submitted for administrative review! An administrator will review your curriculum."
        )
        return redirect('manage-home')


class CourseReviewListView(AdminRequiredMixin, ListView):
    """
    Administrator interface: Lists courses awaiting editorial review.
    """
    template_name = 'courses/manage/review_list.html'
    context_object_name = 'pending_courses'

    def get_queryset(self):
        return get_pending_review_courses()


class CourseReviewActionView(AdminRequiredMixin, View):
    """
    Administrator review action: Inspect curriculum and Approve, Publish, Reject, or Request Changes.
    """
    template_name = 'courses/manage/review_detail.html'

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        form = CourseReviewForm(initial={'admin_review_notes': course.admin_review_notes})
        modules = course.modules.all().prefetch_related('lessons')
        return render(request, self.template_name, {
            'course': course,
            'modules': modules,
            'total_lessons': Lesson.objects.filter(module__course=course).count(),
            'form': form,
        })

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        form = CourseReviewForm(request.POST)
        if not form.is_valid():
            modules = course.modules.all().prefetch_related('lessons')
            return render(request, self.template_name, {
                'course': course,
                'modules': modules,
                'total_lessons': Lesson.objects.filter(module__course=course).count(),
                'form': form,
            })

        action = form.cleaned_data['action']
        notes = form.cleaned_data.get('admin_review_notes', '').strip()

        course.admin_review_notes = notes
        course.reviewed_by = request.user
        course.reviewed_at = timezone.now()

        if action == CourseReviewForm.Action.APPROVE:
            course.status = Course.Status.APPROVED
            course.is_published = False
            messages.success(request, f"Course “{course.title}” approved.")
        elif action == CourseReviewForm.Action.PUBLISH:
            course.status = Course.Status.PUBLISHED
            course.is_published = True
            messages.success(request, f"Course “{course.title}” approved and published!")
        elif action in [CourseReviewForm.Action.REJECT, CourseReviewForm.Action.REQUEST_CHANGES]:
            course.status = Course.Status.REJECTED
            course.is_published = False
            messages.warning(request, f"Course “{course.title}” returned with review notes.")
        elif action == CourseReviewForm.Action.ARCHIVE:
            course.status = Course.Status.ARCHIVED
            course.is_published = False
            messages.info(request, f"Course “{course.title}” archived.")

        course.save()
        return redirect('course-review-list')



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

    def get_queryset(self):
        if self.request.user.is_admin:
            return Module.objects.all()
        return Module.objects.filter(
            course__owner=self.request.user,
            course__is_official=False,
        )

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

    def get_queryset(self):
        if self.request.user.is_admin:
            return Lesson.objects.all()
        return Lesson.objects.filter(
            module__course__owner=self.request.user,
            module__course__is_official=False,
        )

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

    def get_queryset(self):
        if self.request.user.is_admin:
            return Lesson.objects.all()
        return Lesson.objects.filter(
            module__course__owner=self.request.user,
            module__course__is_official=False,
        )

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
        lesson = get_object_or_404(Lesson, id=self.kwargs['lesson_id'])
        if not self.request.user.is_admin and (
            lesson.module.course.owner != self.request.user or lesson.module.course.is_official
        ):
            raise Http404("You do not have permission to edit this quiz.")
        return lesson

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

    def get_queryset(self):
        if self.request.user.is_admin:
            return Assignment.objects.all()
        return Assignment.objects.filter(
            module__course__owner=self.request.user,
            module__course__is_official=False,
        )

    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated.')
        return super().form_valid(form)


class AssignmentDeleteView(TeacherRequiredMixin, DeleteView):
    model = Assignment
    template_name = 'courses/manage/assignment_confirm_delete.html'
    pk_url_kwarg = 'assignment_id'
    success_url = reverse_lazy('manage-home')

    def get_queryset(self):
        if self.request.user.is_admin:
            return Assignment.objects.all()
        return Assignment.objects.filter(
            module__course__owner=self.request.user,
            module__course__is_official=False,
        )

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
        if not self.request.user.is_admin:
            qs = qs.filter(
                assignment__module__course__owner=self.request.user,
                assignment__module__course__is_official=False,
            )
        return qs.filter(**self.STATUS_FILTERS[self.get_status()])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status'] = self.get_status()
        base_qs = AssignmentSubmission.objects.all()
        if not self.request.user.is_admin:
            base_qs = base_qs.filter(
                assignment__module__course__owner=self.request.user,
                assignment__module__course__is_official=False,
            )
            context['assignments'] = Assignment.objects.filter(
                module__course__owner=self.request.user,
                module__course__is_official=False,
            ).select_related('module__course').order_by(
                'module__course__title', 'module__order'
            )
        else:
            context['assignments'] = Assignment.objects.select_related('module__course').order_by(
                'module__course__title', 'module__order'
            )
        context['ungraded_count'] = base_qs.filter(score__isnull=True).count()
        context['graded_count'] = base_qs.filter(score__isnull=False).count()
        return context


class SubmissionGradeView(TeacherRequiredMixin, UpdateView):
    model = AssignmentSubmission
    form_class = SubmissionGradeForm
    template_name = 'courses/manage/grade_submission.html'
    pk_url_kwarg = 'submission_id'

    def get_queryset(self):
        qs = AssignmentSubmission.objects.select_related(
            'assignment__module__course', 'student'
        )
        if not self.request.user.is_admin:
            qs = qs.filter(
                assignment__module__course__owner=self.request.user,
                assignment__module__course__is_official=False,
            )
        return qs

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
        return Course.objects.filter(
            owner=self.request.user,
            is_official=False,
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


# -----------------------------------------------------------------------------
# REST API Endpoints (Mobile / Desktop / SPA Clients)
# -----------------------------------------------------------------------------
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import (
    SubjectSerializer, CourseListSerializer, CourseDetailSerializer
)


class CategoryListAPIView(APIView):
    """
    GET /courses/api/categories/
    Returns list of all active categories (Python, CS, ICT, GED, AI, etc.)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        Subject.ensure_default_subjects()
        subjects = Subject.objects.filter(is_active=True).order_by('order')
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CourseListAPIView(APIView):
    """
    GET /courses/api/courses/
    Filters by ?category=<slug>&level=<level>&is_premium=<bool>&q=<query>
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Course.objects.filter(is_published=True).select_related('subject', 'owner')
        category = request.GET.get('category')
        if category:
            qs = qs.filter(subject__slug=category)
        level = request.GET.get('level')
        if level:
            qs = qs.filter(level=level)
        is_premium = request.GET.get('is_premium')
        if is_premium is not None and is_premium != '':
            qs = qs.filter(is_premium=is_premium.lower() in ['true', '1'])
        q = request.GET.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(subject__title__icontains=q)
            )
        serializer = CourseListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CourseDetailAPIView(APIView):
    """
    GET /courses/api/courses/<slug>/
    Returns full course structure and syllabus modules.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        course = get_object_or_404(
            Course.objects.prefetch_related('modules__lessons'),
            slug=slug,
            is_published=True
        )
        serializer = CourseDetailSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

