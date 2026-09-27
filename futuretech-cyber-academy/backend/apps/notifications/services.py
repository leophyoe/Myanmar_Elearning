import logging
from django.utils import timezone
from .models import Notification, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    @classmethod
    def create_notification(cls, recipient, title, message, notification_type=NotificationType.INFO, link=""):
        """Creates a single in-app notification."""
        try:
            return Notification.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None

    @classmethod
    def mark_as_read(cls, notification_id, user):
        """Marks a notification as read if it belongs to the user."""
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save(update_fields=['is_read', 'read_at'])
            return True
        except Notification.DoesNotExist:
            return False

    @classmethod
    def mark_all_as_read(cls, user):
        """Marks all unread notifications for a user as read."""
        return Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )

