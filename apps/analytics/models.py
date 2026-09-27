from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class ActivityAction(models.TextChoices):
    LOGIN = 'login', 'User Login'
    LOGOUT = 'logout', 'User Logout'
    LAB_START = 'lab_start', 'Lab Started'
    LAB_STOP = 'lab_stop', 'Lab Stopped'
    LAB_RESET = 'lab_reset', 'Lab Reset'
    FLAG_SUBMIT = 'flag_submit', 'Flag Submitted'
    QUIZ_SUBMIT = 'quiz_submit', 'Quiz Submitted'
    ASSIGNMENT_SUBMIT = 'assignment_submit', 'Assignment Submitted'
    PROFILE_UPDATE = 'profile_update', 'Profile Updated'


class ActivityLog(BaseModel):
    """
    Immutable audit trail logging all user and administrative actions.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=64, choices=ActivityAction.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    path = models.CharField(max_length=512, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {username} -> {self.get_action_display()}"


class SystemLogLevel(models.TextChoices):
    INFO = 'INFO', 'Info'
    WARNING = 'WARNING', 'Warning'
    ERROR = 'ERROR', 'Error'
    CRITICAL = 'CRITICAL', 'Critical'


class SystemLog(BaseModel):
    """
    Internal platform logs recording engine events, orchestration failures, and container health.
    """
    level = models.CharField(max_length=16, choices=SystemLogLevel.choices, default=SystemLogLevel.INFO, db_index=True)
    component = models.CharField(max_length=64, db_index=True)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.level}] {self.component}: {self.message[:60]}"

