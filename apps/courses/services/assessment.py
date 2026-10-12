"""
Assessment evaluation and grading engine for Myanmar E-Learning (MEL).
Supports multiple question types across general academic and technical categories:
- Multiple Choice (Single select)
- Multiple Select (Multi-choice)
- True / False
- Fill in the Blank
- Short Answer
- Coding Problems, Hands-on Lab Exercises, File Submissions, Project Evaluations
"""
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from apps.courses.models import Course, Module, Lesson, Quiz, Question, Choice, QuizAttempt, UserProgress
from apps.courses.services.access import can_access_course, can_take_course_exam


def evaluate_question_answer(question: Question, raw_answer) -> tuple[bool, int, str]:
    """
    Evaluates a student's answer for a single question.
    Returns:
        (is_correct: bool, points_earned: int, explanation: str)
    """
    q_type = question.question_type
    points = question.points

    if raw_answer is None or raw_answer == '' or raw_answer == []:
        return False, 0, "No answer provided."

    # 1. Multiple Choice & True/False
    if q_type in (Question.QuestionType.MULTIPLE_CHOICE, Question.QuestionType.TRUE_FALSE):
        choice_id = str(raw_answer).strip()
        choice = question.choices.filter(id=choice_id).first()
        if choice and choice.is_correct:
            return True, points, question.explanation or "Correct!"
        return False, 0, question.explanation or "Incorrect choice."

    # 2. Multiple Select
    elif q_type == Question.QuestionType.MULTIPLE_SELECT:
        if isinstance(raw_answer, (list, tuple, set)):
            selected_ids = {str(cid).strip() for cid in raw_answer if cid}
        else:
            selected_ids = {str(raw_answer).strip()}

        correct_ids = {str(c.id) for c in question.choices.filter(is_correct=True)}
        if not correct_ids:
            return False, 0, "Question has no designated correct answers."

        if selected_ids == correct_ids:
            return True, points, question.explanation or "All correct options selected!"
        return False, 0, question.explanation or "Incorrect option combination."

    # 3. Fill in the Blank
    elif q_type == Question.QuestionType.FILL_IN_BLANK:
        user_text = str(raw_answer).strip().lower()
        accepted_variants = [
            v.strip().lower()
            for v in (question.correct_text_answer or '').split('|')
            if v.strip()
        ]
        # Also check any correct Choices if authored
        choice_variants = [c.text.strip().lower() for c in question.choices.filter(is_correct=True)]
        all_accepted = set(accepted_variants + choice_variants)

        if user_text and user_text in all_accepted:
            return True, points, question.explanation or "Correct answer!"
        return False, 0, question.explanation or f"Incorrect. Accepted answer: {question.correct_text_answer or 'specified criteria'}"

    # 4. Short Answer
    elif q_type == Question.QuestionType.SHORT_ANSWER:
        user_text = str(raw_answer).strip().lower()
        accepted_variants = [
            v.strip().lower()
            for v in (question.correct_text_answer or '').split('|')
            if v.strip()
        ]
        if accepted_variants:
            if user_text in accepted_variants or any(var in user_text for var in accepted_variants):
                return True, points, question.explanation or "Satisfactory answer!"
            return False, 0, question.explanation or "Answer did not match target criteria."
        # If open-ended without automatic text match, grant points provisionally or hold for review
        return True, points, "Recorded for evaluation."

    # 5. Coding Problem / Practical Lab / File Submission / Project
    elif q_type in (
        Question.QuestionType.CODING,
        Question.QuestionType.PRACTICAL_LAB,
        Question.QuestionType.FILE_SUBMISSION,
        Question.QuestionType.PROJECT_EVALUATION,
    ):
        if question.correct_text_answer:
            user_text = str(raw_answer or '').strip()
            patterns = [p.strip() for p in question.correct_text_answer.split('|') if p.strip()]
            if all(p in user_text for p in patterns):
                return True, points, question.explanation or "Coding solution passed test criteria."
            return False, 0, question.explanation or "Coding solution did not meet the required pattern."
        # Automatically accepts submission for grading queue
        return True, points, "Submission recorded for instructor evaluation."

    # Default fallback
    return False, 0, "Unknown question type."


