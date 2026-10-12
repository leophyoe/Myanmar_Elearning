"""
Certificate and Associate Credential issuance services.

Certificates are produced automatically when a student's enrollment for a
certificate-eligible course reaches 100%. Issuance is idempotent: re-running it
for the same (student, course) pair returns the existing, un-revoked certificate
instead of minting a duplicate serial.

Associate Credential is an earned academic merit benchmark awarded automatically
when a student fulfills practical and curriculum requirements.
"""

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Certificate, CertificateTemplate, AssociateCredential


def compute_grade(student, course):
    """
    Derive the certificate classification from the student's graded assignment
    work inside the given course.

    Returns one of ``Distinction``, ``Merit`` or ``Pass``. Students with no
    graded work yet still earn a ``Pass`` — reaching 100 % already required
    passing every quiz and assignment lesson.
    """
    from apps.courses.models import AssignmentSubmission

    submissions = AssignmentSubmission.objects.filter(
        student=student,
        assignment__module__course=course,
        score__isnull=False,
    )

    earned = 0
    possible = 0
    for submission in submissions:
        max_score = submission.assignment.max_score or 0
        if not max_score:
            continue
        earned += submission.score * 100 / max_score
        possible += 100

    if not possible:
        return 'Pass'

    percentage = (earned / possible) * 100
    if percentage >= 85:
        return 'Distinction'
    if percentage >= 70:
        return 'Merit'
    return 'Pass'


def issue_certificate_for_enrollment(enrollment):
    """
    Issue (or return) the certificate for an enrolment that has been completed.
    Safe to call repeatedly. Returns None if the course is not certificate eligible.
    """
    course = enrollment.course
    student = enrollment.student

    if not getattr(course, 'certificate_eligible', True):
        return None

    existing = Certificate.objects.filter(
        student=student, course=course, is_revoked=False
    ).first()
    if existing:
        return existing

    comp_date = enrollment.completed_at.date() if enrollment.completed_at else timezone.now().date()
    tpl = getattr(course, 'certificate_template', None)
    if not tpl and getattr(course, 'partner_institution', None):
        tpl = CertificateTemplate.objects.filter(partner=course.partner_institution, is_active=True).first()
    if not tpl:
        tpl = CertificateTemplate.objects.filter(is_default=True, is_active=True).first()

    certificate = Certificate(
        student=student,
        course=course,
        template=tpl,
        student_name=student.get_full_name() or student.username,
        program_title=course.title,
        grade=compute_grade(student, course),
        completion_date=comp_date,
    )

    for _ in range(12):
        certificate.certificate_code = Certificate.generate_code()
        try:
            with transaction.atomic():
                certificate.save()
            break
        except IntegrityError:
            continue
    else:
        certificate.certificate_code = f'{Certificate.generate_code()}-{enrollment.pk.hex[:6].upper()}'
        certificate.save()

    try:
        evaluate_associate_eligibility(student)
    except Exception:
        pass

    return certificate


