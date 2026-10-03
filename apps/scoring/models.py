from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class BadgeCriteriaType(models.TextChoices):
    POINTS_THRESHOLD = 'points_threshold', 'Total Points Reached'
    LABS_COMPLETED = 'labs_completed', 'Labs Completed Count'
    CHALLENGES_SOLVED = 'challenges_solved', 'CTF Challenges Solved Count'
    MODULE_COMPLETED = 'module_completed', 'Specific Module Completed'
    COURSES_COMPLETED = 'courses_completed', 'Courses Completed Count'
    PROJECTS_COMPLETED = 'projects_completed', 'Capstone Projects Completed Count'


class Badge(BaseModel):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=64, default="shield-check")
    criteria_type = models.CharField(max_length=32, choices=BadgeCriteriaType.choices)
    criteria_threshold = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['criteria_threshold']

    def __str__(self):
        return f"Badge: {self.name}"


class UserBadge(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_users')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'badge')]
        ordering = ['-awarded_at']

    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"


class ScoreSnapshot(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='score_snapshots')
    points = models.PositiveIntegerField()
    rank = models.PositiveIntegerField()
    snapshot_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'snapshot_date')]
        ordering = ['-snapshot_date', 'rank']

