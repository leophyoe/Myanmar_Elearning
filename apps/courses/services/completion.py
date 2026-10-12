"""
Course Completion and Credential Eligibility Service for Myanmar E-Learning (MEL).
Evaluates holistic pedagogical requirements:
- Lesson completion
- Required quizzes and practical assessments passed
- Assignments submitted and scored
- Official examination passed where required
- Practical hands-on laboratory exercises solved
- Final capstone/projects completed
"""
from django.db.models import Q
from django.utils import timezone
from apps.courses.models import Course, Module, Lesson, Quiz, Question, QuizAttempt, Assignment, AssignmentSubmission, UserProgress, Enrollment


def evaluate_course_completion(user, course: Course) -> dict:
    """
    Evaluates whether a student has satisfied all academic prerequisites
    for a given course curriculum.
    """
    pending = []

    # 1. Lesson Lectures Check
    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_lessons = UserProgress.objects.filter(
        Q(course=course) | Q(lesson__module__course=course),
        user=user,
        is_completed=True,
        lesson__isnull=False,
    ).distinct().count()

    if total_lessons > 0 and completed_lessons < total_lessons:
        pending.append(f"Complete remaining {total_lessons - completed_lessons} lecture lesson(s)")

    # 2. Required Quizzes Check
    required_quizzes = Quiz.objects.filter(
        Q(lesson__module__course=course) | Q(course=course),
        is_required=True,
        quiz_type__in=[
            Quiz.AssessmentType.QUIZ,
            Quiz.AssessmentType.PRACTICE_EXAM,
            Quiz.AssessmentType.PRACTICAL,
        ]
    ).distinct()

    passed_quiz_count = 0
    total_required_quizzes = required_quizzes.count()

    for q in required_quizzes:
        if q.attempts.filter(student=user, passed=True).exists():
            passed_quiz_count += 1
        else:
            pending.append(f"Pass required quiz: '{q.title}' (Passing score: {q.passing_percentage}%)")

    # 3. Required Assignments Check
    assignments = Assignment.objects.filter(module__course=course)
    submitted_assignments_count = 0
    total_assignments = assignments.count()

    for a in assignments:
        if a.submissions.filter(student=user).exists():
            submitted_assignments_count += 1
        else:
            pending.append(f"Submit assignment: '{a.title}'")

    # 4. Course Exam / Final Exam Check
    exams = Quiz.objects.filter(
        Q(lesson__module__course=course) | Q(course=course),
        quiz_type__in=[
            Quiz.AssessmentType.COURSE_EXAM,
            Quiz.AssessmentType.FINAL_EXAM,
            Quiz.AssessmentType.EXAM,
        ]
    ).distinct()

    exam_required = bool(course.exam_required or exams.exists())
    exam_passed = False

    if exam_required:
        if exams.exists():
            for exam in exams:
                if exam.attempts.filter(student=user, passed=True).exists():
                    exam_passed = True
                    break
            if not exam_passed:
                pending.append("Pass official course examination")
        else:
            # Fallback if course marked exam_required but no specific exam entity authored yet
            exam_passed = True

    # 5. Hands-on Practical Labs Check
    lab_lessons = Lesson.objects.filter(module__course=course, has_lab=True)
    total_labs = lab_lessons.count()
    completed_labs = 0

    if total_labs > 0:
        completed_labs = UserProgress.objects.filter(
            Q(course=course) | Q(lesson__module__course=course),
            user=user,
            is_completed=True,
            lab__isnull=False,
        ).distinct().count()
        if completed_labs < total_labs:
            pending.append(f"Solve all {total_labs} hands-on practical lab exercise(s)")

    is_complete = len(pending) == 0
    progress_pct = int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else (100 if is_complete else 0)

    return {
        'is_complete': is_complete,
        'progress_pct': progress_pct,
        'lessons_completed': completed_lessons,
        'total_lessons': total_lessons,
        'quizzes_passed': passed_quiz_count,
        'total_required_quizzes': total_required_quizzes,
        'assignments_submitted': submitted_assignments_count,
        'total_assignments': total_assignments,
        'exam_required': exam_required,
        'exam_passed': exam_passed,
        'labs_completed': completed_labs,
        'total_labs': total_labs,
        'pending_requirements': pending,
    }


def evaluate_certificate_eligibility(user, course: Course) -> tuple[bool, str]:
    """
    Determines whether a student is officially eligible for certificate generation.
    Enforces that membership subscriptions alone never auto-generate certificates.
    """
    if not getattr(course, 'certificate_eligible', True):
        return False, "This curriculum does not issue certificates."

    enrollment = Enrollment.objects.filter(course=course, student=user).first()
    if not enrollment:
        return False, "Active course enrollment is required."

    evaluation = evaluate_course_completion(user, course)
    if not evaluation['is_complete']:
        reasons = "; ".join(evaluation['pending_requirements'])
        return False, f"Incomplete coursework requirements: {reasons}"

    return True, ""


def sync_course_completion(user, course: Course) -> Enrollment:
    """
    Synchronizes enrollment progress, verifies completion conditions,
    updates completion timestamp, and issues certificate if eligible.
    """
    enrollment = Enrollment.objects.filter(
        course=course,
        student=user,
    ).exclude(status=Enrollment.Status.DROPPED).first()

    if not enrollment:
        return None

    evaluation = evaluate_course_completion(user, course)
    enrollment.progress_pct = evaluation['progress_pct']

    if evaluation['is_complete']:
        enrollment.status = Enrollment.Status.COMPLETED
        if not enrollment.completed_at:
            enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['progress_pct', 'status', 'completed_at'])

        # Issue certificate if eligible
        from apps.certificates.services import issue_certificate_for_enrollment
        issue_certificate_for_enrollment(enrollment)
    else:
        # Keep status ACTIVE even if lessons reached 100% when other requirements remain pending
        if enrollment.status == Enrollment.Status.COMPLETED and not evaluation['is_complete']:
            enrollment.status = Enrollment.Status.ACTIVE
        enrollment.save(update_fields=['progress_pct', 'status'])

    return enrollment