def check_assessment_attempt_eligibility(user, assessment: Quiz) -> tuple[bool, str]:
    """
    Validates whether a student is authorized to begin or submit an attempt.
    Supports both standalone exams and course-embedded quizzes.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Authentication required to access assessment."

    if getattr(user, 'is_admin', False) or user == getattr(assessment, 'owner', None) or user == getattr(assessment, 'assigned_instructor', None):
        return True, ""

    if assessment.is_standalone:
        from apps.billing.models import has_paid_standalone_exam
        if not assessment.is_free and not has_paid_standalone_exam(user, assessment):
            return False, "This exam requires an active pass or purchase."
    else:
        course = assessment.course or (assessment.lesson.module.course if assessment.lesson else None)
        if course and not can_access_course(user, course):
            return False, "Course enrollment and active entitlement required."

        if assessment.is_exam and course:
            can_exam, reason = can_take_course_exam(user, course)
            if not can_exam:
                return False, reason

    # Check date availability
    now = timezone.now()
    if assessment.available_from and now < assessment.available_from:
        return False, f"Assessment not open yet (available from {assessment.available_from.strftime('%b %d, %Y')})."
    if assessment.available_until and now > assessment.available_until:
        return False, f"Assessment deadline expired on {assessment.available_until.strftime('%b %d, %Y')}."

    if assessment.status != Quiz.Status.PUBLISHED:
        return False, "Assessment is not currently published."

    # Check attempt limit
    if assessment.max_attempts > 0:
        prior_attempts = assessment.attempts.filter(student=user).count()
        if prior_attempts >= assessment.max_attempts:
            return False, f"Maximum attempt limit ({assessment.max_attempts}) reached for this assessment."

    return True, ""


def serialize_exam_for_student(assessment: Quiz) -> dict:
    """
    Serializes exam structure and questions for the interactive exam taker UI.
    CRITICAL: Never leaks `is_correct`, `correct_text_answer`, `rubric_criteria`,
    or `explanation` to the client DOM/API.
    """
    import random
    questions_qs = assessment.questions.all().prefetch_related('choices')
    questions_list = list(questions_qs)
    if assessment.randomize_questions:
        random.shuffle(questions_list)

    serialized_questions = []
    for idx, q in enumerate(questions_list, start=1):
        choices = list(q.choices.all())
        if assessment.randomize_choices:
            random.shuffle(choices)

        serialized_questions.append({
            'id': str(q.id),
            'index': idx,
            'prompt': q.prompt,
            'question_type': q.question_type,
            'points': q.points,
            'choices': [
                {
                    'id': str(c.id),
                    'text': c.text,
                }
                for c in choices
            ],
        })

    return {
        'id': str(assessment.id),
        'title': assessment.title,
        'description': assessment.description,
        'quiz_type': assessment.quiz_type,
        'time_limit_minutes': assessment.time_limit_minutes,
        'passing_percentage': assessment.passing_percentage,
        'total_questions': len(serialized_questions),
        'questions': serialized_questions,
        'is_standalone': assessment.is_standalone,
        'requires_manual_grading': assessment.requires_manual_grading,
    }


def grade_assessment_attempt(assessment: Quiz, user, submitted_answers: dict, time_taken_seconds: int = 0) -> tuple[QuizAttempt, str]:
    """
    Grades an assessment submission, records pedagogical audit attempt,
    updates lesson progress and triggers certificate issuance / course completion checks.

    submitted_answers: dict of responses, e.g.:
      {'question_1': 'choice_4', 'question_2': ['choice_5', 'choice_6'], 'question_3': 'DNS'}
    """
    is_eligible, reason = check_assessment_attempt_eligibility(user, assessment)
    if not is_eligible:
        raise PermissionDenied(reason)

    questions = assessment.questions.all().prefetch_related('choices')
    total_possible_points = sum(q.points for q in questions)
    if total_possible_points == 0:
        total_possible_points = max(questions.count() * 10, 1)

    total_earned_points = 0
    detailed_answers = {}
    has_pending_manual_question = False

    for question in questions:
        q_key = f"question_{question.id}"
        alt_key = str(question.id)

        raw_val = None
        if hasattr(submitted_answers, 'getlist'):
            val_list = submitted_answers.getlist(q_key) or submitted_answers.getlist(alt_key)
            if len(val_list) > 1 or question.question_type == Question.QuestionType.MULTIPLE_SELECT:
                raw_val = val_list
            elif len(val_list) == 1:
                raw_val = val_list[0]
        else:
            raw_val = submitted_answers.get(q_key)
            if raw_val is None:
                raw_val = submitted_answers.get(alt_key)

        is_corr, pts, feedback = evaluate_question_answer(question, raw_val)

        # Questions requiring manual evaluation
        if question.question_type in (
            Question.QuestionType.SHORT_ANSWER,
            Question.QuestionType.CODING,
            Question.QuestionType.PRACTICAL_LAB,
            Question.QuestionType.FILE_SUBMISSION,
            Question.QuestionType.PROJECT_EVALUATION,
        ) and (not question.correct_text_answer or assessment.requires_manual_grading):
            has_pending_manual_question = True
            is_corr = False
            pts = 0
            feedback = "Submitted and queued for instructor evaluation."

        if is_corr:
            total_earned_points += pts

        detailed_answers[str(question.id)] = {
            'prompt': question.prompt,
            'question_type': question.question_type,
            'raw_answer': raw_val,
            'is_correct': is_corr,
            'points_earned': pts,
            'max_points': question.points,
            'feedback': feedback,
            'rubric_criteria': question.rubric_criteria,
        }

    score_pct = int((total_earned_points / total_possible_points) * 100) if total_possible_points > 0 else 0
    passed = score_pct >= assessment.passing_percentage

    prior_attempts = assessment.attempts.filter(student=user).count()
    attempt_number = prior_attempts + 1

    status = (
        QuizAttempt.AttemptStatus.PENDING_REVIEW
        if (has_pending_manual_question or assessment.requires_manual_grading)
        else QuizAttempt.AttemptStatus.GRADED
    )

    attempt = QuizAttempt.objects.create(
        student=user,
        quiz=assessment,
        attempt_number=attempt_number,
        status=status,
        score_percentage=score_pct,
        passed=passed and status == QuizAttempt.AttemptStatus.GRADED,
        points_earned=total_earned_points,
        answers_data=detailed_answers,
        time_taken_seconds=max(int(time_taken_seconds or 0), 0),
    )

    course = assessment.course or (assessment.lesson.module.course if assessment.lesson else None)

    if attempt.passed and status == QuizAttempt.AttemptStatus.GRADED:
        # Award student points once
        profile = getattr(user, 'student_profile', None)
        if profile and prior_attempts == 0:
            profile.points += total_earned_points
            profile.save(update_fields=['points'])

        # If attached to a lesson, mark lesson completed
        if assessment.lesson:
            prog, _ = UserProgress.objects.get_or_create(
                user=user,
                lesson=assessment.lesson,
                defaults={
                    'course': assessment.course or (assessment.lesson.module.course if assessment.lesson.module else None),
                    'module': assessment.lesson.module if assessment.lesson.module else None,
                }
            )
            prog.is_completed = True
            prog.completed_at = timezone.now()
            if not prog.course_id and (assessment.course or (assessment.lesson.module and assessment.lesson.module.course)):
                prog.course = assessment.course or assessment.lesson.module.course
            if not prog.module_id and assessment.lesson.module:
                prog.module = assessment.lesson.module
            prog.save()

        # Standalone or verified exam certificate issuance
        if assessment.is_standalone or assessment.certificate_type == 'exam_verified':
            from apps.certificates.services import issue_certificate_for_exam
            issue_certificate_for_exam(attempt)

    if course:
        from apps.courses.services.completion import sync_course_completion
        sync_course_completion(user, course)

    msg = "Assessment submitted and queued for instructor evaluation." if status == QuizAttempt.AttemptStatus.PENDING_REVIEW else "Assessment graded successfully."
    return attempt, msg


def manual_grade_attempt(attempt: QuizAttempt, evaluator, rubric_scores: dict, overall_feedback: str = "") -> QuizAttempt:
    """
    Evaluates open-ended / practical exam questions using criteria rubric,
    computes final aggregate score, updates attempt status, and issues certificate if passed.
    """
    assessment = attempt.quiz
    questions = assessment.questions.all()
    total_possible_points = sum(q.points for q in questions)
    if total_possible_points == 0:
        total_possible_points = max(questions.count() * 10, 1)

    answers_data = attempt.answers_data or {}
    total_earned = 0

    for q in questions:
        qid_str = str(q.id)
        q_ans = answers_data.get(qid_str, {})
        if qid_str in rubric_scores:
            eval_info = rubric_scores[qid_str]
            awarded_pts = int(eval_info.get('points', 0))
            awarded_pts = max(0, min(awarded_pts, q.points))
            q_ans['points_earned'] = awarded_pts
            q_ans['is_correct'] = awarded_pts >= (q.points * 0.5)
            q_ans['evaluator_feedback'] = eval_info.get('feedback', '')
            q_ans['rubric_level'] = eval_info.get('criteria_level', '')
            answers_data[qid_str] = q_ans
            total_earned += awarded_pts
        else:
            total_earned += int(q_ans.get('points_earned', 0))

    score_pct = int((total_earned / total_possible_points) * 100) if total_possible_points > 0 else 100
    passed = score_pct >= assessment.passing_percentage

    attempt.answers_data = answers_data
    attempt.rubric_scores = rubric_scores
    attempt.feedback = overall_feedback
    attempt.points_earned = total_earned
    attempt.score_percentage = score_pct
    attempt.passed = passed
    attempt.graded_by = evaluator
    attempt.graded_at = timezone.now()
    attempt.status = QuizAttempt.AttemptStatus.GRADED
    attempt.save()

    if passed and (assessment.is_standalone or assessment.certificate_type == 'exam_verified'):
        from apps.certificates.services import issue_certificate_for_exam
        issue_certificate_for_exam(attempt, verified_by=evaluator)

    course = assessment.course or (assessment.lesson.module.course if assessment.lesson else None)
    if passed and course:
        from apps.courses.services.completion import sync_course_completion
        sync_course_completion(attempt.student, course)

    return attempt
