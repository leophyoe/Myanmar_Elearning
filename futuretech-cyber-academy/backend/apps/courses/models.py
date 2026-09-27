from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.core.validators import validate_resource_file

class CourseType(models.TextChoices):
    CERTIFICATE = 'CERTIFICATE', 'Certificate Program'
    DIPLOMA = 'DIPLOMA', 'Diploma Program'
    SHORT_COURSE = 'SHORT_COURSE', 'Short Course'
    PROFESSIONAL = 'PROFESSIONAL', 'Professional Specialization'
    OTHER = 'OTHER', 'Other'


class CourseCategory(BaseModel):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=64, default="shield", help_text="Lucide or FontAwesome icon tag")

    class Meta:
        verbose_name_plural = "Course Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class CourseLevel(models.TextChoices):
    BEGINNER = 'BEGINNER', 'Beginner'
    INTERMEDIATE = 'INTERMEDIATE', 'Intermediate'
    ADVANCED = 'ADVANCED', 'Advanced'


class CourseStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    ARCHIVED = 'ARCHIVED', 'Archived'


class Course(BaseModel):
    course_type = models.CharField(max_length=32, choices=CourseType.choices, default=CourseType.CERTIFICATE, db_index=True)
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True, db_index=True)
    short_description = models.CharField(max_length=512)
    description = models.TextField()
    description_en = models.TextField(blank=True)
    description_my = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', null=True, blank=True)
    level = models.CharField(max_length=32, choices=CourseLevel.choices, default=CourseLevel.BEGINNER)
    duration = models.CharField(max_length=64, default="10 Months")
    language = models.CharField(max_length=64, default="English")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=True)
    passing_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('70.00'))
    certificate_enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=32, choices=CourseStatus.choices, default=CourseStatus.DRAFT, db_index=True)
    categories = models.ManyToManyField(CourseCategory, related_name='courses', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_courses')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug', 'status']),
            models.Index(fields=['course_type', 'status']),
        ]

    def __str__(self):
        return self.title

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_description(self, lang='en'):
        if lang == 'my' and self.description_my:
            return self.description_my
        return self.description_en or self.description

    @property
    def total_lessons_count(self):
        return Lesson.objects.filter(module__course=self, is_published=True).count()

    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if not reviews.exists():
            return 5.0
        total = sum(r.rating for r in reviews)
        return round(total / reviews.count(), 1)


class CourseModule(BaseModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    description_en = models.TextField(blank=True)
    description_my = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=1, db_index=True)
    learning_objectives = models.JSONField(default=list, blank=True)
    estimated_hours = models.PositiveIntegerField(default=10)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        unique_together = [('course', 'order'), ('course', 'slug')]

    def __str__(self):
        return f"{self.course.title} - M{self.order}: {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_description(self, lang='en'):
        if lang == 'my' and self.description_my:
            return self.description_my
        return self.description_en or self.description


class LessonType(models.TextChoices):
    THEORY = 'THEORY', 'Theory'
    ARTICLE = 'ARTICLE', 'Article'
    VIDEO = 'VIDEO', 'Video'
    READING = 'READING', 'Reading'
    PRACTICAL = 'PRACTICAL', 'Practical Lab'
    REVIEW = 'REVIEW', 'Review'
    QUIZ = 'QUIZ', 'Quiz'
    RESOURCE = 'RESOURCE', 'Downloadable Resource'
    OTHER = 'OTHER', 'Other'


class Lesson(BaseModel):
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(db_index=True)
    lesson_type = models.CharField(max_length=32, choices=LessonType.choices, default=LessonType.ARTICLE)
    content = models.TextField(help_text="Supports rich Markdown content")
    content_en = models.TextField(blank=True)
    content_my = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=1, db_index=True)
    estimated_minutes = models.PositiveIntegerField(default=30)
    is_published = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        unique_together = [('module', 'order'), ('module', 'slug')]
        indexes = [
            models.Index(fields=['slug', 'is_published']),
            models.Index(fields=['module', 'is_required']),
        ]

    def __str__(self):
        return f"{self.module.title} - L{self.order}: {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_content(self, lang='en'):
        if lang == 'my' and self.content_my:
            return self.content_my
        return self.content_en or self.content


class LearningObjective(BaseModel):
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name='objectives')
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='objectives')
    title_en = models.CharField(max_length=255)
    title_my = models.CharField(max_length=255, blank=True)
    description_en = models.TextField(blank=True)
    description_my = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.module.title} - Obj {self.order}: {self.title_en}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en

    def get_description(self, lang='en'):
        if lang == 'my' and self.description_my:
            return self.description_my
        return self.description_en


class ResourceType(models.TextChoices):
    PDF = 'PDF', 'PDF Document'
    DOCUMENT = 'DOCUMENT', 'Word/Document'
    IMAGE = 'IMAGE', 'Image'
    ZIP = 'ZIP', 'Zip/Archive'
    LINK = 'LINK', 'External Link'
    OTHER = 'OTHER', 'Other File'


class CourseResource(BaseModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='course_resources/',
        validators=[validate_resource_file],
        null=True,
        blank=True
    )
    resource_type = models.CharField(max_length=32, choices=ResourceType.choices, default=ResourceType.PDF)
    description = models.TextField(blank=True)
    external_link = models.URLField(blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_resource_type_display()})"


class CourseReview(BaseModel):
    """
    Student course review with rating, commentary, and duplicate review prevention.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_reviews')
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f"{i} Stars") for i in range(1, 6)],
        default=5,
        help_text="Rating between 1 and 5 stars"
    )
    comment = models.TextField()
    is_approved = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('course', 'student')]
        indexes = [
            models.Index(fields=['course', 'is_approved']),
        ]

    def __str__(self):
        return f"{self.student.username} - {self.course.title} ({self.rating}★)"

