from django.db.models import Q, Max
from django.views.generic import (
    ListView, DetailView, View, CreateView, UpdateView, DeleteView, TemplateView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404, JsonResponse, HttpResponseRedirect
from django.contrib import messages
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse_lazy, reverse

from apps.common.permissions import RoleRequiredMixin, TeacherRequiredMixin, AdminRequiredMixin
from apps.billing.models import active_payment_for, Payment
from .models import (
    Subject, Course, Module, Lesson, LessonType, Quiz, Question, Choice,
    UserProgress, Enrollment, Assignment, AssignmentSubmission, LiveSession,
    LiveSessionAttendance, QuizAttempt,
)
from apps.courses.services.jitsi import get_jitsi_connection_config
from apps.courses.live import (
    get_live_provider,
    get_available_providers,
    get_default_provider,
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
    can_publish_course, can_review_course, can_enroll_course,
    can_access_course, can_start_course, can_take_course_exam,
    enroll_student_in_course,
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


def recorded_live_sessions(course):
    """Published sessions for `course` that have a recording/replay URL attached."""
    return list(
        course.live_sessions.filter(
            is_published=True
        ).exclude(recording_url='').order_by('-starts_at')
    )



def sync_enrollment_progress(user, course):
    """Recompute and persist the stored percentage on the student's enrollment and sync completion."""
    from apps.courses.services.completion import sync_course_completion
    return sync_course_completion(user, course)


# ----------------------------------------------------------------------
# Catalogue (public)
# ----------------------------------------------------------------------
class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12

    def get_queryset(self):
        category_slug = self.request.GET.get('category')
        level = self.request.GET.get('level')
        access_type = self.request.GET.get('access')
        price_type = self.request.GET.get('price_type')
        sort = self.request.GET.get('sort', '')
        query = self.request.GET.get('q')

        return get_published_courses(
            subject_slug=category_slug,
            level=level,
            access_type=access_type,
            search_query=query,
            price_type=price_type,
            sort=sort,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        Subject.ensure_default_subjects()
        context['categories'] = Subject.objects.filter(is_active=True).order_by('order')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_level'] = self.request.GET.get('level', '')
        context['selected_access'] = self.request.GET.get('access', '')
        context['selected_price_type'] = self.request.GET.get('price_type', '')
        context['selected_sort'] = self.request.GET.get('sort', '')
        context['search_query'] = self.request.GET.get('q', '')
        # Compute total matching items for display
        qs = self.get_queryset()
        context['total_matches'] = qs.count() if hasattr(qs, 'count') else len(qs)
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
            has_live_access = bool(user.is_teacher or user.is_admin or context['has_access'])
            context['live_sessions'] = (
                upcoming_live_sessions(course) if has_live_access else []
            )
            context['recorded_live_sessions'] = (
                recorded_live_sessions(course) if has_live_access else []
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
            context['recorded_live_sessions'] = []

        # Edube-style module progress roadmap & resume lesson calculation
        modules_list = list(course.modules.prefetch_related('lessons', 'assignments').order_by('order', 'id'))
        first_lesson = None
        resume_lesson = None
        completed_lesson_ids = set()
        best_quiz_scores = {}

        if user.is_authenticated:
            completed_lesson_ids = set(
                UserProgress.objects.filter(
                    user=user, course=course, is_completed=True
                ).values_list('lesson_id', flat=True)
            )
            for attempt in QuizAttempt.objects.filter(student=user, quiz__course=course).values('quiz_id').annotate(max_score=Max('score_percentage')):
                best_quiz_scores[attempt['quiz_id']] = attempt['max_score']

        module_progress_data = []
        for m in modules_list:
            m_lessons = list(m.lessons.order_by('order', 'id'))
            if not first_lesson and m_lessons:
                first_lesson = m_lessons[0]

            m_completed = sum(1 for l in m_lessons if l.id in completed_lesson_ids)
            if not resume_lesson and user.is_authenticated:
                for l in m_lessons:
                    if l.id not in completed_lesson_ids:
                        resume_lesson = l
                        break

            m_quiz = m.quizzes.filter(status=Quiz.Status.PUBLISHED).first() or m.quizzes.first()
            if not m_quiz:
                for l in m_lessons:
                    if getattr(l, 'quiz', None):
                        m_quiz = l.quiz
                        break

            quiz_score = best_quiz_scores.get(m_quiz.id) if m_quiz else None
            has_labs = any(getattr(l, 'has_lab', False) or l.labs.exists() for l in m_lessons)

            module_progress_data.append({
                'module': m,
                'total_lessons': len(m_lessons),
                'completed_lessons': m_completed,
                'is_completed': len(m_lessons) > 0 and m_completed == len(m_lessons),
                'first_lesson': m_lessons[0] if m_lessons else None,
                'quiz': m_quiz,
                'quiz_score': quiz_score,
                'has_labs': has_labs,
            })

        total_lessons_count = context.get('total_lessons', 0)
        completed_lessons_count = len(completed_lesson_ids)
        all_lessons_completed = (total_lessons_count > 0 and completed_lessons_count >= total_lessons_count)

        if not resume_lesson and not all_lessons_completed:
            resume_lesson = first_lesson

        # Summary test / final certifying exam for roadmap
        final_exam = course.quizzes.filter(
            quiz_type__in=[Quiz.AssessmentType.FINAL_EXAM, Quiz.AssessmentType.COURSE_EXAM, Quiz.AssessmentType.EXAM],
            status=Quiz.Status.PUBLISHED
        ).first()
        final_exam_score = best_quiz_scores.get(final_exam.id) if final_exam else None

        final_exam_passed = False
        if final_exam and user.is_authenticated:
            if final_exam_score is not None and final_exam_score >= final_exam.passing_percentage:
                final_exam_passed = True
            elif final_exam.attempts.filter(student=user, passed=True).exists():
                final_exam_passed = True

        earned_certificate = None
        if user.is_authenticated:
            from apps.certificates.models import Certificate
            earned_certificate = Certificate.objects.filter(
                student=user, course=course, is_revoked=False
            ).first()
            if not earned_certificate and final_exam:
                earned_certificate = Certificate.objects.filter(
                    student=user, exam=final_exam, is_revoked=False
                ).first()

        context['first_lesson'] = first_lesson
        context['resume_lesson'] = resume_lesson
        context['module_progress_data'] = module_progress_data
        context['final_exam'] = final_exam
        context['final_exam_score'] = final_exam_score
        context['final_exam_passed'] = final_exam_passed
        context['all_lessons_completed'] = all_lessons_completed
        context['earned_certificate'] = earned_certificate
        context['course_assessments'] = course.quizzes.filter(
            status=Quiz.Status.PUBLISHED
        ).exclude(quiz_type=Quiz.AssessmentType.QUIZ)
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

        # Curriculum navigation and progress tracking
        modules = list(course.modules.prefetch_related('lessons').order_by('order', 'id'))
        context['modules'] = modules
        
        all_lessons = []
        for m in modules:
            all_lessons.extend(list(m.lessons.order_by('order', 'id')))
        
        current_idx = -1
        for idx, l in enumerate(all_lessons):
            if l.id == lesson.id:
                current_idx = idx
                break
        
        context['prev_lesson'] = all_lessons[current_idx - 1] if current_idx > 0 else None
        context['next_lesson'] = all_lessons[current_idx + 1] if (current_idx >= 0 and current_idx < len(all_lessons) - 1) else None
        context['total_lessons_count'] = len(all_lessons)
        context['current_lesson_index'] = current_idx + 1 if current_idx >= 0 else 1
        
        if self.request.user.is_authenticated:
            completed_lesson_ids = set(
                UserProgress.objects.filter(
                    user=self.request.user,
                    course=course,
                    is_completed=True
                ).values_list('lesson_id', flat=True)
            )
        else:
            completed_lesson_ids = set()
        context['completed_lesson_ids'] = completed_lesson_ids
        context['course_progress_percentage'] = (
            round((len(completed_lesson_ids) / len(all_lessons) * 100), 1) if all_lessons else 0
        )
        slide_deck = lesson.slide_deck
        context['slide_deck'] = slide_deck
        context['total_slides_count'] = len(slide_deck)
        context['has_slide_deck'] = len(slide_deck) > 0

        # Final assessment exam and certificate status for forward navigation
        final_exam = course.quizzes.filter(
            quiz_type__in=[Quiz.AssessmentType.FINAL_EXAM, Quiz.AssessmentType.COURSE_EXAM, Quiz.AssessmentType.EXAM],
            status=Quiz.Status.PUBLISHED
        ).first()
        final_exam_passed = False
        earned_certificate = None
        if self.request.user.is_authenticated:
            if final_exam:
                final_exam_passed = final_exam.attempts.filter(student=self.request.user, passed=True).exists()
            from apps.certificates.models import Certificate
            earned_certificate = Certificate.objects.filter(
                student=self.request.user, course=course, is_revoked=False
            ).first()
            if not earned_certificate and final_exam:
                earned_certificate = Certificate.objects.filter(
                    student=self.request.user, exam=final_exam, is_revoked=False
                ).first()

        context['final_exam'] = final_exam
        context['final_exam_passed'] = final_exam_passed
        context['earned_certificate'] = earned_certificate
        context['is_last_lesson'] = (context['next_lesson'] is None)
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

        from apps.certificates.models import Certificate
        earned_certificate = Certificate.objects.filter(
            student=request.user, course=course, is_revoked=False
        ).first()
        if not earned_certificate:
            earned_certificate = Certificate.objects.filter(
                student=request.user, exam=assessment, is_revoked=False
            ).first()

        return render(request, self.template_name, {
            'course': course,
            'assessment': assessment,
            'questions': questions,
            'can_attempt': can_attempt,
            'eligibility_reason': reason,
            'attempts': attempts,
            'best_attempt': best_attempt,
            'attempts_left': max(assessment.max_attempts - attempts.count(), 0) if assessment.max_attempts > 0 else 'Unlimited',
            'earned_certificate': earned_certificate,
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
            from apps.courses.services.completion import sync_course_completion
            sync_course_completion(request.user, course)

            from apps.certificates.models import Certificate
            cert = Certificate.objects.filter(student=request.user, course=course, is_revoked=False).first()
            if not cert:
                cert = Certificate.objects.filter(student=request.user, exam=assessment, is_revoked=False).first()

            if cert:
                messages.success(
                    request,
                    f"🎉 ဂုဏ်ယူပါသည်! {assessment.title} ကို အောင်မြင်စွာ ဖြေဆိုပြီးဖြစ်၍ သင်၏ တရားဝင် အောင်လက်မှတ် (Certificate Code: {cert.certificate_code}) ကို ထုတ်ပေးပြီး ဖြစ်ပါသည်။"
                )
            else:
                messages.success(
                    request,
                    f"🎉 Congratulations! You passed {assessment.title} with a score of {attempt.score_percentage}%!"
                )
        else:
            messages.error(
                request,
                f"You scored {attempt.score_percentage}%. The passing threshold is {assessment.passing_percentage}%. (ပြန်လည်လေ့လာပြီး ထပ်မံဖြေဆိုနိုင်ပါသည်)"
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
        status_label = "Published" if course.is_published else "Draft"
        messages.success(self.request, f"Course “{course.title}” created successfully in {status_label} status.")
        return redirect('course-edit', slug=course.slug)


class CourseUpdateView(RoleRequiredMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/manage/course_form.html'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('manage-home')
    allowed_roles = ['teacher', 'instructor', 'partner']

    def get_queryset(self):
        # Admins edit everything; instructors only their own non-official courses.
        if self.request.user.is_admin:
            return Course.objects.all()
        if getattr(self.request.user, 'is_partner', False):
            from apps.partner.views import get_user_partner_institutions
            institutions = get_user_partner_institutions(self.request.user)
            return Course.objects.filter(
                Q(owner=self.request.user) | Q(partner_institution__in=institutions),
                is_official=False
            ).distinct()
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
        can_pub, pub_reason = can_publish_course(self.request.user, course)
        context['can_publish'] = can_pub
        context['publish_reason'] = pub_reason
        context['course_final_exam'] = course.quizzes.filter(
            quiz_type__in=[
                Quiz.AssessmentType.FINAL_EXAM,
                Quiz.AssessmentType.COURSE_EXAM,
                Quiz.AssessmentType.EXAM,
            ]
        ).first()
        return context

    def form_valid(self, form):
        course = form.save(commit=False)
        if not course.owner_id:
            course.owner = self.request.user

        if self.request.user.is_admin:
            course.is_official = form.cleaned_data.get('is_official', course.is_official)
            if form.cleaned_data.get('is_published'):
                course.status = Course.Status.PUBLISHED
                course.is_published = True
            elif course.status == Course.Status.PUBLISHED and not form.cleaned_data.get('is_published'):
                course.status = Course.Status.DRAFT
                course.is_published = False
        else:
            course.is_official = False
            # Preserve published status on edits: updating course details does NOT demote published courses to draft!
            if course.status == Course.Status.PUBLISHED:
                course.is_published = True
            elif course.status in [Course.Status.DRAFT, Course.Status.REJECTED]:
                course.is_published = False

        course.save()
        messages.success(self.request, f"Course “{course.title}” updated successfully.")
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
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('manage-home')


class CoursePublishToggleView(TeacherRequiredMixin, View):
    """
    POST-only: Allows verified teachers and admins to publish or unpublish a course.
    - If currently PUBLISHED -> Unpublishes to DRAFT.
    - If currently DRAFT / APPROVED / REJECTED -> Validates curriculum completeness and transitions to PUBLISHED.
    """
    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        if not can_manage_course(request.user, course):
            messages.error(request, "You do not have permission to manage this course.")
            return redirect('manage-home')

        if course.status == Course.Status.PUBLISHED:
            course.status = Course.Status.DRAFT
            course.is_published = False
            course.save(update_fields=['status', 'is_published'])
            messages.info(
                request,
                f"Course “{course.title}” has been unpublished and reverted to Draft status. It is no longer visible to students in the catalog."
            )
        else:
            can_pub, reason = can_publish_course(request.user, course)
            if not can_pub:
                messages.error(request, reason)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('course-edit', slug=course.slug)

            course.status = Course.Status.PUBLISHED
            course.is_published = True
            course.save(update_fields=['status', 'is_published'])
            messages.success(
                request,
                f"Course “{course.title}” is now published and live in the Course Catalog! Students can now view, enrol, and learn."
            )

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
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

    def get_success_url(self):
        if self.object and self.object.course:
            return reverse('course-edit', kwargs={'slug': self.object.course.slug})
        return reverse('manage-home')

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

    def get_success_url(self):
        if self.object and self.object.course:
            return reverse('course-edit', kwargs={'slug': self.object.course.slug})
        return reverse('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Module updated.")
        return super().form_valid(form)


class ModuleDeleteView(TeacherRequiredMixin, DeleteView):
    model = Module
    template_name = 'courses/manage/module_confirm_delete.html'
    pk_url_kwarg = 'module_id'
    success_url = reverse_lazy('manage-home')

    def get_queryset(self):
        if self.request.user.is_admin:
            return Module.objects.all()
        return Module.objects.filter(
            course__owner=self.request.user,
            course__is_official=False,
        )

    def get_success_url(self):
        if self.object and self.object.course:
            return reverse('course-edit', kwargs={'slug': self.object.course.slug})
        return reverse('manage-home')

    def form_valid(self, form):
        messages.success(self.request, f"Module “{self.object.title}” deleted.")
        return super().form_valid(form)


class LessonCreateView(TeacherRequiredMixin, CreateView):
    model = Lesson
    form_class = LessonForm
    template_name = 'courses/manage/lesson_form.html'

    def get_initial(self):
        initial = super().get_initial()
        module_pk = self.request.GET.get('module')
        course_pk = self.request.GET.get('course')
        if module_pk:
            initial['module'] = module_pk
            initial['order'] = Lesson.objects.filter(module_id=module_pk).count() + 1
        elif course_pk:
            course = Course.objects.filter(pk=course_pk).first()
            if course:
                mod = course.modules.first()
                if not mod:
                    mod = Module.objects.create(
                        course=course,
                        title=f"{course.title} - Module 1",
                        order=1
                    )
                initial['module'] = mod.pk
                initial['order'] = mod.lessons.count() + 1
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        course_pk = self.request.GET.get('course')
        module_pk = self.request.GET.get('module')
        if course_pk:
            form.fields['module'].queryset = Module.objects.filter(course_id=course_pk)
        elif module_pk:
            mod = Module.objects.filter(pk=module_pk).first()
            if mod:
                form.fields['module'].queryset = Module.objects.filter(course=mod.course)
        elif not self.request.user.is_admin:
            form.fields['module'].queryset = Module.objects.filter(
                course__owner=self.request.user, course__is_official=False
            )
        return form

    def get_success_url(self):
        if self.object and self.object.module and self.object.module.course:
            return reverse('course-edit', kwargs={'slug': self.object.module.course.slug})
        return reverse('module-edit', kwargs={'module_id': self.object.module_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module_pk = self.request.GET.get('module')
        course_pk = self.request.GET.get('course')
        if module_pk:
            mod = Module.objects.filter(pk=module_pk).select_related('course').first()
            if mod:
                context['target_module'] = mod
                context['target_course'] = mod.course
        elif course_pk:
            course = Course.objects.filter(pk=course_pk).first()
            if course:
                context['target_course'] = course
                context['target_module'] = course.modules.first()
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Lesson “{form.cleaned_data['title']}” created successfully.")
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object and self.object.module:
            context['target_module'] = self.object.module
            context['target_course'] = self.object.module.course
        return context

    def get_success_url(self):
        if self.object and self.object.module and self.object.module.course:
            return reverse('course-edit', kwargs={'slug': self.object.module.course.slug})
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

    def get_success_url(self):
        if self.object and self.object.module and self.object.module.course:
            return reverse('course-edit', kwargs={'slug': self.object.module.course.slug})
        return reverse('manage-home')

    def form_valid(self, form):
        messages.success(self.request, "Lesson deleted.")
        return super().form_valid(form)


# ----------------------------------------------------------------------
# Phase 3 - quizzes, assignments, submissions and grading
# ----------------------------------------------------------------------
class QuizBuilderView(TeacherRequiredMixin, View):
    """
    One screen for building a lesson checkpoint quiz or course/standalone exam:
    quiz settings plus a formset of multiple choice questions, each with four answer slots.
    """

    template_name = 'courses/manage/quiz_form.html'

    def get_lesson_and_quiz(self, target_id):
        lesson = Lesson.objects.filter(id=target_id).first()
        if lesson:
            if not self.request.user.is_admin and (
                lesson.module.course.owner != self.request.user or lesson.module.course.is_official
            ):
                raise Http404("You do not have permission to edit this quiz.")
            quiz, _ = Quiz.objects.get_or_create(
                lesson=lesson,
                defaults={
                    'title': f'Checkpoint — {lesson.title}',
                    'course': lesson.module.course,
                    'module': lesson.module,
                }
            )
            return lesson, quiz, lesson.module.course, lesson.module

        quiz = get_object_or_404(Quiz, id=target_id)
        if not self.request.user.is_admin and (
            quiz.owner != self.request.user and quiz.assigned_instructor != self.request.user
        ):
            if quiz.course and quiz.course.owner != self.request.user:
                raise Http404("You do not have permission to edit this quiz.")
        lesson = quiz.lesson
        course = quiz.course or (lesson.module.course if lesson and lesson.module else None)
        module = quiz.module or (lesson.module if lesson else None)
        return lesson, quiz, course, module

    def _render(self, request, lesson, quiz, course, module, quiz_form=None, question_formset=None):
        context = {
            'lesson': lesson,
            'course': course,
            'module': module,
            'quiz': quiz,
            'form': quiz_form or QuizForm(instance=quiz),
            'question_formset': question_formset or QuestionFormSet(instance=quiz),
        }
        return render(request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        lesson, quiz, course, module = self.get_lesson_and_quiz(self.kwargs['lesson_id'])
        return self._render(request, lesson, quiz, course, module)

    def post(self, request, *args, **kwargs):
        lesson, quiz, course, module = self.get_lesson_and_quiz(self.kwargs['lesson_id'])
        quiz_form = QuizForm(request.POST, instance=quiz)
        question_formset = QuestionFormSet(request.POST, instance=quiz)

        if quiz_form.is_valid() and question_formset.is_valid():
            saved_quiz = quiz_form.save()
            question_formset.save()
            if lesson:
                if not lesson.has_quiz:
                    lesson.has_quiz = True
                    lesson.save(update_fields=['has_quiz'])
                messages.success(
                    request,
                    f'Quiz “{saved_quiz.title}” saved with {saved_quiz.questions.count()} question(s).'
                )
                return redirect('lesson-detail', lesson_id=lesson.id)
            else:
                messages.success(
                    request,
                    f'Assessment “{saved_quiz.title}” saved with {saved_quiz.questions.count()} question(s).'
                )
                if saved_quiz.course:
                    return redirect('course-edit', slug=saved_quiz.course.slug)
                return redirect('standalone-exam-detail', exam_id=saved_quiz.id)

        messages.error(request, 'Please fix the highlighted errors before saving the quiz.')
        return self._render(request, lesson, quiz, course, module, quiz_form, question_formset)


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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module_pk = self.request.GET.get('module')
        if module_pk:
            from apps.courses.models import Module
            context['target_module'] = Module.objects.filter(pk=module_pk).select_related('course').first()
        return context

    def get_success_url(self):
        if self.object and self.object.module and self.object.module.course:
            return reverse('course-edit', kwargs={'slug': self.object.module.course.slug})
        return reverse('manage-home')

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
        if getattr(self.request.user, 'is_admin', False) or self.request.user.is_superuser:
            return Assignment.objects.all()
        return Assignment.objects.filter(
            models.Q(module__course__owner=self.request.user) |
            models.Q(module__course__is_official=False)
        ).distinct()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object and self.object.module:
            context['target_module'] = self.object.module
        return context

    def get_success_url(self):
        if self.object and self.object.module and self.object.module.course:
            return reverse('course-edit', kwargs={'slug': self.object.module.course.slug})
        return reverse('manage-home')

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
        from apps.users.models import Notification
        Notification.objects.create(
            user=submission.student,
            title="Assignment Graded",
            message=f"Your assignment “{submission.assignment.title}” has been graded: {submission.score}/{submission.assignment.max_score}.",
            level=Notification.Level.SUCCESS if submission.score and submission.score >= (submission.assignment.max_score * 0.6) else Notification.Level.INFO,
            link=reverse('assignment-detail', kwargs={'assignment_id': submission.assignment.id}),
        )
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

        action = request.POST.get('action')

        # Enforce thorough slide study for presentations/documents
        progress, _ = UserProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'course': course, 'module': lesson.module},
        )

        is_marking_complete = (action == 'complete') or (action != 'incomplete' and not progress.is_completed)

        # Enforce thorough slide study for presentations/documents when marking complete
        slide_deck = lesson.slide_deck
        if slide_deck and len(slide_deck) > 0 and is_marking_complete:
            slides_completed = request.POST.get('slides_completed')
            try:
                slides_viewed_count = int(request.POST.get('slides_viewed_count') or 0)
            except (ValueError, TypeError):
                slides_viewed_count = 0

            # Staff, superusers, and course instructors can bypass when auditing, learners must study all slides
            is_author = (course.instructor == request.user)
            if not (request.user.is_staff or request.user.is_superuser or is_author):
                if slides_completed != '1' or slides_viewed_count < len(slide_deck):
                    messages.warning(
                        request,
                        f'သင်ခန်းစာရှိ Slide အားလုံး ({len(slide_deck)} ခု) ကို တစ်ခုချင်းစီ အပြည့်အစုံ လေ့လာဖတ်ရှုပြီးမှသာ Mark Complete ပြုလုပ်နိုင်ပါမည်။ (ကျေးဇူးပြု၍ ကျန်ရှိနေသော Slide များကို ဆက်လက်လေ့လာပေးပါ)'
                    )
                    return redirect('lesson-detail', lesson_id=lesson.id)

        if not is_marking_complete:
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

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('lesson-detail', lesson_id=lesson.id)


def user_can_manage_live_session(user, target) -> bool:
    """
    Checks if a user is authorized to manage or host a live session:
    - Platform Administrators (universal)
    - Course Owner/Author
    - Institutional Partner manager/instructor managing the course's partner institution
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False):
        return True
    course = target.course if hasattr(target, 'course') else target
    if course and course.owner_id and course.owner_id == user.id:
        return True
    if getattr(user, 'is_partner', False) and course and getattr(course, 'partner_institution_id', None):
        try:
            from apps.partner.models import get_user_partner_institutions
            institutions = get_user_partner_institutions(user)
            if course.partner_institution in institutions:
                return True
        except Exception:
            pass
    return False


# ----------------------------------------------------------------------
# Live sessions (Zoom / Google Meet / Teams)
# ----------------------------------------------------------------------
class LiveSessionMixin(TeacherRequiredMixin):
    """Teacher/admin-only live session management with course ownership checks."""

    def owned_courses(self):
        if self.request.user.is_admin:
            return Course.objects.all()
        user = self.request.user
        qs = Course.objects.filter(owner=user, is_official=False)
        if getattr(user, 'is_partner', False):
            try:
                from apps.partner.models import get_user_partner_institutions
                from django.db.models import Q
                institutions = get_user_partner_institutions(user)
                if institutions:
                    qs = Course.objects.filter(
                        Q(owner=user) | Q(partner_institution__in=institutions)
                    ).distinct()
            except Exception:
                pass
        return qs

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
        status_filter = self.request.GET.get('status')
        now = timezone.now()
        if status_filter == 'upcoming':
            qs = qs.filter(starts_at__gt=now)
        elif status_filter == 'past':
            qs = qs.filter(starts_at__lte=now)
        elif status_filter == 'recorded':
            qs = qs.exclude(recording_url='')
        return qs.order_by('starts_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = LiveSession.objects.filter(course__in=self.owned_courses())
        course_id = self.request.GET.get('course')
        if course_id:
            base_qs = base_qs.filter(course_id=course_id)
        now = timezone.now()
        context['total_count'] = base_qs.count()
        context['upcoming_count'] = base_qs.filter(starts_at__gt=now).count()
        context['past_count'] = base_qs.filter(starts_at__lte=now).count()
        context['recorded_count'] = base_qs.exclude(recording_url='').count()
        context['sessions'] = self.get_queryset()
        context['courses'] = self.owned_courses().order_by('title')
        context['active_course'] = course_id or ''
        context['active_status'] = self.request.GET.get('status', 'all')
        return context


class LiveSessionCreateView(LiveSessionEditorMixin, CreateView):
    model = LiveSession
    form_class = LiveSessionForm
    template_name = 'courses/manage/live_session_form.html'
    success_url = reverse_lazy('live-session-list')

    def form_valid(self, form):
        if not form.instance.course_id:
            form.instance.course = self.owned_courses().first()

        schedule_type = form.cleaned_data.get('schedule_type')
        computed_dates = form.cleaned_data.get('computed_recurring_dates')
        recurrence_rule_str = form.cleaned_data.get('recurrence_rule_str', '')

        if schedule_type == 'recurring' and computed_dates and len(computed_dates) > 1:
            import uuid
            series_id = uuid.uuid4()
            total_sessions = len(computed_dates)
            base_title = form.cleaned_data.get('title')
            course = form.instance.course
            provider_type = form.cleaned_data.get('provider')
            join_url = form.cleaned_data.get('join_url', '')
            duration = form.cleaned_data.get('duration_minutes', 60)
            record_meeting = form.cleaned_data.get('record_meeting', True)
            notes = form.cleaned_data.get('notes', '')
            is_published = form.cleaned_data.get('is_published', True)

            provider = get_live_provider(provider_type)
            created_sessions = []

            for idx, dt in enumerate(computed_dates, start=1):
                session = LiveSession(
                    course=course,
                    title=f"{base_title} - Session {idx}/{total_sessions}",
                    provider=provider_type,
                    join_url=join_url,
                    starts_at=dt,
                    duration_minutes=duration,
                    record_meeting=record_meeting,
                    notes=notes,
                    is_published=is_published,
                    series_id=series_id,
                    session_number=idx,
                    total_sessions_in_series=total_sessions,
                    recurrence_rule=recurrence_rule_str,
                )
                session.save()
                try:
                    provider.prepare_session(session, host_user=self.request.user)
                except Exception:
                    pass
                created_sessions.append(session)

            self.object = created_sessions[0]
            messages.success(
                self.request,
                f"Multi-day live class series “{base_title}” ({total_sessions} sessions: {recurrence_rule_str}) successfully scheduled! အကြိမ်ကြိမ်သင်ကြားမှု အတန်းစဉ် {total_sessions} ခု ဖွင့်လှစ်ပြီးပါပြီ။"
            )
            return redirect(self.get_success_url())
        else:
            response = super().form_valid(form)
            # Prepare session room with provider
            provider = get_live_provider(self.object.provider)
            try:
                provider.prepare_session(self.object, host_user=self.request.user)
            except Exception:
                pass
            messages.success(self.request, f"Live session “{self.object.title}” scheduled successfully.")
            return response


class LiveSessionUpdateView(LiveSessionEditorMixin, UpdateView):
    model = LiveSession
    form_class = LiveSessionForm
    template_name = 'courses/manage/live_session_form.html'
    success_url = reverse_lazy('live-session-list')
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        return LiveSession.objects.filter(course__in=self.owned_courses())

    def form_valid(self, form):
        response = super().form_valid(form)
        provider = get_live_provider(self.object.provider)
        try:
            provider.prepare_session(self.object, host_user=self.request.user)
        except Exception:
            pass
        messages.success(self.request, "Live session updated.")
        return response


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


class LiveSessionDetailView(LoginRequiredMixin, DetailView):
    """
    Dedicated virtual classroom stage for THUTA courses.
    Supports BigBlueButton (THUTA Classroom), Zoom, and Google Meet with countdown timer,
    host launch controls, attendance roster, and replay player.
    """
    model = LiveSession
    template_name = 'courses/live_session_detail.html'
    pk_url_kwarg = 'session_id'
    context_object_name = 'session'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        session = self.get_object()
        course = session.course
        user = request.user
        if not (user_can_manage_live_session(user, session) or can_access_course(user, course)):
            messages.warning(request, "You must be enrolled in this course to access this live classroom.")
            return redirect('course-detail', slug=course.slug)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        user = request.user
        if not user_can_manage_live_session(user, session):
            messages.error(request, "Only the instructor or platform administrator can control this live session.")
            return redirect('live-session-detail', session_id=session.id)

        action = request.POST.get('action')
        from django.utils import timezone
        from datetime import timedelta

        if action == 'start_now':
            session.starts_at = timezone.now() - timedelta(minutes=1)
            if session.duration_minutes < 15:
                session.duration_minutes = 60
            session.save(update_fields=['starts_at', 'duration_minutes'])
            messages.success(request, "🔴 Live Classroom Activated! အတန်းကို တိုက်ရိုက် စတင်လိုက်ပါပြီ။")
        elif action == 'end_now':
            elapsed = max(1, int((timezone.now() - session.starts_at).total_seconds() / 60))
            session.duration_minutes = elapsed
            session.starts_at = timezone.now() - timedelta(minutes=elapsed + 1)
            session.save(update_fields=['starts_at', 'duration_minutes'])
            messages.info(request, "⏹️ Live Session Concluded. အတန်းသင်ကြားမှု ပြီးဆုံးပါပြီ။")
        elif action == 'extend_30':
            session.duration_minutes += 30
            session.save(update_fields=['duration_minutes'])
            messages.success(request, f"⏱️ Extended by 30 minutes. သင်ကြားချိန် ၃၀ မိနစ် ထပ်တိုးလိုက်ပါပြီ (Total: {session.duration_minutes}m).")

        return redirect('live-session-detail', session_id=session.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object
        course = session.course
        user = self.request.user
        provider = get_live_provider(session.provider)

        context['course'] = course
        context['is_host'] = user_can_manage_live_session(user, session)
        context['status'] = session.status
        context['is_live'] = session.is_live
        context['is_upcoming'] = session.is_upcoming
        context['is_ended'] = session.is_ended
        context['has_replay'] = session.has_replay
        context['ends_at'] = session.ends_at
        context['other_sessions'] = course.live_sessions.filter(
            is_published=True
        ).exclude(id=session.id).order_by('starts_at')[:5]
        if session.series_id:
            context['series_sessions'] = session.get_series_sessions()
        else:
            context['series_sessions'] = None

        # Multi-provider classroom configuration
        context['provider'] = provider
        context['provider_code'] = session.provider
        context['provider_name'] = provider.name
        context['is_bbb'] = session.is_bbb
        context['supports_embedded'] = provider.supports_embedded_client
        context['supports_attendance_sync'] = provider.supports_attendance_sync
        context['supports_recording_sync'] = provider.supports_recording_sync

        # Attendances list for host/teacher
        if context['is_host']:
            context['attendances'] = session.attendances.select_related('user').order_by('-joined_at')[:50]
            context['attendance_count'] = session.attendances.count()

        # Legacy Jitsi connection parameters for backward compatibility
        jitsi_config = get_jitsi_connection_config(user, session)
        context['jitsi_config'] = jitsi_config
        context['jitsi_room_name'] = jitsi_config['room_name']
        context['jitsi_domain'] = jitsi_config['domain']

        # External provider detection (e.g. Google Meet, Zoom)
        is_external = session.provider in [
            LiveSession.Provider.ZOOM,
            LiveSession.Provider.GOOGLE_MEET,
            LiveSession.Provider.TEAMS,
            LiveSession.Provider.OTHER,
        ] and bool(session.join_url and ('meet.google.com' in session.join_url or 'zoom.us' in session.join_url or 'teams.microsoft.com' in session.join_url))

        join_url = provider.get_join_url(session, user, is_host=context['is_host'])
        context['join_url'] = join_url
        context['is_external'] = is_external

        # Embedded live video stream
        import urllib.parse
        full_name = user.get_full_name() or user.username or 'THUTA Learner'
        encoded_name = urllib.parse.quote(full_name)
        room_name = jitsi_config['room_name']

        if is_external and session.join_url:
            context['embedded_video_url'] = session.join_url
            context['can_embed'] = False
        else:
            context['can_embed'] = True
            if session.is_bbb and join_url and 'meet.jit.si' not in join_url:
                context['embedded_video_url'] = join_url
            else:
                context['embedded_video_url'] = f"https://meet.jit.si/{room_name}#userInfo.displayName=\"{encoded_name}\"&config.prejoinPageEnabled=false&config.startWithAudioMuted=false&config.startWithVideoMuted=false"

        return context


class LiveSessionJoinView(LoginRequiredMixin, View):
    """
    Secure single-click entrypoint to virtual classrooms:
    1. Verifies course enrollment or host permissions.
    2. Prevents students from joining before the scheduled time.
    3. Logs attendance in LiveSessionAttendance (user, role, IP, user-agent).
    4. Generates signed BigBlueButton join URL or external Zoom/Meet link.
    5. Redirects authenticated attendee directly into the video room.
    """
    def get(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        course = session.course
        user = request.user

        # Permission check
        is_host = user_can_manage_live_session(user, session)
        if not (is_host or can_access_course(user, course)):
            messages.error(request, "You must be enrolled in this course to join the live virtual classroom.")
            return redirect('course-detail', slug=course.slug)

        # Early entry policy: only hosts can enter before scheduled time to prepare slides/audio
        if session.is_upcoming and not is_host:
            messages.info(request, "This live class has not started yet. Please wait for the scheduled start time.")
            return redirect('live-session-detail', session_id=session.id)

        # Log attendance record
        role = 'moderator' if is_host else 'student'
        LiveSessionAttendance.objects.get_or_create(
            session=session,
            user=user,
            defaults={
                'role': role,
                'is_moderator': is_host,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:250],
                'ip_address': request.META.get('REMOTE_ADDR'),
            }
        )

        # Generate target join URL via provider
        provider = get_live_provider(session.provider)
        join_url = provider.get_join_url(session, user, is_host=is_host)

        if not join_url:
            messages.warning(request, "The meeting link has not been published by the instructor yet.")
            return redirect('live-session-detail', session_id=session.id)

        return HttpResponseRedirect(join_url)


class LiveSessionSyncAttendanceView(LoginRequiredMixin, View):
    """
    Instructor/Admin action: queries BigBlueButton /getMeetingInfo to synchronize
    active participants into the THUTA attendance ledger.
    """
    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        user = request.user
        if not user_can_manage_live_session(user, session):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        provider = get_live_provider(session.provider)
        status_info = provider.get_meeting_status(session)

        # For BigBlueButton, reconcile returned participants with database users
        synced_count = 0
        from django.contrib.auth import get_user_model
        User = get_user_model()

        for att in status_info.attendees:
            user_id = att.get('userID')
            matched_user = None
            if user_id:
                try:
                    matched_user = User.objects.filter(id=user_id).first()
                except Exception:
                    pass
            if not matched_user:
                full_name = att.get('fullName', '')
                matched_user = User.objects.filter(username=full_name).first()

            if matched_user:
                is_mod = (att.get('role', '').upper() == 'MODERATOR')
                LiveSessionAttendance.objects.get_or_create(
                    session=session,
                    user=matched_user,
                    defaults={
                        'role': 'moderator' if is_mod else 'student',
                        'is_moderator': is_mod,
                        'user_agent': 'BigBlueButton-Sync',
                    }
                )
                synced_count += 1

        total_attendees = session.attendances.count()
        messages.success(request, f"Attendance synced: {total_attendees} participants recorded.")
        return JsonResponse({
            'status': 'success',
            'is_running': status_info.is_running,
            'participant_count': status_info.participant_count,
            'synced_count': synced_count,
            'total_attendances': total_attendees,
        })


class LiveSessionRecordingSyncView(LoginRequiredMixin, View):
    """
    Instructor/Admin action: checks BigBlueButton /getRecordings to link published lecture replay.
    """
    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        user = request.user
        if not user_can_manage_live_session(user, session):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        provider = get_live_provider(session.provider)
        recordings = provider.fetch_recordings(session)

        if recordings and recordings[0].playback_url:
            rec = recordings[0]
            session.recording_url = rec.playback_url
            session.bbb_recording_id = rec.record_id
            session.save(update_fields=['recording_url', 'bbb_recording_id', 'updated_at'])
            messages.success(request, "Lecture replay discovered and attached to course!")
            return JsonResponse({'status': 'success', 'recording_url': session.recording_url})

        return JsonResponse({'status': 'none', 'message': 'No processed recordings found on conferencing server yet.'})


class LiveSessionAttendanceView(LoginRequiredMixin, View):
    """
    AJAX endpoint invoked by client event hooks to log participant join/leave attendance.
    """
    def post(self, request, session_id):
        session = get_object_or_404(LiveSession, id=session_id)
        course = session.course
        user = request.user
        is_host = user_can_manage_live_session(user, session)
        if not (is_host or can_access_course(user, course)):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        action = request.POST.get('action', 'join')
        now = timezone.now()

        attendance, created = LiveSessionAttendance.objects.get_or_create(
            session=session,
            user=user,
            defaults={
                'role': 'moderator' if is_host else 'student',
                'is_moderator': is_host,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:250],
                'ip_address': request.META.get('REMOTE_ADDR'),
            }
        )

        if action == 'leave':
            attendance.left_at = now
            if attendance.joined_at:
                delta = (now - attendance.joined_at).total_seconds()
                attendance.duration_seconds = max(0, int(delta))
            attendance.save(update_fields=['left_at', 'duration_seconds', 'updated_at'])
            return JsonResponse({
                'status': 'success',
                'action': 'leave',
                'duration_seconds': attendance.duration_seconds
            })

        return JsonResponse({
            'status': 'success',
            'action': 'join',
            'joined_at': attendance.joined_at.isoformat(),
        })


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import hmac
import hashlib


@method_decorator(csrf_exempt, name='dispatch')
class LiveSessionWebhookView(View):
    """
    Idempotent webhook receiver for virtual classroom providers (BigBlueButton, Zoom, Google Meet).
    Processes asynchronous event callbacks:
    - meeting-ended: concludes session, updates attendance records.
    - user-joined: logs attendee entry with role.
    - user-left: records attendee departure and calculates total duration.
    - rap-publish-ended / recording-ready: attaches published lecture replay URL to the course.
    """
    def post(self, request, provider='bigbluebutton'):
        try:
            body = request.body.decode('utf-8')
            data = json.loads(body) if body else {}
        except Exception:
            data = request.POST.dict()

        # Check signature if secret configured
        try:
            from apps.courses.models import LiveProviderSetting
            setting = LiveProviderSetting.objects.filter(provider=provider).first()
            secret = (setting.webhook_secret or setting.shared_secret) if setting else ''
        except Exception:
            secret = ''

        if secret:
            signature = request.headers.get('X-BBB-Signature') or request.headers.get('X-Signature') or request.GET.get('checksum')
            if signature and not request.GET.get('checksum'):
                computed = hmac.new(secret.encode('utf-8'), request.body, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(computed, signature):
                    return JsonResponse({'error': 'Invalid webhook signature'}, status=403)

        event_items = []
        if isinstance(data, dict):
            if 'event' in data and isinstance(data['event'], list):
                event_items = data['event']
            elif 'event' in data and isinstance(data['event'], dict):
                event_items = [data['event']]
            else:
                event_items = [data]
        elif isinstance(data, list):
            event_items = data

        processed_events = []
        from django.contrib.auth import get_user_model
        User = get_user_model()

        for item in event_items:
            event_type = ''
            attrs = {}
            if isinstance(item, dict) and 'data' in item and isinstance(item['data'], dict):
                d = item['data']
                event_type = d.get('id', '')
                attrs = d.get('attributes', {})
            elif isinstance(item, dict):
                event_type = item.get('event') or item.get('type') or item.get('id', '')
                attrs = item

            event_name = (event_type or '').lower().replace('_', '-').replace('.', '-')

            meeting_id = ''
            if isinstance(attrs, dict) and 'meeting' in attrs and isinstance(attrs['meeting'], dict):
                meeting_id = attrs['meeting'].get('external-meeting-id') or attrs['meeting'].get('meeting-id') or ''
            if not meeting_id and isinstance(attrs, dict):
                meeting_id = attrs.get('meeting_id') or attrs.get('meetingID') or attrs.get('external_meeting_id') or ''

            session = LiveSession.objects.filter(meeting_id=meeting_id).first() if meeting_id else None

            # 1. Meeting Ended
            if 'meeting-ended' in event_name or event_name == 'meeting-end':
                if session:
                    now = timezone.now()
                    for att in session.attendances.filter(left_at__isnull=True):
                        att.left_at = now
                        if att.joined_at:
                            delta = (now - att.joined_at).total_seconds()
                            att.duration_seconds = max(0, int(delta))
                        att.save(update_fields=['left_at', 'duration_seconds', 'updated_at'])
                    processed_events.append({'event': 'meeting-ended', 'meeting_id': meeting_id, 'status': 'closed'})

            # 2. User Joined
            elif 'user-joined' in event_name or event_name == 'user-join':
                if session and isinstance(attrs, dict):
                    u_data = attrs.get('user', {}) if isinstance(attrs.get('user'), dict) else attrs
                    user_id = u_data.get('external-user-id') or u_data.get('user_id') or u_data.get('userId')
                    full_name = u_data.get('name') or u_data.get('full_name') or ''
                    role_str = str(u_data.get('role') or 'VIEWER').upper()
                    is_mod = (role_str == 'MODERATOR')

                    target_user = None
                    if user_id:
                        try:
                            target_user = User.objects.filter(id=user_id).first()
                        except Exception:
                            pass
                    if not target_user and full_name:
                        target_user = User.objects.filter(username=full_name).first()

                    if target_user:
                        LiveSessionAttendance.objects.get_or_create(
                            session=session,
                            user=target_user,
                            defaults={
                                'role': 'moderator' if is_mod else 'student',
                                'is_moderator': is_mod,
                                'user_agent': f"Webhook ({provider})",
                            }
                        )
                        processed_events.append({'event': 'user-joined', 'user': target_user.username})

            # 3. User Left
            elif 'user-left' in event_name or event_name == 'user-leave':
                if session and isinstance(attrs, dict):
                    u_data = attrs.get('user', {}) if isinstance(attrs.get('user'), dict) else attrs
                    user_id = u_data.get('external-user-id') or u_data.get('user_id') or u_data.get('userId')
                    full_name = u_data.get('name') or u_data.get('full_name') or ''

                    target_user = None
                    if user_id:
                        try:
                            target_user = User.objects.filter(id=user_id).first()
                        except Exception:
                            pass
                    if not target_user and full_name:
                        target_user = User.objects.filter(username=full_name).first()

                    if target_user:
                        att = session.attendances.filter(user=target_user, left_at__isnull=True).order_by('-joined_at').first()
                        if att:
                            now = timezone.now()
                            att.left_at = now
                            if att.joined_at:
                                att.duration_seconds = max(0, int((now - att.joined_at).total_seconds()))
                            att.save(update_fields=['left_at', 'duration_seconds', 'updated_at'])
                            processed_events.append({'event': 'user-left', 'user': target_user.username, 'duration': att.duration_seconds})

            # 4. Recording Published
            elif any(k in event_name for k in ['rap-publish-ended', 'recording-ready', 'recording-published']):
                rec_data = attrs.get('recording', {}) if isinstance(attrs, dict) and isinstance(attrs.get('recording'), dict) else (attrs if isinstance(attrs, dict) else {})
                playback_url = ''
                playback = rec_data.get('playback', {})
                if isinstance(playback, dict) and 'format' in playback:
                    formats = playback['format']
                    if isinstance(formats, list) and formats:
                        playback_url = formats[0].get('url', '')
                    elif isinstance(formats, dict):
                        playback_url = formats.get('url', '')
                if not playback_url and isinstance(rec_data, dict):
                    playback_url = rec_data.get('playback_url') or attrs.get('playback_url') or attrs.get('url', '')

                record_id = (rec_data.get('record-id') or rec_data.get('record_id') or attrs.get('record_id', '')) if isinstance(rec_data, dict) else ''

                if session and playback_url:
                    session.recording_url = playback_url
                    if record_id:
                        session.bbb_recording_id = record_id
                    session.save(update_fields=['recording_url', 'bbb_recording_id', 'updated_at'])
                    processed_events.append({'event': 'recording-published', 'playback_url': playback_url})

        return JsonResponse({
            'status': 'received',
            'provider': provider,
            'processed_count': len(processed_events),
            'events': processed_events,
        })



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

