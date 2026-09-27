import uuid
from django.db import models

class TimeStampedModel(models.Model):
    """Abstract model providing automatic creation and modification timestamps."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Abstract base model providing:
    - Non-sequential, cryptographically strong UUID4 primary keys
    - Creation and modification timestamps
    - Soft-deletion flag
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