def issue_certificate_for_exam(attempt, verified_by=None):
    """
    Issue (or return) an Exam-Based Verified Certificate for a passed exam attempt.
    Safe to call repeatedly; returns existing unrevoked certificate if already minted.
    """
    exam = attempt.quiz
    student = attempt.student

    if not attempt.passed:
        return None

    if getattr(exam, 'certificate_type', None) == 'none':
        return None

    existing = Certificate.objects.filter(
        student=student,
        exam=exam,
        certificate_type=Certificate.CertificateType.EXAM_VERIFIED,
        is_revoked=False,
    ).first()
    if existing:
        if not attempt.certificate:
            attempt.certificate = existing
            attempt.save(update_fields=['certificate'])
        return existing

    score = attempt.score_percentage
    grade = 'Pass'
    if score >= 90:
        grade = 'High Distinction'
    elif score >= 80:
        grade = 'Distinction'
    elif score >= 70:
        grade = 'Merit'

    verifier = verified_by or getattr(attempt, 'graded_by', None) or getattr(exam, 'assigned_instructor', None) or getattr(exam, 'owner', None)

    tpl = getattr(exam, 'certificate_template', None)
    if not tpl and exam.course:
        tpl = getattr(exam.course, 'certificate_template', None)
    if not tpl and getattr(exam, 'institution', None):
        tpl = CertificateTemplate.objects.filter(partner=exam.institution, is_active=True).first()
    if not tpl:
        tpl = CertificateTemplate.objects.filter(is_default=True, is_active=True).first()

    certificate = Certificate(
        student=student,
        course=exam.course if exam.course else None,
        exam=exam,
        template=tpl,
        certificate_type=Certificate.CertificateType.EXAM_VERIFIED,
        student_name=student.get_full_name() or student.username,
        program_title=exam.title,
        grade=grade,
        exam_score=score,
        verified_by=verifier,
        completion_date=timezone.now().date(),
    )

    for _ in range(12):
        certificate.certificate_code = Certificate.generate_code(cert_type='exam_verified')
        try:
            with transaction.atomic():
                certificate.save()
            break
        except IntegrityError:
            continue
    else:
        certificate.certificate_code = f"{Certificate.generate_code(cert_type='exam_verified')}-{attempt.pk.hex[:6].upper()}"
        certificate.save()

    attempt.certificate = certificate
    attempt.save(update_fields=['certificate'])

    try:
        evaluate_associate_eligibility(student)
    except Exception:
        pass

    return certificate


def evaluate_associate_eligibility(user):
    """
    Evaluate student's academic and practical achievements to determine
    eligibility for the 'Associate of Myanmar E-Learning' academic title.
    """
    from apps.courses.models import Enrollment, UserProgress

    courses_completed = Enrollment.objects.filter(
        student=user,
        status=Enrollment.Status.COMPLETED,
    ).count()

    labs_solved = UserProgress.objects.filter(
        user=user,
        is_completed=True,
        lab__isnull=False,
    ).count()

    capstones_completed = 0
    try:
        from apps.projects.models import ProjectSubmission
        capstones_completed = ProjectSubmission.objects.filter(
            student=user,
            final_grade__gt='',
        ).count()
    except Exception:
        pass

    completed_progress = UserProgress.objects.filter(
        user=user,
        is_completed=True,
        lesson__isnull=False,
    ).select_related('lesson')
    estimated_mins = sum(p.lesson.estimated_minutes for p in completed_progress if p.lesson)
    learning_hours = max(estimated_mins // 60, courses_completed * 10)

    certs_earned = Certificate.objects.filter(student=user, is_revoked=False).count()

    metrics = {
        'courses_completed': courses_completed,
        'labs_solved': labs_solved,
        'capstones_completed': capstones_completed,
        'learning_hours': learning_hours,
        'certificates_earned': certs_earned,
    }

    existing_cred = AssociateCredential.objects.filter(student=user).first()
    if existing_cred:
        updated = False
        if courses_completed > existing_cred.courses_completed_count:
            existing_cred.courses_completed_count = courses_completed
            updated = True
        if labs_solved > existing_cred.labs_solved_count:
            existing_cred.labs_solved_count = labs_solved
            updated = True
        if capstones_completed > existing_cred.capstones_completed_count:
            existing_cred.capstones_completed_count = capstones_completed
            updated = True
        if learning_hours > existing_cred.active_learning_hours:
            existing_cred.active_learning_hours = learning_hours
            updated = True
        if updated:
            existing_cred.save()
        return True, existing_cred, metrics

    is_eligible = (courses_completed >= 1 or certs_earned >= 1) and (
        labs_solved >= 1 or capstones_completed >= 1 or learning_hours >= 10
    )

    if not is_eligible:
        return False, None, metrics

    cred = AssociateCredential(
        student=user,
        title="Associate of Myanmar E-Learning",
        courses_completed_count=courses_completed,
        labs_solved_count=labs_solved,
        capstones_completed_count=capstones_completed,
        active_learning_hours=learning_hours,
    )

    for _ in range(12):
        cred.credential_code = AssociateCredential.generate_code()
        try:
            with transaction.atomic():
                cred.save()
            return True, cred, metrics
        except IntegrityError:
            continue

    cred.credential_code = f"{AssociateCredential.generate_code()}-{user.pk}"
    cred.save()
    return True, cred, metrics
