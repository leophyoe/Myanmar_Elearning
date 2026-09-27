import logging
from decimal import Decimal
from django.utils import timezone
from .models import (
    Quiz, QuizAttempt, QuizAnswer, QuestionType,
    Exam, ExamAttempt, ExamAnswer, AssessmentWeight
)

logger = logging.getLogger(__name__)


class QuizGradingService:
    """
    Automated zero-trust server-side grading engine for quizzes.
    Validates answers strictly on the server; client never receives the answer key.
    """

    @classmethod
    def can_attempt(cls, quiz: Quiz, student) -> tuple:
        """Returns tuple of (can_attempt: bool, attempts_remaining: int)."""
        attempts_count = QuizAttempt.objects.filter(quiz=quiz, student=student).count()
        remaining = max(0, quiz.max_attempts - attempts_count)
        return remaining > 0, remaining

    @classmethod
    def grade_attempt(cls, attempt: QuizAttempt, raw_answers: dict):
        """
        raw_answers: dict mapping question_id (str) to list of selected option_ids (list of str) or text
        """
        quiz = attempt.quiz
        questions = quiz.questions.filter(is_active=True).prefetch_related('options')

        total_points_possible = Decimal('0.00')
        total_points_earned = Decimal('0.00')

        for q in questions:
            q_id_str = str(q.id)
            points = q.points
            total_points_possible += points
            selected_opts = raw_answers.get(q_id_str, [])
            if not isinstance(selected_opts, list):
                selected_opts = [selected_opts] if selected_opts else []

            selected_opts_str = [str(x) for x in selected_opts]
            correct_opts_ids = [str(opt.id) for opt in q.options.filter(is_correct=True)]

            is_correct = False
            points_awarded = Decimal('0.00')

            if q.question_type in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE]:
                if len(selected_opts_str) == 1 and selected_opts_str[0] in correct_opts_ids:
                    is_correct = True
                    points_awarded = points
            elif q.question_type == QuestionType.MULTIPLE_SELECT:
                # Must match all correct options without selecting incorrect ones
                if set(selected_opts_str) == set(correct_opts_ids) and len(correct_opts_ids) > 0:
                    is_correct = True
                    points_awarded = points

            total_points_earned += points_awarded

            # Save per-question answer
            QuizAnswer.objects.update_or_create(
                attempt=attempt,
                question=q,
                defaults={
                    'selected_options': selected_opts_str,
                    'is_correct': is_correct,
                    'points_awarded': points_awarded,
                }
            )

        percentage = Decimal('0.00')
        if total_points_possible > 0:
            percentage = Decimal((total_points_earned / total_points_possible) * 100).quantize(Decimal('0.01'))

        passed = (percentage >= Decimal(str(quiz.passing_score)))

        attempt.score = total_points_earned
        attempt.percentage = percentage
        attempt.passed = passed
        attempt.is_completed = True
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['score', 'percentage', 'passed', 'is_completed', 'submitted_at', 'updated_at'])

        # Log audit entry
        from apps.core.audit import log_audit_event
        log_audit_event(
            user=attempt.student,
            action="QUIZ_SUBMITTED",
            object_type="QuizAttempt",
            object_id=str(attempt.id),
            metadata={'quiz_id': str(quiz.id), 'score': str(total_points_earned), 'passed': passed}
        )

        # Notify student
        from apps.notifications.services import NotificationService
        status_text = "Passed" if passed else "Did not pass"
        NotificationService.create_notification(
            recipient=attempt.student,
            title=f"Quiz Graded: {quiz.title}",
            message=f"You scored {percentage}% ({total_points_earned}/{total_points_possible}). Status: {status_text}.",
            notification_type="QUIZ"
        )

        # Evaluate gamification achievements
        try:
            from apps.achievements.services import AchievementEvaluationService
            AchievementEvaluationService.evaluate_student(
                student=attempt.student,
                event="QUIZ_SUBMITTED",
                context={'attempt': attempt, 'percentage': percentage, 'passed': passed}
            )
        except Exception as e:
            logger.error(f"Achievement check failed: {e}")

        # Check course completion
        try:
            from apps.courses.completion_service import CourseCompletionService
            CourseCompletionService.check_and_complete_course(attempt.student, quiz.course)
        except Exception as e:
            logger.error(f"Course completion check failed: {e}")

        return attempt


