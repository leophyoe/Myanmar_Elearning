from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel

class NotificationType(models.TextChoices):
    INFO = 'INFO', 'Information'
    ENROLLMENT = 'ENROLLMENT', 'Enrollment Update'
    COMPLETION = 'COMPLETION', 'Lesson/Course Completion'
    COURSE = 'COURSE', 'Course Update'
    QUIZ = 'QUIZ', 'Quiz Alert'
    ASSIGNMENT = 'ASSIGNMENT', 'Assignment Alert'
    EXAM = 'EXAM', 'Examination Alert'
    CERTIFICATE = 'CERTIFICATE', 'Certificate Issued'
    SYSTEM = 'SYSTEM', 'System Alert'


class Notification(BaseModel):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices, default=NotificationType.INFO)
    link = models.CharField(max_length=512, blank=True, help_text="Optional target link")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f"{self.recipient.email}: {self.title} ({'Read' if self.is_read else 'Unread'})"


class Announcement(BaseModel):
    """
    Campus-wide or course-specific announcements published by instructors or administrators.
    """
    title = models.CharField(max_length=255)
    content = models.TextField()
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='announcements'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_announcements'
    )
    published_at = models.DateTimeField(default=timezone.now)
    is_published = models.BooleanField(default=True, db_index=True)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_pinned', '-published_at']
        indexes = [
            models.Index(fields=['course', 'is_published']),
            models.Index(fields=['is_pinned', 'published_at']),
        ]

    def __str__(self):
        target = self.course.title if self.course else "Academy-Wide"
        return f"[{target}] {self.title}"


