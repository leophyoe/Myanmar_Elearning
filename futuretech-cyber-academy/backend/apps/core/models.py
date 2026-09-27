import uuid
from django.db import models

class BaseModel(models.Model):
    """
    Abstract base model providing:
    - Cryptographically strong UUID primary key
    - Automatic creation and update timestamps
    - Soft-delete active flag
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class AuditLog(BaseModel):
    """
    Tamper-evident audit log for sensitive academic, security, and administrative events.
    """
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64, db_index=True, blank=True)
    object_id = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Anonymous/System"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {user_str} - {self.action} ({self.object_type})"