class ExamTimerService:
    """
    Server-side authoritative timer service.
    Enforces strict exam duration based on database timestamps, impervious to client clock tampering.
    """

    @classmethod
    def start_attempt(cls, student, exam: Exam) -> ExamAttempt:
        return cls.start_exam_attempt(student, exam)

    @classmethod
    def check_expired(cls, attempt: ExamAttempt) -> bool:
        return attempt.is_expired

    @classmethod
    def start_exam_attempt(cls, student, exam: Exam) -> ExamAttempt:
        """
        Starts a new timed attempt if student has attempts remaining.
        Calculates authoritative expires_at timestamp.
        """
        existing_attempts_count = ExamAttempt.objects.filter(student=student, exam=exam).count()
        if existing_attempts_count >= exam.max_attempts:
            raise ValueError(f"You have reached the maximum allowed attempts ({exam.max_attempts}) for this exam.")

        now = timezone.now()
        expires_at = now + timezone.timedelta(minutes=exam.duration_minutes)

        attempt = ExamAttempt.objects.create(
            student=student,
            exam=exam,
            attempt_number=existing_attempts_count + 1,
            started_at=now,
            expires_at=expires_at,
            is_completed=False
        )

        from apps.core.audit import log_audit_event
        log_audit_event(
            user=student,
            action="EXAM_STARTED",
            object_type="ExamAttempt",
            object_id=str(attempt.id),
            metadata={'exam_id': str(exam.id), 'expires_at': expires_at.isoformat()}
        )

        return attempt

    @classmethod
    def submit_exam_attempt(cls, attempt: ExamAttempt, raw_answers: dict):
        """
        Submits and grades exam attempt with strict server-side deadline verification.
        """
        if attempt.is_completed:
            return attempt

        # Validate deadline
        if attempt.is_expired:
            attempt.is_completed = True
            attempt.submitted_at = timezone.now()
            attempt.passed = False
            attempt.save(update_fields=['is_completed', 'submitted_at', 'passed', 'updated_at'])
            raise ValueError("Exam time limit expired. Submission was rejected by the server.")

        exam = attempt.exam
        questions = exam.questions.filter(is_active=True).prefetch_related('options')

        total_points_possible = Decimal('0.00')
        total_points_earned = Decimal('0.00')

        for q in questions:
            q_id_str = str(q.id)
            points = q.points
            total_points_possible += points
            selected_opts = raw_answers.get(q_id_str, [])
            if not isinstance(selected_opts, list):
                selected_opts = [selected_opts] if selected_opts else []

            selected_opts_str = [str(x) for x in selected_opts]
            correct_opts_ids = [str(opt.id) for opt in q.options.filter(is_correct=True)]

            is_correct = False
            points_awarded = Decimal('0.00')

            if q.question_type in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE]:
                if len(selected_opts_str) == 1 and selected_opts_str[0] in correct_opts_ids:
                    is_correct = True
                    points_awarded = points
            elif q.question_type == QuestionType.MULTIPLE_SELECT:
                if set(selected_opts_str) == set(correct_opts_ids) and len(correct_opts_ids) > 0:
                    is_correct = True
                    points_awarded = points

            total_points_earned += points_awarded

            ExamAnswer.objects.update_or_create(
                attempt=attempt,
                question=q,
                defaults={
                    'selected_options': selected_opts_str,
                    'is_correct': is_correct,
                    'points_awarded': points_awarded,
                }
            )

        percentage = Decimal('0.00')
        if total_points_possible > 0:
            percentage = Decimal((total_points_earned / total_points_possible) * 100).quantize(Decimal('0.01'))

        passed = (percentage >= Decimal(str(exam.passing_score)))

        attempt.score = total_points_earned
        attempt.percentage = percentage
        attempt.passed = passed
        attempt.is_completed = True
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['score', 'percentage', 'passed', 'is_completed', 'submitted_at', 'updated_at'])

        # Audit log
        from apps.core.audit import log_audit_event
        log_audit_event(
            user=attempt.student,
            action="EXAM_SUBMITTED",
            object_type="ExamAttempt",
            object_id=str(attempt.id),
            metadata={'exam_id': str(exam.id), 'score': str(total_points_earned), 'passed': passed}
        )

        # Notify student
        from apps.notifications.services import NotificationService
        status_text = "Passed" if passed else "Failed"
        NotificationService.create_notification(
            recipient=attempt.student,
            title=f"Exam Result: {exam.title}",
            message=f"Your exam has been finalized. Score: {percentage}%. Status: {status_text}.",
            notification_type="EXAM"
        )

        # Trigger Course Completion
        try:
            from apps.courses.completion_service import CourseCompletionService
            CourseCompletionService.check_and_complete_course(attempt.student, exam.course)
        except Exception as e:
            logger.error(f"Course completion check failed: {e}")

        return attempt


