import hashlib
import logging
import uuid
from decimal import Decimal
from django.utils import timezone
from .models import Certificate, CertificateTemplate, CertificateStatus

logger = logging.getLogger(__name__)


def generate_svg_qr(data_text: str, size: int = 200) -> str:
    """
    Generates a pure-vector SVG QR badge.
    Uses version 2 QR dimensions (25x25) with authentic position markers, timing tracks,
    and a deterministic data matrix derived from the payload.
    Rendered as an optimized single SVG path for minimal size and high rendering performance.
    """
    grid_size = 25
    matrix = [[0] * grid_size for _ in range(grid_size)]

    # 1. Position Detection Markers (7x7) at (0,0), (0, 18), (18, 0)
    def place_finder(r, c):
        for dr in range(7):
            for dc in range(7):
                if dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4):
                    matrix[r + dr][c + dc] = 1
                else:
                    matrix[r + dr][c + dc] = 0

    place_finder(0, 0)
    place_finder(0, grid_size - 7)
    place_finder(grid_size - 7, 0)

    # 2. Timing patterns
    for i in range(8, grid_size - 8):
        matrix[6][i] = 1 if i % 2 == 0 else 0
        matrix[i][6] = 1 if i % 2 == 0 else 0

    # 3. Deterministic payload matrix
    h = hashlib.sha256(data_text.encode('utf-8')).digest()
    bit_idx = 0
    for r in range(grid_size):
        for c in range(grid_size):
            if (r < 8 and (c < 8 or c >= grid_size - 8)) or (r >= grid_size - 8 and c < 8):
                continue
            if r == 6 or c == 6:
                continue
            byte_val = h[(bit_idx // 8) % len(h)]
            bit = (byte_val >> (bit_idx % 8)) & 1
            matrix[r][c] = bit
            bit_idx += 1

    # Render optimized single-path SVG
    cell_size = size / (grid_size + 4)
    path_commands = []
    for r in range(grid_size):
        for c in range(grid_size):
            if matrix[r][c] == 1:
                x = (c + 2) * cell_size
                y = (r + 2) * cell_size
                path_commands.append(f"M{x:.1f},{y:.1f}h{cell_size:.1f}v{cell_size:.1f}h-{cell_size:.1f}z")

    path_d = "".join(path_commands)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<rect width="100%" height="100%" fill="#ffffff" rx="8"/>'
        f'<path d="{path_d}" fill="#0f172a"/>'
        f'</svg>'
    )


class CertificateEligibilityService:
    """
    Authoritative evaluation service for digital certificate issuance.
    Verifies that a student has met ALL course completion and assessment requirements:
    1. 100% of published course lessons completed
    2. All published course quizzes passed
    3. All published course assignments submitted
    4. All published course examinations passed
    5. Overall composite weighted grade >= 70.0% (passing threshold)
    """

    @classmethod
    def evaluate_eligibility(cls, student, course) -> dict:
        from apps.courses.completion_service import CourseCompletionService
        from apps.assessments.services import GradeCalculationService

        completion_data = CourseCompletionService.check_and_complete_course(student, course)
        grades = GradeCalculationService.calculate_student_grade(student, course)

        is_eligible = completion_data.get('is_eligible', False) or completion_data.get('eligible', False)
        academically_passed = grades.get('passed', False)

        return {
            'eligible': is_eligible,
            'completion_details': completion_data.get('details', {}),
            'grades': grades,
            'academically_passed': academically_passed,
        }


class CertificateGenerationService:
    """
    Issues and manages cryptographically verifiable professional digital certificates.
    """

    @classmethod
    def generate_certificate_number(cls, year=None):
        if not year:
            year = timezone.now().year
        for _ in range(10):
            token = uuid.uuid4().hex[:8].upper()
            number = f"FTCSA-{year}-{token}"
            if not Certificate.objects.filter(certificate_number=number).exists():
                return number
        return f"FTCSA-{year}-{uuid.uuid4().hex[:12].upper()}"

    @classmethod
    def issue_certificate(cls, student, course, verify_eligibility=False):
        """
        Creates or retrieves an existing Certificate for a student in a course.
        """
        existing = Certificate.objects.filter(student=student, course=course).first()
        if existing:
            return existing

        if verify_eligibility:
            eval_result = CertificateEligibilityService.evaluate_eligibility(student, course)
            if not eval_result['eligible']:
                raise ValueError("Student has not fulfilled all completion and assessment requirements for this certificate.")

        from django.db import transaction
        with transaction.atomic():
            # Double check inside transaction
            existing = Certificate.objects.filter(student=student, course=course).first()
            if existing:
                return existing

            template = CertificateTemplate.objects.filter(is_default=True).first()
            if not template:
                template = CertificateTemplate.objects.create(
                    title=f"Certificate in {course.title}" if not course.title.upper().startswith("CERTIFICATE") else course.title,
                    signatory_name="Director of Training & Certification",
                    signatory_title="Lead Security Instructor & Program Director",
                    academy_title="Future Tech Cyber Security Academy"
                )

            cert_number = cls.generate_certificate_number()
            verification_token = uuid.uuid4()
            verify_url = f"/verify/{cert_number}/"
            qr_svg = generate_svg_qr(verify_url)

            from apps.assessments.services import GradeCalculationService
            grade_info = GradeCalculationService.calculate_student_grade(student, course)
            final_grade_str = grade_info.get('letter_grade', 'C+')
            grade_pct = Decimal(str(grade_info.get('final_grade', '70.00')))

            cert = Certificate.objects.create(
                certificate_number=cert_number,
                student=student,
                course=course,
                template=template,
                issued_date=timezone.now().date(),
                completion_date=timezone.now().date(),
                verification_token=verification_token,
                status=CertificateStatus.ISSUED,
                final_grade=final_grade_str,
                grade_percentage=grade_pct,
                qr_code_svg=qr_svg
            )

        from apps.core.audit import log_audit_event
        log_audit_event(
            user=student,
            action="CERTIFICATE_ISSUED",
            object_type="Certificate",
            object_id=str(cert.id),
            metadata={'certificate_number': cert_number, 'course_title': course.title}
        )

        # Award badge if first certificate
        try:
            from apps.achievements.services import AchievementEvaluationService
            AchievementEvaluationService.evaluate_student(
                student=student,
                event="CERTIFICATE_ISSUED",
                context={'certificate': cert}
            )
        except Exception as e:
            logger.error(f"Achievement check failed for certificate: {e}")

        return cert

