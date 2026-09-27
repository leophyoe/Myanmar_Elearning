import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import DetailView, ListView
from django.contrib import messages
from django.utils import timezone
from apps.courses.models import Course
from apps.enrollments.models import Enrollment, EnrollmentStatus
from .models import (
    Quiz, Question, QuestionOption, QuizAttempt, QuizAnswer,
    Assignment, AssignmentSubmission, AssignmentFeedback, SubmissionStatus,
    Exam, ExamAttempt, ExamAnswer, AssessmentWeight
)
from .services import QuizGradingService, ExamTimerService, GradeCalculationService

logger = logging.getLogger(__name__)


# ==============================================================================
# QUIZ VIEWS
# ==============================================================================

class QuizDetailView(LoginRequiredMixin, DetailView):
    model = Quiz
    template_name = 'assessments/quiz_detail.html'
    context_object_name = 'quiz'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        quiz = self.object
        student = self.request.user
        attempts = QuizAttempt.objects.filter(quiz=quiz, student=student)
        ctx['attempts'] = attempts
        ctx['attempts_count'] = attempts.count()
        ctx['attempts_remaining'] = max(0, quiz.max_attempts - attempts.count())
        ctx['has_passed'] = attempts.filter(passed=True).exists()
        ctx['best_attempt'] = attempts.order_by('-score').first()
        return ctx


class QuizTakeView(LoginRequiredMixin, View):
    """
    Renders quiz interface. Crucially, is_correct flags and explanations
    are stripped from the context so the answer key is never exposed.
    """
    def get(self, request, pk):
        quiz = get_object_or_404(Quiz, pk=pk, is_published=True)
        student = request.user

        # Ensure student enrollment for progress tracking
        if not (student.is_instructor or student.is_academy_admin or student.is_superuser):
            Enrollment.objects.get_or_create(
                student=student,
                course=quiz.course,
                defaults={'status': EnrollmentStatus.ACTIVE}
            )

        # Resume existing in-progress attempt if present
        attempt = QuizAttempt.objects.filter(quiz=quiz, student=student, is_completed=False).first()
        if not attempt:
            attempts_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()
            if attempts_count >= quiz.max_attempts:
                messages.error(request, f"You have reached the maximum allowed attempts ({quiz.max_attempts}) for this quiz.")
                return redirect('assessments:quiz-detail', pk=quiz.pk)

            # Create new in-progress attempt
            attempt = QuizAttempt.objects.create(
                student=student,
                quiz=quiz,
                attempt_number=attempts_count + 1,
                started_at=timezone.now(),
                is_completed=False
            )

        questions = list(quiz.questions.filter(is_active=True).prefetch_related('options'))
        if quiz.randomize_questions:
            import random
            random.shuffle(questions)

        # Prepare questions with masked options (no is_correct)
        sanitized_questions = []
        for q in questions:
            opts = list(q.options.filter(is_active=True))
            if quiz.randomize_questions:
                import random
                random.shuffle(opts)
            sanitized_questions.append({
                'id': str(q.id),
                'question_text': q.question_text,
                'question_type': q.question_type,
                'points': q.points,
                'options': [{'id': str(opt.id), 'text': opt.option_text} for opt in opts]
            })

        return render(request, 'assessments/quiz_take.html', {
            'quiz': quiz,
            'attempt': attempt,
            'questions': sanitized_questions,
            'time_limit_seconds': quiz.time_limit_minutes * 60,
        })


class QuizSubmitView(LoginRequiredMixin, View):
    """
    Accepts student answers, grades them server-side, and records the result.
    """
    def post(self, request, pk):
        attempt = get_object_or_404(QuizAttempt, pk=pk, student=request.user)
        if attempt.is_completed:
            messages.info(request, "This attempt has already been submitted and finalized.")
            return redirect('assessments:quiz-result', pk=attempt.pk)

        raw_answers = {}
        for key in request.POST:
            if key.startswith('question_'):
                q_id = key.replace('question_', '')
                raw_answers[q_id] = request.POST.getlist(key)

        attempt = QuizGradingService.grade_attempt(attempt, raw_answers)
        messages.success(request, f"Quiz submitted! You scored {attempt.percentage}%.")
        return redirect('assessments:quiz-result', pk=attempt.pk)


