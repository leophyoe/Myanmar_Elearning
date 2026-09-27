from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel

class LessonProgress(BaseModel):
    """
    Tracks granular per-lesson learning and completion status.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_progress_records')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='student_progress')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False, db_index=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('student', 'lesson')]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['student', 'completed']),
        ]

    def __str__(self):
        status = "COMPLETED" if self.completed else "IN PROGRESS"
        return f"{self.student.username} -> {self.lesson.title} [{status}]"

    def mark_started(self):
        """Marks the lesson as started if not already recorded."""
        if not self.started_at:
            self.started_at = timezone.now()
            self.save(update_fields=['started_at', 'updated_at'])

    def mark_completed(self):
        """Marks the lesson as completed and triggers overall course progress recalculation."""
        self.completed = True
        if not self.completed_at:
            self.completed_at = timezone.now()
        if not self.started_at:
            self.started_at = self.completed_at
        self.save(update_fields=['completed', 'completed_at', 'started_at', 'updated_at'])

        # Recalculate course progress
        from .services import ProgressCalculationService
        ProgressCalculationService.update_course_progress(self.student, self.lesson.module.course)


class ModuleProgress(BaseModel):
    """
    Granular module progress tracking weighted across:
    Lessons (30%), Quizzes (15%), Assignments (15%), Practical Labs (25% placeholder), Module Exam (15%).
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='module_progress_records')
    module = models.ForeignKey('courses.CourseModule', on_delete=models.CASCADE, related_name='student_progress')
    lesson_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    quiz_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    assignment_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    practical_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    exam_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    overall_progress = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('student', 'module')]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['student', 'is_completed']),
        ]

    def __str__(self):
        status = "COMPLETED" if self.is_completed else "IN PROGRESS"
        return f"{self.student.username} -> {self.module.title} [{status}: {self.overall_progress}%]"

