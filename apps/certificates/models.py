import secrets
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class Certificate(BaseModel):
    """
    Cryptographically verifiable credential awarded upon diploma/course completion.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.PROTECT,
        related_name='issued_certificates'
    )
    certificate_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Public certificate serial ID, e.g. MEL-CERT-2026-89A1"
    )
    student_name = models.CharField(max_length=255)
    program_title = models.CharField(max_length=255, default="Diploma in Cyber Security")
    issued_at = models.DateTimeField(auto_now_add=True)
    completion_date = models.DateField(blank=True, null=True, help_text="Date requirements were satisfied.")
    grade = models.CharField(max_length=16, default="Distinction")
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.certificate_code} - {self.student_name}"

    @classmethod
    def generate_code(cls):
        rand = secrets.token_hex(4).upper()
        return f"MEL-CERT-2026-{rand}"


class AssociateCredential(BaseModel):
    """
    Earned Academic Merit Benchmark: "Associate of Myanmar E-Learning".
    Awarded automatically when a student satisfies the merit criteria:
    - completed courses
    - examinations / certificates
    - practical labs
    - projects
    - active learning hours
    """
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='associate_credential'
    )
    credential_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Public credential serial ID, e.g. MEL-ASSOC-2026-89A1"
    )
    title = models.CharField(max_length=255, default="Associate of Myanmar E-Learning")
    awarded_at = models.DateTimeField(auto_now_add=True)
    courses_completed_count = models.PositiveSmallIntegerField(default=0)
    labs_solved_count = models.PositiveSmallIntegerField(default=0)
    capstones_completed_count = models.PositiveSmallIntegerField(default=0)
    active_learning_hours = models.PositiveIntegerField(default=0)
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at']

    def __str__(self):
        return f"{self.credential_code} - {self.student.username}"

    @classmethod
    def generate_code(cls):
        rand = secrets.token_hex(4).upper()
        return f"MEL-ASSOC-2026-{rand}"
