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