class QuizResultView(LoginRequiredMixin, DetailView):
    model = QuizAttempt
    template_name = 'assessments/quiz_result.html'
    context_object_name = 'attempt'

    def get_queryset(self):
        # Instructors or the student owner can view results
        user = self.request.user
        if user.is_instructor or user.is_academy_admin:
            return QuizAttempt.objects.all()
        return QuizAttempt.objects.filter(student=user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        attempt = self.object
        ctx['answers'] = attempt.answers.select_related('question').all()
        return ctx


# ==============================================================================
# ASSIGNMENT VIEWS
# ==============================================================================

class AssignmentDetailView(LoginRequiredMixin, DetailView):
    model = Assignment
    template_name = 'assessments/assignment_detail.html'
    context_object_name = 'assignment'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        assignment = self.object
        student = self.request.user
        submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()
        ctx['submission'] = submission
        ctx['is_past_due'] = assignment.due_date and timezone.now() > assignment.due_date
        return ctx


class AssignmentSubmitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk)
        student = request.user

        # Ensure student enrollment for progress tracking
        if not (student.is_instructor or student.is_academy_admin or student.is_superuser):
            Enrollment.objects.get_or_create(
                student=student,
                course=assignment.course,
                defaults={'status': EnrollmentStatus.ACTIVE}
            )

        # Check if closed
        if assignment.status == 'CLOSED':
            messages.error(request, "This assignment is closed for submissions.")
            return redirect('assessments:assignment-detail', pk=assignment.pk)

        submitted_file = request.FILES.get('submitted_file')
        submission_text = request.POST.get('submission_text', '').strip()

        if not submitted_file and not submission_text:
            messages.error(request, "Please provide a file upload or text submission.")
            return redirect('assessments:assignment-detail', pk=assignment.pk)

        # Validate file type and security if file provided
        if submitted_file:
            from apps.core.validators import validate_resource_file
            from django.core.exceptions import ValidationError
            try:
                validate_resource_file(submitted_file)
            except ValidationError as ve:
                messages.error(request, str(ve))
                return redirect('assessments:assignment-detail', pk=assignment.pk)

            if assignment.allowed_file_types:
                ext = submitted_file.name.split('.')[-1].lower()
                if ext not in [t.lower().replace('.', '') for t in assignment.allowed_file_types]:
                    messages.error(request, f"File extension .{ext} is not allowed. Allowed types: {', '.join(assignment.allowed_file_types)}")
                    return redirect('assessments:assignment-detail', pk=assignment.pk)

            # Enforce max file size
            if submitted_file.size > assignment.max_file_size_mb * 1024 * 1024:
                messages.error(request, f"File exceeds maximum allowed size of {assignment.max_file_size_mb} MB.")
                return redirect('assessments:assignment-detail', pk=assignment.pk)

        submission, created = AssignmentSubmission.objects.get_or_create(
            assignment=assignment,
            student=student,
            defaults={
                'submitted_file': submitted_file,
                'submission_text': submission_text,
                'status': SubmissionStatus.SUBMITTED,
                'version': 1,
            }
        )

        if not created:
            # Resubmission
            if submitted_file:
                submission.submitted_file = submitted_file
            submission.submission_text = submission_text
            submission.version += 1
            submission.status = SubmissionStatus.RESUBMITTED
            submission.save()

        # Audit log
        from apps.core.audit import log_audit_event
        log_audit_event(
            user=student,
            action="ASSIGNMENT_SUBMITTED",
            object_type="AssignmentSubmission",
            object_id=str(submission.id),
            metadata={'assignment_id': str(assignment.id), 'version': submission.version}
        )

        # Award badge if first assignment
        try:
            from apps.achievements.services import AchievementEvaluationService
            AchievementEvaluationService.evaluate_student(
                student=student,
                event="ASSIGNMENT_SUBMITTED",
                context={'submission': submission}
            )
        except Exception as e:
            logger.error(f"Achievement check failed: {e}")

        messages.success(request, f"Assignment '{assignment.title}' submitted successfully!")
        return redirect('assessments:assignment-detail', pk=assignment.pk)


