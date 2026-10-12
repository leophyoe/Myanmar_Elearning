import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel


class Conversation(BaseModel):
    """
    Direct one-to-one conversation between two authorized users.
    Can be optionally anchored to an academic course context.
    """
    course = models.ForeignKey(
        'courses.Course',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chat_conversations',
        help_text="Optional academic course context for student-instructor inquiries."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_conversations'
    )
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        return f"Conversation {self.id}"

    def get_other_participant(self, user):
        """Returns the other user in this direct 1-to-1 conversation."""
        membership = self.participants.exclude(user=user).select_related('user').first()
        return membership.user if membership else None

    def get_latest_message(self):
        """Returns the most recent message in the conversation."""
        return self.messages.order_by('-created_at').first()

    def get_unread_count(self, user):
        """Returns unread message count for the given participant."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    @classmethod
    def get_or_create_direct(cls, user_a, user_b, course=None):
        """
        Finds existing 1-to-1 conversation between user_a and user_b,
        or creates a new one with ConversationParticipant entries for both.
        """
        # Search existing conversations containing both participants
        conversations = cls.objects.filter(
            participants__user=user_a
        ).filter(
            participants__user=user_b
        )
        if course:
            course_matched = conversations.filter(course=course).first()
            if course_matched:
                return course_matched, False

        direct = conversations.first()
        if direct:
            return direct, False

        # Create new
        convo = cls.objects.create(
            created_by=user_a,
            course=course,
            last_message_at=timezone.now()
        )
        ConversationParticipant.objects.create(conversation=convo, user=user_a)
        ConversationParticipant.objects.create(conversation=convo, user=user_b)
        return convo, True


class ConversationParticipant(BaseModel):
    """
    Junction record between a Conversation and a participating User.
    Stores per-user read markers, mute settings, and archive states.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_participations'
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('conversation', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} in {self.conversation_id}"


class Message(BaseModel):
    """
    Persistent text message within a Conversation.
    Includes client idempotency key for network deduplication and read markers.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_chat_messages'
    )
    content = models.TextField(help_text="Plaintext message payload")
    client_message_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Client deduplication / idempotency key"
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Msg from {self.sender.username} at {self.created_at}"


class UserBlock(BaseModel):
    """
    User-level block preventing two users from messaging each other.
    """
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_users'
    )
    blocked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_by_users'
    )
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('blocker', 'blocked_user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.blocker.username} blocked {self.blocked_user.username}"


class MessageReport(BaseModel):
    """
    Abuse report filed against an inappropriate or abusive message.
    Moderation queue enables administrators to review reported incidents
    without having blanket access to eavesdrop on private chats.
    """
    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam / Advertising'
        HARASSMENT = 'harassment', 'Harassment / Abuse'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate Content'
        OTHER = 'other', 'Other Violation'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        RESOLVED = 'resolved', 'Resolved / Action Taken'
        DISMISSED = 'dismissed', 'Dismissed'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_message_reports'
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    reason = models.CharField(
        max_length=32,
        choices=Reason.choices,
        default=Reason.HARASSMENT,
        db_index=True
    )
    details = models.TextField(blank=True, help_text="Additional explanation from reporter")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_chat_reports'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report #{self.id} on Message {self.message_id} by {self.reporter.username}"