class GradeCalculationService:
    """
    Computes weighted student gradebook calculations according to institutional rubric:
    Assignments (10%), Quizzes (10%), Labs (25%), Module Exams (20%), Practical Exam (15%), Final Project (20%)
    """

    @classmethod
    def calculate_student_grade(cls, student, course):
        # 1. Get or create weight config
        weight_config, _ = AssessmentWeight.objects.get_or_create(course=course)

        # 2. Assignment Average: evaluated across all published assignments
        from .models import Assignment, AssignmentSubmission, SubmissionStatus
        published_assignments = Assignment.objects.filter(course=course, status='PUBLISHED')
        total_assignments = published_assignments.count()
        if total_assignments > 0:
            assignment_scores = []
            for a in published_assignments:
                sub = AssignmentSubmission.objects.filter(
                    assignment=a,
                    student=student,
                    status=SubmissionStatus.GRADED
                ).prefetch_related('feedbacks').first()
                if sub and sub.latest_feedback and a.max_score > 0:
                    pct = (sub.latest_feedback.score / a.max_score) * 100
                    assignment_scores.append(min(100.0, max(0.0, float(pct))))
                else:
                    # Unsubmitted or ungraded assignments count as 0.0 towards category average
                    assignment_scores.append(0.0)
            avg_assignment = sum(assignment_scores) / total_assignments
        else:
            avg_assignment = 0.0

        # 3. Quiz Average: evaluated across all published quizzes (best completed attempt per quiz)
        published_quizzes = Quiz.objects.filter(course=course, is_published=True)
        total_quizzes = published_quizzes.count()
        if total_quizzes > 0:
            quiz_scores = []
            for q in published_quizzes:
                attempts = q.attempts.filter(student=student, is_completed=True)
                if attempts.exists():
                    best_pct = max([float(att.percentage) for att in attempts])
                    quiz_scores.append(min(100.0, max(0.0, best_pct)))
                else:
                    quiz_scores.append(0.0)
            avg_quiz = sum(quiz_scores) / total_quizzes
        else:
            avg_quiz = 0.0

        # 4. Module Exams Average (best completed attempt per published module/midterm exam)
        published_module_exams = Exam.objects.filter(
            course=course,
            exam_type__in=['MODULE_EXAM', 'MIDTERM'],
            is_published=True
        )
        total_module_exams = published_module_exams.count()
        if total_module_exams > 0:
            exam_scores = []
            for e in published_module_exams:
                attempts = e.attempts.filter(student=student, is_completed=True)
                if attempts.exists():
                    best_pct = max([float(att.percentage) for att in attempts])
                    exam_scores.append(min(100.0, max(0.0, best_pct)))
                else:
                    exam_scores.append(0.0)
            avg_exam = sum(exam_scores) / total_module_exams
        else:
            avg_exam = 0.0

        # 5. Practical Exam (best completed attempt per published practical exam)
        published_practical_exams = Exam.objects.filter(
            course=course,
            exam_type='PRACTICAL',
            is_published=True
        )
        total_practical = published_practical_exams.count()
        if total_practical > 0:
            practical_scores = []
            for e in published_practical_exams:
                attempts = e.attempts.filter(student=student, is_completed=True)
                if attempts.exists():
                    best_pct = max([float(att.percentage) for att in attempts])
                    practical_scores.append(min(100.0, max(0.0, best_pct)))
                else:
                    practical_scores.append(0.0)
            avg_practical = sum(practical_scores) / total_practical
        else:
            avg_practical = 0.0

        # 6. Final Project / Final Exam
        from .models import FinalProject, ProjectSubmission, ProjectStatus
        final_project = FinalProject.objects.filter(course=course, is_published=True).first()
        if final_project:
            submission = ProjectSubmission.objects.filter(
                project=final_project,
                student=student,
                status=ProjectStatus.GRADED
            ).first()
            if submission and final_project.max_score > 0:
                proj_score = float(submission.score)
                if submission.presentation_score is not None:
                    total_proj_score = (proj_score + float(submission.presentation_score)) / 2.0
                else:
                    total_proj_score = proj_score
                avg_final = min(100.0, max(0.0, (total_proj_score / float(final_project.max_score)) * 100.0))
            else:
                avg_final = 0.0
        else:
            published_final_exams = Exam.objects.filter(
                course=course,
                exam_type='FINAL',
                is_published=True
            )
            total_final = published_final_exams.count()
            if total_final > 0:
                final_scores = []
                for e in published_final_exams:
                    attempts = e.attempts.filter(student=student, is_completed=True)
                    if attempts.exists():
                        best_pct = max([float(att.percentage) for att in attempts])
                        final_scores.append(min(100.0, max(0.0, best_pct)))
                    else:
                        final_scores.append(0.0)
                avg_final = sum(final_scores) / total_final
            else:
                avg_final = 0.0

        # 7. Labs: evaluated across all published practical lessons in the course
        from apps.progress.models import LessonProgress
        from apps.courses.models import Lesson, LessonType
        total_labs = Lesson.objects.filter(
            module__course=course,
            module__is_published=True,
            is_published=True,
            lesson_type=LessonType.PRACTICAL
        ).count()
        if total_labs > 0:
            completed_labs = LessonProgress.objects.filter(
                student=student,
                lesson__module__course=course,
                lesson__lesson_type=LessonType.PRACTICAL,
                completed=True
            ).count()
            avg_lab = (completed_labs / total_labs) * 100.0
        else:
            avg_lab = 100.0

        # Weighted calculation
        w_assign = float(weight_config.assignments_weight) / 100.0
        w_quiz = float(weight_config.quizzes_weight) / 100.0
        w_lab = float(weight_config.labs_weight) / 100.0
        w_exam = float(weight_config.module_exams_weight) / 100.0
        w_pract = float(weight_config.practical_exam_weight) / 100.0
        w_proj = float(weight_config.final_project_weight) / 100.0

        final_weighted_grade = (
            (avg_assignment * w_assign) +
            (avg_quiz * w_quiz) +
            (avg_lab * w_lab) +
            (avg_exam * w_exam) +
            (avg_practical * w_pract) +
            (avg_final * w_proj)
        )

        final_weighted_grade = round(min(100.0, max(0.0, final_weighted_grade)), 2)

        # Letter grade lookup
        if final_weighted_grade >= 90:
            letter = 'A+'
        elif final_weighted_grade >= 85:
            letter = 'A'
        elif final_weighted_grade >= 80:
            letter = 'B+'
        elif final_weighted_grade >= 75:
            letter = 'B'
        elif final_weighted_grade >= 70:
            letter = 'C+'
        elif final_weighted_grade >= 60:
            letter = 'C'
        else:
            letter = 'F'

        passed = (final_weighted_grade >= 70.0)
        passing_threshold = float(getattr(course, 'passing_percentage', Decimal('70.00')))
        passed = (final_weighted_grade >= passing_threshold)
        component_scores = {
            'assignments': round(avg_assignment, 2),
            'quizzes': round(avg_quiz, 2),
            'labs': round(avg_lab, 2),
            'module_exams': round(avg_exam, 2),
            'practical_exam': round(avg_practical, 2),
            'final_project': round(avg_final, 2),
        }
        component_weights = {
            'assignments': float(weight_config.assignments_weight),
            'quizzes': float(weight_config.quizzes_weight),
            'labs': float(weight_config.labs_weight),
            'module_exams': float(weight_config.module_exams_weight),
            'practical_exam': float(weight_config.practical_exam_weight),
            'final_project': float(weight_config.final_project_weight),
        }

        return {
            'final_grade': final_weighted_grade,
            'weighted_percentage': final_weighted_grade,
            'letter_grade': letter,
            'final_letter_grade': letter,
            'passed': passed,
            'passing_percentage': passing_threshold,
            'component_scores': component_scores,
            'component_weights': component_weights,
            'breakdown': {
                'assignments': {'average': round(avg_assignment, 2), 'weight': float(weight_config.assignments_weight)},
                'quizzes': {'average': round(avg_quiz, 2), 'weight': float(weight_config.quizzes_weight)},
                'labs': {'average': round(avg_lab, 2), 'weight': float(weight_config.labs_weight)},
                'module_exams': {'average': round(avg_exam, 2), 'weight': float(weight_config.module_exams_weight)},
                'practical_exam': {'average': round(avg_practical, 2), 'weight': float(weight_config.practical_exam_weight)},
                'final_project': {'average': round(avg_final, 2), 'weight': float(weight_config.final_project_weight)},
            }
        }