class InstructorGradingQueueView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AssignmentSubmission
    template_name = 'assessments/instructor_grading_queue.html'
    context_object_name = 'submissions'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_instructor or self.request.user.is_academy_admin

    def get_queryset(self):
        qs = AssignmentSubmission.objects.select_related('assignment', 'student', 'assignment__course').all()
        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        course_filter = self.request.GET.get('course')
        if course_filter:
            qs = qs.filter(assignment__course_id=course_filter)
        return qs.order_by('-submitted_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['courses'] = Course.objects.filter(is_active=True)
        ctx['pending_count'] = AssignmentSubmission.objects.filter(status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.RESUBMITTED]).count()
        return ctx


class InstructorGradeSubmissionView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_instructor or self.request.user.is_academy_admin

    def get(self, request, pk):
        submission = get_object_or_404(
            AssignmentSubmission.objects.select_related('assignment', 'student', 'assignment__course'),
            pk=pk
        )
        return render(request, 'assessments/instructor_grade_submission.html', {
            'submission': submission,
            'assignment': submission.assignment,
            'latest_feedback': submission.latest_feedback,
        })

    def post(self, request, pk):
        submission = get_object_or_404(AssignmentSubmission, pk=pk)
        score_str = request.POST.get('score', '').strip()
        feedback_text = request.POST.get('feedback', '').strip()

        try:
            score = Decimal(score_str)
        except Exception:
            messages.error(request, "Please enter a valid numeric score.")
            return redirect('assessments:instructor-grade-submission', pk=pk)

        if score < 0 or score > submission.assignment.max_score:
            messages.error(request, f"Score must be between 0 and {submission.assignment.max_score}.")
            return redirect('assessments:instructor-grade-submission', pk=pk)

        AssignmentFeedback.objects.create(
            submission=submission,
            instructor=request.user,
            score=score,
            feedback=feedback_text
        )

        submission.status = SubmissionStatus.GRADED
        submission.save(update_fields=['status', 'updated_at'])

        # Notify student
        from apps.notifications.services import NotificationService
        NotificationService.create_notification(
            recipient=submission.student,
            title=f"Assignment Graded: {submission.assignment.title}",
            message=f"Your assignment has been graded: {score}/{submission.assignment.max_score}. Feedback: {feedback_text[:120]}...",
            notification_type="ASSIGNMENT"
        )

        # Audit log
        from apps.core.audit import log_audit_event
        log_audit_event(
            user=request.user,
            action="ASSIGNMENT_GRADED",
            object_type="AssignmentSubmission",
            object_id=str(submission.id),
            metadata={'score': str(score), 'student': submission.student.email}
        )

        # Check course completion
        try:
            from apps.courses.completion_service import CourseCompletionService
            CourseCompletionService.check_and_complete_course(submission.student, submission.assignment.course)
        except Exception as e:
            logger.error(f"Course completion check failed: {e}")

        messages.success(request, f"Graded submission for {submission.student.get_full_name()}!")
        return redirect('assessments:grading-queue')


# ==============================================================================
# EXAMINATION VIEWS
# ==============================================================================

class ExamPortalView(LoginRequiredMixin, ListView):
    model = Exam
    template_name = 'assessments/exam_portal.html'
    context_object_name = 'exams'

    def get_queryset(self):
        user = self.request.user
        enrolled_courses = Enrollment.objects.filter(student=user, is_active=True).values_list('course_id', flat=True)
        return Exam.objects.filter(course_id__in=enrolled_courses, is_published=True).select_related('course')


class ExamDetailView(LoginRequiredMixin, DetailView):
    model = Exam
    template_name = 'assessments/exam_detail.html'
    context_object_name = 'exam'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        exam = self.object
        student = self.request.user
        attempts = ExamAttempt.objects.filter(exam=exam, student=student)
        ctx['attempts'] = attempts
        ctx['attempts_count'] = attempts.count()
        ctx['can_start'] = attempts.count() < exam.max_attempts
        ctx['best_attempt'] = attempts.order_by('-score').first()
        return ctx


