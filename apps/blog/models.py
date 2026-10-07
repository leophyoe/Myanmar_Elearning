from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel


class ArticleCategory(BaseModel):
    """Category classification for Knowledge Hub developer articles."""
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=32,
        default='book',
        help_text='Icon identifier, e.g. shield, code, cloud, cpu, terminal',
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Article Category'
        verbose_name_plural = 'Article Categories'

    def __str__(self):
        return self.name


class Article(BaseModel):
    """
    Technical tutorial, cheatsheet, or developer guide in THUTA Knowledge Hub.
    Functions as an organic educational funnel connecting articles to structured courses.
    """

    class Difficulty(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authored_articles',
    )
    category = models.ForeignKey(
        ArticleCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
    )
    summary = models.TextField(
        max_length=500,
        help_text='Short excerpt displayed on catalog cards and SEO meta tags.',
    )
    content = models.TextField(
        help_text='Full Markdown or structured article tutorial content.',
    )
    cover_image = models.ImageField(upload_to='blog/covers/', null=True, blank=True)
    reading_time_minutes = models.PositiveSmallIntegerField(
        default=5,
        help_text='Estimated reading duration in minutes.',
    )
    difficulty = models.CharField(
        max_length=16,
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
        db_index=True,
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text='Comma-separated tags e.g. python, django, ctf, devops',
    )
    related_course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_articles',
        help_text='Promotional course funnel linking this article to a comprehensive curriculum.',
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Featured articles appear at the top of the Knowledge Hub.',
    )
    is_published = models.BooleanField(default=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-is_featured', '-published_at', '-created_at']
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def reading_time_display(self):
        return f"{self.reading_time_minutes} min read"
