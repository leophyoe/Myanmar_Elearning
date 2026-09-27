from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class BadgeType(models.TextChoices):
    BRONZE = 'BRONZE', 'Bronze'
    SILVER = 'SILVER', 'Silver'
    GOLD = 'GOLD', 'Gold'
    PLATINUM = 'PLATINUM', 'Platinum'


class Achievement(BaseModel):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    icon = models.CharField(max_length=64, default="award", help_text="Lucide icon identifier")
    badge_type = models.CharField(max_length=32, choices=BadgeType.choices, default=BadgeType.BRONZE)
    points = models.PositiveIntegerField(default=10)
    criteria_type = models.CharField(max_length=64, default="EVENT")

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"[{self.badge_type}] {self.title} ({self.points} pts)"


class StudentAchievement(BaseModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='awarded_students')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('student', 'achievement')]
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.student.username} earned {self.achievement.title}"

