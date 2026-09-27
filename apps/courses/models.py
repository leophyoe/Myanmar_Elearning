from django.db import models
from django.conf import settings
from apps.common.models import BaseModel


class Subject(BaseModel):
    """
    Top-level subject / category that groups courses.

    Kind distinguishes general academic subjects from the integrated
    cyber security range (which exposes labs, CTF and the web terminal).
    """

    class Kind(models.TextChoices):
        GENERAL = 'general', 'General'
        CYBER = 'cyber', 'Cyber Security'

    title = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=64, default="book-open")
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.GENERAL,
        db_index=True,
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


class Course(BaseModel):
    """
    Top-level academic program (e.g. Diploma in Cyber Security).
    """
    title = models.CharField(max_length=255, default="Diploma in Cyber Security")
    slug = models.SlugField(unique=True, db_index=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )
    description = models.TextField()
    duration_months = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=True, db_index=True)
    thumbnail = models.ImageField(upload_to='courses/', null=True, blank=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class Module(BaseModel):
    """
    Modular division of the Diploma curriculum (14 modules).
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    order = models.PositiveSmallIntegerField(db_index=True)
    code = models.CharField(max_length=32, db_index=True, help_text="e.g., MOD-01, MOD-14")
    title = models.CharField(max_length=255)
    summary = models.TextField()
    learning_objectives = models.JSONField(default=list, blank=True)
    icon_name = models.CharField(max_length=64, default="shield-check")

    class Meta:
        ordering = ['order']
        unique_together = [('course', 'order'), ('course', 'code')]

    def __str__(self):
        return f"{self.code}: {self.title}"


class Lesson(BaseModel):
    """
    Structured learning unit inside a module.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    order = models.PositiveSmallIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    content_markdown = models.TextField(help_text="Detailed theoretical lecture in Markdown format")
    estimated_minutes = models.PositiveIntegerField(default=45)
    has_lab = models.BooleanField(default=False)
    has_quiz = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = [('module', 'order')]

    def __str__(self):
        return f"{self.module.code} - L{self.order}: {self.title}"


class Topic(BaseModel):
    """
    Granular topic or theoretical section within a lesson.
    """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='topics')
    order = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=255)
    content_markdown = models.TextField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.lesson.title} -> {self.title}"


class Quiz(BaseModel):
    """
    Multiple-choice knowledge evaluation for a lesson or module.
    """
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255)
    passing_percentage = models.PositiveSmallIntegerField(default=75)
    max_attempts = models.PositiveSmallIntegerField(default=3)

    def __str__(self):
        return f"Quiz: {self.title} ({self.lesson.title})"


class Question(BaseModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveSmallIntegerField(default=1)
    prompt = models.TextField()
    points = models.PositiveSmallIntegerField(default=10)
    explanation = models.TextField(blank=True, help_text="Explanatory feedback shown after attempt")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.prompt[:60]}..."


class Choice(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=512)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{'[✓]' if self.is_correct else '[ ]'} {self.text[:50]}"


class Assignment(BaseModel):
    """
    Practical or written assignment for instructor grading.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField()
    max_score = models.PositiveIntegerField(default=100)
    due_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Assignment: {self.title} ({self.module.code})"


class AssignmentSubmission(BaseModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_text = models.TextField(blank=True)
    submission_file = models.FileField(upload_to='submissions/', null=True, blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_assignments')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('assignment', 'student')]

    def __str__(self):
        return f"Submission by {self.student.username} for {self.assignment.title}"


class UserProgress(BaseModel):
    """
    Tracks granular completion states for lessons, modules, and labs.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='user_progress')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True)
    lab = models.ForeignKey('labs.Lab', on_delete=models.CASCADE, null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('user', 'lesson')]
        indexes = [
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.lesson or self.module} ({'Done' if self.is_completed else 'Pending'})"

