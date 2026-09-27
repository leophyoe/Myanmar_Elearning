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

    class BillingPeriod(models.TextChoices):
        ONE_TIME = 'one_time', 'One-time payment'
        MONTHLY = 'monthly', 'Monthly subscription'

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

    # Commercial settings — teachers price their own courses; the platform keeps
    # settings.PAYMENT_PLATFORM_COMMISSION_RATE of every approved payment.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_courses',
        help_text="Teacher who publishes this course and receives the revenue share.",
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Price per billing period. Set 0 to publish the course for free.",
    )
    currency = models.CharField(max_length=8, default='MMK', editable=False)
    billing_period = models.CharField(
        max_length=16,
        choices=BillingPeriod.choices,
        default=BillingPeriod.ONE_TIME,
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def is_free(self):
        return self.price is None or self.price <= 0


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


class LessonType(models.TextChoices):
    TEXT = 'text', 'Text / Article'
    VIDEO = 'video', 'Video'
    PDF = 'pdf', 'PDF Document'
    QUIZ = 'quiz', 'Quiz'
    ASSIGNMENT = 'assignment', 'Assignment'
    LAB = 'lab', 'Hands-on Lab'
    CTF = 'ctf', 'CTF Challenge'


class Lesson(BaseModel):
    """
    Structured learning unit inside a module.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    order = models.PositiveSmallIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    lesson_type = models.CharField(
        max_length=16,
        choices=LessonType.choices,
        default=LessonType.TEXT,
        db_index=True,
        help_text="Determines how the lesson body is rendered for students.",
    )
    content_markdown = models.TextField(help_text="Detailed theoretical lecture in Markdown format")
    video_url = models.URLField(
        blank=True,
        help_text="External video link (YouTube, Vimeo, ...). Used when no file is uploaded.",
    )
    video_file = models.FileField(
        upload_to='lessons/video/%Y/%m/',
        null=True,
        blank=True,
        help_text="Uploaded video file (mp4/webm).",
    )
    document_file = models.FileField(
        upload_to='lessons/docs/%Y/%m/',
        null=True,
        blank=True,
        help_text="Attached document, e.g. a PDF handout.",
    )
    estimated_minutes = models.PositiveIntegerField(default=45)
    has_lab = models.BooleanField(default=False)
    has_quiz = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = [('module', 'order')]

    def __str__(self):
        return f"{self.module.code} - L{self.order}: {self.title}"

    @property
    def course(self):
        return self.module.course

    @property
    def has_video(self):
        return bool(self.video_file or self.video_url)

    @property
    def has_document(self):
        return bool(self.document_file)


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


class Enrollment(BaseModel):
    """
    A student's registration on a course. Required before lessons can be opened.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DROPPED = 'dropped', 'Dropped'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    progress_pct = models.PositiveSmallIntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [('course', 'student')]
        indexes = [
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.course.title} ({self.get_status_display()})"



class LiveSession(BaseModel):
    """
    A scheduled real-time class for a course (Zoom, Google Meet, Teams, ...).
    Only students with access to the course can see the joining link.
    """

    class Provider(models.TextChoices):
        ZOOM = 'zoom', 'Zoom'
        GOOGLE_MEET = 'google_meet', 'Google Meet'
        TEAMS = 'teams', 'Microsoft Teams'
        OTHER = 'other', 'Other / custom link'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='live_sessions')
    title = models.CharField(max_length=255)
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.ZOOM
    )
    join_url = models.URLField(help_text="Direct joining URL for the session.")
    starts_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return f"{self.title} ({self.get_provider_display()})"

    @property
    def is_upcoming(self):
        from django.utils import timezone
        return self.starts_at >= timezone.now()
