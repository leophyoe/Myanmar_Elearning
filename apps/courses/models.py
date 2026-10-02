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

    @classmethod
    def ensure_default_subjects(cls):
        """
        Seeds standard subject disciplines:
        - Python Programming
        - Computer Science
        - ICT
        - IGCSE / O Level
        - GED
        - Artificial Intelligence
        - Cyber Security
        - Engineering
        - Non-IT subjects
        """
        categories = [
            {
                'slug': 'python-programming',
                'title': 'Python Programming',
                'description': 'Master Python from fundamentals to advanced automation and software development.',
                'icon_name': 'code-slash',
                'kind': cls.Kind.GENERAL,
                'order': 1,
            },
            {
                'slug': 'computer-science',
                'title': 'Computer Science',
                'description': 'Data structures, algorithms, operating systems, and computer architecture.',
                'icon_name': 'cpu',
                'kind': cls.Kind.GENERAL,
                'order': 2,
            },
            {
                'slug': 'ict',
                'title': 'Information & Communication Technology (ICT)',
                'description': 'Digital literacy, productivity tools, computer networking, and office systems.',
                'icon_name': 'laptop',
                'kind': cls.Kind.GENERAL,
                'order': 3,
            },
            {
                'slug': 'igcse-o-level',
                'title': 'IGCSE / O Level',
                'description': 'International curriculum preparation for IGCSE Computer Science, ICT, and Sciences.',
                'icon_name': 'mortarboard',
                'kind': cls.Kind.GENERAL,
                'order': 4,
            },
            {
                'slug': 'ged',
                'title': 'GED (General Educational Development)',
                'description': 'Comprehensive preparation for high school equivalency exams.',
                'icon_name': 'journal-bookmark',
                'kind': cls.Kind.GENERAL,
                'order': 5,
            },
            {
                'slug': 'artificial-intelligence',
                'title': 'Artificial Intelligence & Machine Learning',
                'description': 'Deep learning, computer vision, natural language processing, and modern GenAI.',
                'icon_name': 'robot',
                'kind': cls.Kind.GENERAL,
                'order': 6,
            },
            {
                'slug': 'cyber-security',
                'title': 'Cyber Security & Ethical Hacking',
                'description': 'Network defense, web security, reverse engineering, and hands-on CTF challenges.',
                'icon_name': 'shield-check',
                'kind': cls.Kind.CYBER,
                'order': 7,
            },
            {
                'slug': 'engineering',
                'title': 'Engineering & Technology',
                'description': 'Electrical engineering, embedded systems, robotics, and hardware principles.',
                'icon_name': 'gear',
                'kind': cls.Kind.GENERAL,
                'order': 8,
            },
            {
                'slug': 'non-it',
                'title': 'Non-IT & Academic Subjects',
                'description': 'Languages, business studies, mathematics, and professional development.',
                'icon_name': 'book',
                'kind': cls.Kind.GENERAL,
                'order': 9,
            },
        ]
        created = []
        for cat in categories:
            slug = cat.pop('slug')
            obj, _ = cls.objects.update_or_create(slug=slug, defaults=cat)
            created.append(obj)
        return created


