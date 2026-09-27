import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel


class CertificateStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Issuance'
    ISSUED = 'ISSUED', 'Issued & Verified'
    REVOKED = 'REVOKED', 'Revoked'


class CertificateTemplate(BaseModel):
    title = models.CharField(max_length=255, default="Certificate in Cyber Security")
    signatory_name = models.CharField(max_length=255, default="Director of Training & Certification")
    signatory_title = models.CharField(max_length=255, default="Lead Security Instructor & Program Director")
    academy_title = models.CharField(max_length=255, default="Future Tech Cyber Security Academy")
    is_default = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.academy_title} - {self.title}"


class Certificate(BaseModel):
    """
    Cryptographically verifiable professional digital certificate and credentials.
    Includes unique certificate number, verification token, and vector SVG QR code.
    """
    certificate_number = models.CharField(max_length=64, unique=True, db_index=True)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='issued_certificates')
    template = models.ForeignKey(CertificateTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    issued_date = models.DateField(default=timezone.now)
    completion_date = models.DateField(default=timezone.now)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    status = models.CharField(max_length=32, choices=CertificateStatus.choices, default=CertificateStatus.ISSUED, db_index=True)
    final_grade = models.CharField(max_length=16, blank=True)
    grade_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    qr_code_svg = models.TextField(blank=True, help_text="Pure vector SVG QR code")

    class Meta:
        ordering = ['-issued_date']
        unique_together = [('student', 'course')]
        indexes = [
            models.Index(fields=['certificate_number', 'status']),
            models.Index(fields=['verification_token']),
        ]

    def __str__(self):
        return f"Certificate {self.certificate_number}: {self.student.get_full_name()} - {self.course.title}"

    @property
    def is_valid(self):
        return self.status == CertificateStatus.ISSUED


class CertificateVerification(BaseModel):
    """
    Audit log of external verifications of this certificate.
    """
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='verification_logs')
    verified_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-verified_at']

    def __str__(self):
        return f"Verified {self.certificate.certificate_number} at {self.verified_at}"

