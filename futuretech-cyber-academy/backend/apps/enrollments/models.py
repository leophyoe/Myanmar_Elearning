from django.db import models
from django.conf import settings
from apps.core.models import BaseModel

class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    WITHDRAWN = 'WITHDRAWN', 'Withdrawn'
    EXPIRED = 'EXPIRED', 'Expired'


class Enrollment(BaseModel):
    """
    Student enrollment in a course.
    Enforces unique_together constraint to prevent duplicate enrollments.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    expected_end_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True
    )
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    class Meta:
        unique_together = [('student', 'course')]
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} -> {self.course.title} ({self.status} - {self.progress_percentage}%)"

