"""
Certificate issuance.

Certificates are produced automatically the moment a student's enrolment for a
course reaches 100 %, so no administrator has to create them by hand. Issuance
is idempotent: re-running it for the same (student, course) pair returns the
existing, un-revoked certificate instead of minting a duplicate serial.
"""

from django.db import IntegrityError, transaction

from .models import Certificate


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
    Safe to call repeatedly.
    """
    student = enrollment.student
    course = enrollment.course

    existing = Certificate.objects.filter(
        student=student, course=course, is_revoked=False
    ).first()
    if existing:
        return existing

    certificate = Certificate(
        student=student,
        course=course,
        student_name=student.get_full_name() or student.username,
        program_title=course.title,
        grade=compute_grade(student, course),
    )

    for _ in range(12):
        certificate.certificate_code = Certificate.generate_code()
        # Savepoints keep a serial collision from poisoning an enclosing
        # transaction (the test suite runs inside one).
        try:
            with transaction.atomic():
                certificate.save()
        except IntegrityError:
            continue
        return certificate

    # A collision after a dozen attempts is effectively impossible, but never
    # fail a completed course because of the serial generator.
    certificate.certificate_code = f'{Certificate.generate_code()}-{enrollment.pk.hex[:6].upper()}'
    certificate.save()
    return certificate
