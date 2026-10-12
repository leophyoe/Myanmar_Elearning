import json
import uuid
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView, DetailView, View, CreateView, UpdateView, DeleteView,
)

from apps.common.permissions import TeacherRequiredMixin, AdminRequiredMixin
from apps.billing.models import Payment, PaymentMethod, has_paid_standalone_exam
from apps.billing.forms import PaymentSubmitForm
from apps.certificates.models import Certificate
from apps.partner.models import Institution
from .models import Quiz, Question, Choice, QuizAttempt
from .exam_forms import StandaloneExamForm, ExamGradingRubricForm
from .services.assessment import (
    check_assessment_attempt_eligibility,
    grade_assessment_attempt,
    manual_grade_attempt,
    serialize_exam_for_student,
)


class StandaloneExamListView(ListView):
    """
    Catalog of Standalone Exams, Professional Certifications, and Skill Assessments.
    Students can browse, filter (Free vs Verified), and test their skills without
    mandatory course enrollment.
    """
    model = Quiz
    template_name = 'courses/exam_list.html'
    context_object_name = 'exams'
    paginate_by = 12

    def get_queryset(self):
        qs = Quiz.objects.filter(
            Q(is_standalone=True) | Q(quiz_type__in=[Quiz.AssessmentType.COURSE_EXAM, Quiz.AssessmentType.FINAL_EXAM]),
            status=Quiz.Status.PUBLISHED,
        ).select_related('owner', 'assigned_instructor', 'institution', 'course')

        # Filters
        exam_type = self.request.GET.get('type', 'all')
        if exam_type == 'free':
            qs = qs.filter(price__lte=0)
        elif exam_type == 'paid':
            qs = qs.filter(price__gt=0)
        elif exam_type == 'verified':
            qs = qs.filter(certificate_type='exam_verified')

        institution_id = self.request.GET.get('institution')
        if institution_id:
            qs = qs.filter(institution_id=institution_id)

        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['institutions'] = Institution.objects.filter(is_verified=True).order_by('name')
        context['selected_type'] = self.request.GET.get('type', 'all')
        context['selected_institution'] = self.request.GET.get('institution', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['total_count'] = self.get_queryset().count()

        if user.is_authenticated:
            # Map user's attempts and verified certificates
            user_attempts = QuizAttempt.objects.filter(student=user).select_related('quiz', 'certificate')
            context['user_attempts_by_exam'] = {
                str(att.quiz_id): att for att in user_attempts
            }
            user_certs = Certificate.objects.filter(student=user, is_revoked=False).select_related('exam')
            context['user_certs_by_exam'] = {
                str(c.exam_id): c for c in user_certs if c.exam_id
            }
        else:
            context['user_attempts_by_exam'] = {}
            context['user_certs_by_exam'] = {}

        return context


class StandaloneExamDetailView(DetailView):
    """
    Overview, syllabus, rules, and entry point for a specific examination.
    """
    model = Quiz
    template_name = 'courses/exam_detail.html'
    context_object_name = 'exam'
    pk_url_kwarg = 'exam_id'

    def get_queryset(self):
        return Quiz.objects.all().select_related(
            'owner', 'assigned_instructor', 'institution', 'course'
        ).prefetch_related('questions')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.object
        user = self.request.user

        context['total_questions'] = exam.questions.count()
        context['total_points'] = sum(q.points for q in exam.questions.all())

        if user.is_authenticated:
            is_eligible, reason = check_assessment_attempt_eligibility(user, exam)
            context['is_eligible'] = is_eligible
            context['eligibility_reason'] = reason

            user_attempts = exam.attempts.filter(student=user).order_by('-created_at')
            context['user_attempts'] = user_attempts
            context['attempts_count'] = user_attempts.count()
            context['best_attempt'] = user_attempts.order_by('-score_percentage').first()
            context['has_passed'] = user_attempts.filter(passed=True).exists()

            # Certificate if issued
            context['earned_certificate'] = Certificate.objects.filter(
                student=user, exam=exam, is_revoked=False
            ).first()

            # Pending payment check
            context['pending_payment'] = Payment.objects.filter(
                student=user, exam=exam, status=Payment.Status.PENDING
            ).first()

            context['has_access'] = has_paid_standalone_exam(user, exam)
            context['is_staff_or_owner'] = (
                user.is_admin or user == exam.owner or user == exam.assigned_instructor
            )
        else:
            context['is_eligible'] = False
            context['eligibility_reason'] = "Login required to participate in this exam."
            context['user_attempts'] = []
            context['attempts_count'] = 0
            context['best_attempt'] = None
            context['has_passed'] = False
            context['earned_certificate'] = None
            context['pending_payment'] = None
            context['has_access'] = exam.is_free
            context['is_staff_or_owner'] = False

        return context


class ExamCheckoutView(LoginRequiredMixin, View):
    """
    Checkout page for purchasing standalone exam access or exam vouchers.
    Supports MMQR, KBZ Pay, Wave Pay, Bank Transfer, and Instant Zero-Cost Activation.
    """
    template_name = 'courses/exam_checkout.html'

    def get_exam(self):
        exam_id = self.kwargs.get('exam_id')
        return get_object_or_404(Quiz, id=exam_id, status=Quiz.Status.PUBLISHED)

    def get(self, request, *args, **kwargs):
        exam = self.get_exam()
        if exam.is_free:
            messages.info(request, "This examination is free! You can start immediately.")
            return redirect('exam-session', exam_id=exam.id)

        if has_paid_standalone_exam(request.user, exam):
            messages.info(request, "You already have active authorization for this exam.")
            return redirect('standalone-exam-detail', exam_id=exam.id)

        pending_payment = Payment.objects.filter(
            student=request.user, exam=exam, status=Payment.Status.PENDING
        ).first()

        payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
        form = PaymentSubmitForm()

        return render(request, self.template_name, {
            'exam': exam,
            'form': form,
            'pending_payment': pending_payment,
            'payment_methods': payment_methods,
        })

    def post(self, request, *args, **kwargs):
        exam = self.get_exam()
        if exam.is_free:
            return redirect('exam-session', exam_id=exam.id)

        existing_pending = Payment.objects.filter(
            student=request.user, exam=exam, status=Payment.Status.PENDING
        ).first()
        if existing_pending:
            messages.info(request, "Your exam payment is already awaiting admin verification.")
            return redirect('standalone-exam-detail', exam_id=exam.id)

        form = PaymentSubmitForm(request.POST, request.FILES)
        if not form.is_valid():
            payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
            return render(request, self.template_name, {
                'exam': exam,
                'form': form,
                'payment_methods': payment_methods,
            })

        payment = form.save(commit=False)
        payment.student = request.user
        payment.exam = exam
        payment.course = exam.course
        payment.payment_type = Payment.PaymentType.EXAM_VOUCHER
        payment.amount = exam.price
        payment.currency = exam.currency or 'MMK'
        payment.platform_fee, payment.teacher_amount = Payment.split(exam.price)
        payment.status = Payment.Status.PENDING
        payment.save()

        messages.success(
            request,
            "Your exam registration payment has been submitted! Our admin team will verify it promptly."
        )
        return redirect('standalone-exam-detail', exam_id=exam.id)


class ExamSessionView(LoginRequiredMixin, View):
    """
    Live interactive examination environment.
    Modeled after modern testing interfaces (reference image 1):
    - Clean test header with countdown timer
    - Section & Question Palette (1 to N) with answered/unanswered/flagged badges
    - Zero client-side leakage of answer keys or rubric data
    """
    template_name = 'courses/exam_session.html'

    def get_exam(self):
        exam_id = self.kwargs.get('exam_id')
        return get_object_or_404(Quiz, id=exam_id, status=Quiz.Status.PUBLISHED)

    def get(self, request, *args, **kwargs):
        exam = self.get_exam()
        is_eligible, reason = check_assessment_attempt_eligibility(request.user, exam)
        if not is_eligible:
            messages.error(request, reason or "You are not eligible to take this examination.")
            return redirect('standalone-exam-detail', exam_id=exam.id)

        # Serialized exam data without answer keys
        exam_payload = serialize_exam_for_student(exam)

        return render(request, self.template_name, {
            'exam': exam,
            'exam_payload_json': json.dumps(exam_payload),
            'questions': exam_payload['questions'],
            'time_limit_minutes': exam.time_limit_minutes,
            'time_limit_seconds': exam.time_limit_minutes * 60,
        })


class ExamSubmitView(LoginRequiredMixin, View):
    """
    Receives and processes completed exam submission.
    """
    def post(self, request, *args, **kwargs):
        exam_id = self.kwargs.get('exam_id')
        exam = get_object_or_404(Quiz, id=exam_id)

        time_taken = request.POST.get('time_taken_seconds', 0)
        try:
            time_taken = int(time_taken)
        except ValueError:
            time_taken = 0

        attempt, msg = grade_assessment_attempt(
            assessment=exam,
            user=request.user,
            submitted_answers=request.POST,
            time_taken_seconds=time_taken,
        )

        messages.info(request, msg)
        return redirect('exam-result', exam_id=exam.id, attempt_id=attempt.id)


class ExamResultView(LoginRequiredMixin, DetailView):
    """
    Displays the score, breakdown, feedback, and verifiable certificate upon passing.
    """
    model = QuizAttempt
    template_name = 'courses/exam_result.html'
    context_object_name = 'attempt'
    pk_url_kwarg = 'attempt_id'

    def get_object(self, queryset=None):
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz', 'student', 'certificate', 'graded_by'),
            id=self.kwargs['attempt_id']
        )
        # Check permissions: student, assigned instructor, owner, or admin
        user = self.request.user
        if (
            attempt.student != user and
            not user.is_admin and
            attempt.quiz.owner != user and
            attempt.quiz.assigned_instructor != user
        ):
            raise PermissionDenied("You do not have permission to view this examination attempt.")
        return attempt

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.object
        context['exam'] = attempt.quiz
        context['certificate'] = attempt.certificate or Certificate.objects.filter(
            student=attempt.student, exam=attempt.quiz, is_revoked=False
        ).first()
        return context