class Course(BaseModel):
    """
    Top-level academic program (e.g. Diploma in Cyber Security).
    """

    class BillingPeriod(models.TextChoices):
        ONE_TIME = 'one_time', 'One-time payment'
        MONTHLY = 'monthly', 'Monthly subscription'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    class MembershipTierRequired(models.TextChoices):
        STARTER = 'starter', 'Starter (Free / Exploratory)'
        STANDARD = 'standard', 'Standard Tier'
        PREMIUM = 'premium', 'Premium Tier'

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        ALL_LEVELS = 'all_levels', 'All Levels'

    class Language(models.TextChoices):
        BURMESE = 'my', 'Myanmar'
        ENGLISH = 'en', 'English'
        BILINGUAL = 'bi', 'Bilingual (Myanmar + English)'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
        help_text="Course editorial lifecycle state."
    )
    membership_tier_required = models.CharField(
        max_length=16,
        choices=MembershipTierRequired.choices,
        default=MembershipTierRequired.STANDARD,
        db_index=True,
        help_text="Minimum membership tier required to access this course."
    )
    certificate_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Additional certificate issuance fee (in MMK). 0 if included in course/membership."
    )
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
    level = models.CharField(
        max_length=16,
        choices=Level.choices,
        default=Level.ALL_LEVELS,
        db_index=True,
    )
    language = models.CharField(
        max_length=8,
        choices=Language.choices,
        default=Language.BURMESE,
    )
    is_premium = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Requires Premium membership tier or individual course purchase.",
    )
    certificate_eligible = models.BooleanField(
        default=True,
        help_text="Grants verified completion certificate upon passing criteria.",
    )
    exam_required = models.BooleanField(
        default=False,
        help_text="Requires passing an official proctored examination before certification.",
    )
    exam_voucher_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Price for specialized proctored examination voucher (in MMK). 0 if included in course.",
    )
    duration_months = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=True, db_index=True)
    is_official = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates official Myanmar E-Learning platform course created/owned by administration."
    )
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

    def save(self, *args, **kwargs):
        if self.owner and hasattr(self.owner, 'is_admin') and self.owner.is_admin:
            self.is_official = True
        elif self.owner is None:
            self.is_official = True
        if self.status == self.Status.PUBLISHED:
            self.is_published = True
        elif self.status in (self.Status.DRAFT, self.Status.PENDING_REVIEW, self.Status.ARCHIVED):
            self.is_published = False
        super().save(*args, **kwargs)

    @property
    def is_free(self):
        return self.price is None or self.price <= 0

    @property
    def is_official_platform_course(self):
        """Returns True if marked official or authored by administration / unassigned."""
        if self.is_official:
            return True
        if self.owner is None:
            return True
        if hasattr(self.owner, 'is_admin') and self.owner.is_admin:
            return True
        return False

    @property
    def publisher_display_name(self):
        """Displays 'Myanmar E-Learning' for official platform courses, or the instructor's name."""
        if self.is_official_platform_course:
            return "Myanmar E-Learning"
        return self.owner.get_full_name() or self.owner.username


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
    class QuizType(models.TextChoices):
        QUIZ = 'quiz', 'Module/Lesson Quiz'
        EXAM = 'exam', 'Proctored Final Exam'
        PRACTICE_EXAM = 'practice_exam', 'Practice Exam'
        PRACTICAL = 'practical', 'Practical Assessment'

    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255)
    quiz_type = models.CharField(
        max_length=20,
        choices=QuizType.choices,
        default=QuizType.QUIZ,
        db_index=True,
    )
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


class QuizAttempt(BaseModel):
    """
    Pedagogical audit trail for every student attempt at a quiz or exam.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    score_percentage = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    points_earned = models.PositiveIntegerField(default=0)
    answers_data = models.JSONField(default=dict, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} (Attempt #{self.attempt_number}: {self.score_percentage}%)"


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
    started_at = models.DateTimeField(blank=True, null=True, db_index=True, help_text="First accessed lesson timestamp.")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [('course', 'student')]
        indexes = [
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.course.title} ({self.get_status_display()})"

    @property
    def completed_lessons_count(self):
        from .models import UserProgress
        return UserProgress.objects.filter(
            user=self.student,
            lesson__module__course=self.course,
            is_completed=True,
        ).count()

    @property
    def completed_modules_count(self):
        total_completed = 0
        for mod in self.course.modules.prefetch_related('lessons').all():
            total_lessons = mod.lessons.count()
            if total_lessons > 0:
                completed = self.student.progress_records.filter(
                    lesson__module=mod,
                    is_completed=True,
                ).count()
                if completed >= total_lessons:
                    total_completed += 1
        return total_completed



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
