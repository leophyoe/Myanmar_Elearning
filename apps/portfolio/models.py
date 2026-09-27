from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Skill(BaseModel):
    """A competency shown on the owner's public portfolio."""

    class Category(models.TextChoices):
        TECHNICAL = 'technical', 'Technical'
        TOOLS = 'tools', 'Tools & Platforms'
        SECURITY = 'security', 'Security'
        SOFT = 'soft', 'Soft skills'
        LANGUAGE = 'language', 'Languages'
        OTHER = 'other', 'Other'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skills'
    )
    name = models.CharField(max_length=64)
    category = models.CharField(
        max_length=16, choices=Category.choices, default=Category.TECHNICAL, db_index=True
    )
    level = models.PositiveSmallIntegerField(
        default=3,
        help_text="1 (aware) to 5 (expert).",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'category', 'name']
        unique_together = [('owner', 'name')]

    def __str__(self):
        return f'{self.name} ({self.level}/5)'

    @property
    def level_pct(self):
        return max(0, min(int(self.level or 0), 5)) * 20


class PortfolioLink(BaseModel):
    """An outbound profile link — GitHub, LinkedIn, personal site, CV, ..."""

    class Kind(models.TextChoices):
        GITHUB = 'github', 'GitHub'
        LINKEDIN = 'linkedin', 'LinkedIn'
        WEBSITE = 'website', 'Website'
        CV = 'cv', 'CV / Résumé'
        YOUTUBE = 'youtube', 'YouTube'
        BLOG = 'blog', 'Blog'
        OTHER = 'other', 'Other'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolio_links'
    )
    kind = models.CharField(
        max_length=16, choices=Kind.choices, default=Kind.OTHER, db_index=True
    )
    label = models.CharField(
        max_length=48, blank=True,
        help_text="Shown next to the link. Defaults to the kind, e.g. “GitHub”.",
    )
    url = models.URLField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'kind']
        unique_together = [('owner', 'kind', 'url')]

    def __str__(self):
        return f'{self.owner.username}: {self.display_label}'

    @property
    def display_label(self):
        return self.label or self.get_kind_display()


class ExternalCertificate(BaseModel):
    """
    A credential earned outside the platform (vendor exam, university, employer).

    Students submit these; an administrator stamps `is_verified` after checking
    the issuer's own verification URL or the uploaded document.
    """

    class Meta:
        ordering = ['-issued_on', '-created_at']

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='external_certificates',
    )
    title = models.CharField(max_length=255)
    issuer = models.CharField(max_length=160)
    credential_id = models.CharField(
        max_length=128, blank=True,
        help_text="Badge / exam ID printed on the credential.",
    )
    credential_url = models.URLField(
        blank=True, help_text="Issuer's public verification link."
    )
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    document = models.FileField(
        upload_to='portfolio/certificates/', null=True, blank=True
    )
    note = models.TextField(blank=True)

    is_verified = models.BooleanField(default=False, db_index=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_external_certificates',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    def __str__(self):
        return f'{self.title} — {self.issuer} ({self.owner.username})'

    @property
    def is_expired(self):
        return bool(self.expires_on and self.expires_on < timezone.now().date())

    @property
    def status(self):
        if self.rejection_reason and not self.is_verified:
            return 'rejected'
        if self.is_verified:
            return 'expired' if self.is_expired else 'verified'
        return 'pending'