class ExamGradingQueueView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """
    Instructor & Evaluator queue of pending exam attempts requiring manual grading.
    Modeled after standard assessment management dashboards.
    """
    model = QuizAttempt
    template_name = 'courses/exam_grading_queue.html'
    context_object_name = 'attempts'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = QuizAttempt.objects.filter(
            status=QuizAttempt.AttemptStatus.PENDING_REVIEW
        ).select_related('quiz', 'student', 'quiz__course', 'quiz__institution')

        if not user.is_admin:
            # Instructors only evaluate exams they own or are designated to grade
            qs = qs.filter(
                Q(quiz__owner=user) |
                Q(quiz__assigned_instructor=user) |
                Q(quiz__course__owner=user)
            )

        exam_id = self.request.GET.get('exam')
        if exam_id:
            qs = qs.filter(quiz_id=exam_id)

        return qs.order_by('created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_admin:
            context['exams'] = Quiz.objects.filter(requires_manual_grading=True).order_by('title')
        else:
            context['exams'] = Quiz.objects.filter(
                Q(owner=user) | Q(assigned_instructor=user) | Q(course__owner=user)
            ).filter(requires_manual_grading=True).order_by('title')
        context['selected_exam'] = self.request.GET.get('exam', '')
        return context


class ExamGradingDetailView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Instructor Rubric Grading View (Modeled after reference image 2):
    - Assessment details and student identity
    - Criteria-based evaluation table: Criteria description, Rating scales (3, 2, 1, 0),
      Points input, Comments per criterion
    - Overall evaluation feedback textarea
    - Finalize score and automatically issue Exam-Based Verified Certificate upon passing
    """
    template_name = 'courses/exam_grading_detail.html'

    def get_attempt(self):
        attempt_id = self.kwargs.get('attempt_id')
        attempt = get_object_or_404(
            QuizAttempt.objects.select_related('quiz', 'student', 'quiz__course', 'quiz__institution'),
            id=attempt_id
        )
        user = self.request.user
        if not user.is_admin and attempt.quiz.owner != user and attempt.quiz.assigned_instructor != user and getattr(attempt.quiz.course, 'owner', None) != user:
            raise PermissionDenied("You are not authorized to grade this examination attempt.")
        return attempt

    def get(self, request, *args, **kwargs):
        attempt = self.get_attempt()
        form = ExamGradingRubricForm(initial={'overall_feedback': attempt.feedback or ''})

        # Build list of questions and submitted student answers
        questions = attempt.quiz.questions.all().order_by('order')
        answers_data = attempt.answers_data or {}

        questions_for_grading = []
        for q in questions:
            q_ans = answers_data.get(str(q.id), {})
            questions_for_grading.append({
                'question': q,
                'submitted_answer': q_ans.get('raw_answer', 'No answer provided'),
                'points_earned': q_ans.get('points_earned', 0),
                'max_points': q.points,
                'is_correct': q_ans.get('is_correct', False),
                'feedback': q_ans.get('evaluator_feedback', q_ans.get('feedback', '')),
                'rubric_criteria': q.rubric_criteria,
            })

        return render(request, self.template_name, {
            'attempt': attempt,
            'exam': attempt.quiz,
            'form': form,
            'questions_for_grading': questions_for_grading,
        })

    def post(self, request, *args, **kwargs):
        attempt = self.get_attempt()
        form = ExamGradingRubricForm(request.POST)

        rubric_scores = {}
        for q in attempt.quiz.questions.all():
            qid_str = str(q.id)
            pts_key = f"points_{qid_str}"
            feedback_key = f"feedback_{qid_str}"
            level_key = f"rating_{qid_str}"

            if pts_key in request.POST:
                try:
                    pts = int(request.POST.get(pts_key, 0))
                except ValueError:
                    pts = 0
                rubric_scores[qid_str] = {
                    'points': pts,
                    'feedback': request.POST.get(feedback_key, '').strip(),
                    'criteria_level': request.POST.get(level_key, ''),
                }

        overall_feedback = request.POST.get('overall_feedback', '').strip()
        updated_attempt = manual_grade_attempt(
            attempt=attempt,
            evaluator=request.user,
            rubric_scores=rubric_scores,
            overall_feedback=overall_feedback,
        )

        messages.success(
            request,
            f"Examination graded for {updated_attempt.student.username}. Final Score: {updated_attempt.score_percentage}% ({'PASSED' if updated_attempt.passed else 'FAILED'})."
        )
        return redirect('exam-grading-queue')


class StandaloneExamCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """
    Creates a new standalone exam or course-level final assessment.
    """
    model = Quiz
    form_class = StandaloneExamForm
    template_name = 'courses/manage/exam_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        course_id = self.request.GET.get('course')
        course_slug = self.request.GET.get('course_slug')
        from apps.courses.models import Course
        c = None
        if course_id:
            c = Course.objects.filter(id=course_id).first()
        elif course_slug:
            c = Course.objects.filter(slug=course_slug).first()

        if c:
            initial['course'] = c
            initial['quiz_type'] = Quiz.AssessmentType.FINAL_EXAM
            initial['title'] = f"{c.title} - Final Assessment Exam"
            initial['certificate_type'] = 'course_completion'
        return initial

    def form_valid(self, form):
        exam = form.save(commit=False)
        exam.owner = self.request.user
        if not exam.assigned_instructor:
            exam.assigned_instructor = self.request.user

        if exam.course:
            exam.is_standalone = False
            exam.course.exam_required = True
            exam.course.save(update_fields=['exam_required'])
        else:
            exam.is_standalone = True

        exam.save()
        messages.success(self.request, f"Exam '{exam.title}' created successfully! Now add questions.")
        return redirect('quiz-edit', lesson_id=exam.id)


class StandaloneExamUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    """
    Updates an existing standalone exam or course final assessment.
    """
    model = Quiz
    form_class = StandaloneExamForm
    template_name = 'courses/manage/exam_form.html'
    pk_url_kwarg = 'exam_id'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Quiz.objects.all()
        return Quiz.objects.filter(
            Q(owner=user) | Q(assigned_instructor=user) | Q(course__owner=user)
        ).distinct()

    def form_valid(self, form):
        exam = form.save(commit=False)
        if exam.course:
            exam.course.exam_required = True
            exam.course.save(update_fields=['exam_required'])
        exam.save()
        messages.success(self.request, f"Exam '{exam.title}' updated successfully.")
        if exam.course:
            return redirect('course-edit', slug=exam.course.slug)
        return redirect('standalone-exam-detail', exam_id=exam.id)