class ExamTakeView(LoginRequiredMixin, View):
    """
    Initiates or resumes a strictly timed exam attempt.
    Timer is anchored to database `expires_at`.
    """
    def get(self, request, pk):
        exam = get_object_or_404(Exam, pk=pk, is_published=True)
        student = request.user

        # Ensure student enrollment for progress tracking
        if not (student.is_instructor or student.is_academy_admin or student.is_superuser):
            Enrollment.objects.get_or_create(
                student=student,
                course=exam.course,
                defaults={'status': EnrollmentStatus.ACTIVE}
            )

        # Look for existing in-progress attempt
        attempt = ExamAttempt.objects.filter(exam=exam, student=student, is_completed=False).first()
        if not attempt:
            try:
                attempt = ExamTimerService.start_exam_attempt(student, exam)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('assessments:exam-detail', pk=exam.pk)

        # Check if already expired
        if attempt.is_expired:
            attempt.is_completed = True
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['is_completed', 'submitted_at'])
            messages.error(request, "Your exam time limit has expired.")
            return redirect('assessments:exam-result', pk=attempt.pk)

        remaining_seconds = max(0, int((attempt.expires_at - timezone.now()).total_seconds()))

        questions = list(exam.questions.filter(is_active=True).prefetch_related('options'))
        if exam.randomize_questions:
            import random
            random.shuffle(questions)

        sanitized_questions = []
        for q in questions:
            opts = list(q.options.filter(is_active=True))
            if exam.randomize_questions:
                import random
                random.shuffle(opts)
            sanitized_questions.append({
                'id': str(q.id),
                'question_text': q.question_text,
                'question_type': q.question_type,
                'points': q.points,
                'options': [{'id': str(opt.id), 'text': opt.option_text} for opt in opts]
            })

        return render(request, 'assessments/exam_take.html', {
            'exam': exam,
            'attempt': attempt,
            'questions': sanitized_questions,
            'remaining_seconds': remaining_seconds,
            'expires_at_iso': attempt.expires_at.isoformat(),
        })


class ExamSubmitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, pk=pk, student=request.user)
        if attempt.is_completed:
            messages.info(request, "This exam has already been finalized.")
            return redirect('assessments:exam-result', pk=attempt.pk)

        raw_answers = {}
        for key in request.POST:
            if key.startswith('question_'):
                q_id = key.replace('question_', '')
                raw_answers[q_id] = request.POST.getlist(key)

        try:
            attempt = ExamTimerService.submit_exam_attempt(attempt, raw_answers)
            messages.success(request, f"Exam finalized! Your score: {attempt.percentage}%.")
        except ValueError as ex:
            messages.error(request, str(ex))

        return redirect('assessments:exam-result', pk=attempt.pk)


class ExamResultView(LoginRequiredMixin, DetailView):
    model = ExamAttempt
    template_name = 'assessments/exam_result.html'
    context_object_name = 'attempt'

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor or user.is_academy_admin:
            return ExamAttempt.objects.all()
        return ExamAttempt.objects.filter(student=user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        attempt = self.object
        ctx['answers'] = attempt.answers.select_related('question').all()
        return ctx


# ==============================================================================
# GRADEBOOK VIEWS
# ==============================================================================

class StudentGradebookView(LoginRequiredMixin, View):
    """
    Renders comprehensive gradebook for the logged-in student across all their courses.
    """
    def get(self, request):
        student = request.user
        enrollments = Enrollment.objects.filter(student=student, is_active=True).select_related('course')
        grade_records = []
        for enr in enrollments:
            grades = GradeCalculationService.calculate_student_grade(student, enr.course)
            grade_records.append({
                'course': enr.course,
                'enrollment': enr,
                'final_grade': grades['final_grade'],
                'letter_grade': grades['letter_grade'],
                'breakdown': grades['breakdown'],
            })

        return render(request, 'assessments/student_gradebook.html', {
            'grade_records': grade_records,
        })


class InstructorCourseGradebookView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Renders course gradebook matrix for instructors.
    """
    def test_func(self):
        return self.request.user.is_instructor or self.request.user.is_academy_admin

    def get(self, request, course_slug):
        course = get_object_or_404(Course, slug=course_slug)
        enrollments = Enrollment.objects.filter(course=course, is_active=True).select_related('student')
        weight_config, _ = AssessmentWeight.objects.get_or_create(course=course)

        student_matrix = []
        for enr in enrollments:
            grades = GradeCalculationService.calculate_student_grade(enr.student, course)
            student_matrix.append({
                'student': enr.student,
                'enrollment': enr,
                'final_grade': grades['final_grade'],
                'letter_grade': grades['letter_grade'],
                'breakdown': grades['breakdown'],
            })

        return render(request, 'assessments/instructor_gradebook.html', {
            'course': course,
            'weight_config': weight_config,
            'student_matrix': student_matrix,
        })

