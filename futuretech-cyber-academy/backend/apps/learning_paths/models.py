from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.enrollments.models import Enrollment


class LearningPathLevel(models.TextChoices):
    BEGINNER = 'BEGINNER', 'Beginner'
    INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
    ADVANCED = 'ADVANCED', 'Advanced'


class LearningPath(BaseModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()
    icon = models.CharField(max_length=64, default="shield", help_text="Lucide icon identifier")
    estimated_months = models.PositiveIntegerField(default=6)
    level = models.CharField(max_length=32, choices=LearningPathLevel.choices, default=LearningPathLevel.BEGINNER)
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def total_courses(self):
        return self.path_courses.count()


class LearningPathCourse(BaseModel):
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name='path_courses')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='in_learning_paths')
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = [('learning_path', 'course'), ('learning_path', 'order')]

    def __str__(self):
        return f"{self.learning_path.title} - Step {self.order}: {self.course.title}"


class StudentLearningPath(BaseModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrolled_paths')
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name='student_enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=32, default="ACTIVE")

    class Meta:
        unique_together = [('student', 'learning_path')]
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} -> {self.learning_path.title} ({self.progress_percentage}%)"

    def recalculate_progress(self):
        """Calculates cumulative progress across all sequenced courses in this learning path."""
        courses = [pc.course for pc in self.learning_path.path_courses.all()]
        if not courses:
            return Decimal('0.00')

        total_progress = Decimal('0.00')
        for course in courses:
            enrollment = Enrollment.objects.filter(student=self.student, course=course).first()
            if enrollment:
                total_progress += enrollment.progress_percentage

        average = (total_progress / len(courses)).quantize(Decimal('0.01'))
        self.progress_percentage = min(Decimal('100.00'), average)
        if self.progress_percentage >= Decimal('100.00'):
            self.status = "COMPLETED"
        self.save(update_fields=['progress_percentage', 'status', 'updated_at'])
        return self.progress_percentage

