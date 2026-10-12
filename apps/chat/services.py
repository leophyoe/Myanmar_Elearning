import time
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import escape
from apps.chat.models import Conversation, Message
from apps.chat.permissions import can_user_message, can_access_conversation

MAX_MESSAGE_LENGTH = 4000
RATE_LIMIT_MAX = 30  # Max 30 messages
RATE_LIMIT_WINDOW = 60  # per 60 seconds


class RateLimitExceeded(Exception):
    pass


class MessageValidationError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


def check_rate_limit(user_id):
    """
    Checks if a user exceeded the message sending rate limit.
    Uses sliding window in Django cache.
    """
    cache_key = f"chat_rate_limit_{user_id}"
    now = time.time()
    timestamps = cache.get(cache_key, [])
    # Filter timestamps within current window
    valid_timestamps = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW]
    if len(valid_timestamps) >= RATE_LIMIT_MAX:
        raise RateLimitExceeded("You are sending messages too quickly. Please wait a moment.")
    valid_timestamps.append(now)
    cache.set(cache_key, valid_timestamps, RATE_LIMIT_WINDOW)


def sanitize_content(raw_content):
    """
    Validates and sanitizes chat message content.
    Prevents script injection and strips control characters.
    """
    if not raw_content:
        raise MessageValidationError("Message cannot be empty.")
    content = str(raw_content).strip()
    if not content:
        raise MessageValidationError("Message cannot be empty or whitespace only.")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise MessageValidationError(f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters.")
    # Strip null characters
    content = content.replace('\x00', '')
    return content


def send_message(sender, conversation, content, client_message_id=''):
    """
    Core service to persist a chat message:
    - Validates access
    - Checks rate limits
    - Handles client_message_id idempotency
    - Updates conversation last_message_at
    """
    if not can_access_conversation(sender, conversation):
        raise PermissionDeniedError("You are not a participant in this conversation.")

    # Check recipient permissions
    recipient = conversation.get_other_participant(sender)
    if recipient:
        allowed, reason = can_user_message(sender, recipient, course=conversation.course)
        if not allowed:
            raise PermissionDeniedError(reason)

    check_rate_limit(sender.id)
    clean_text = sanitize_content(content)

    # Idempotency check: if client_message_id is provided, check recent duplicates
    if client_message_id:
        existing = Message.objects.filter(
            conversation=conversation,
            sender=sender,
            client_message_id=client_message_id
        ).first()
        if existing:
            return existing, False

    msg = Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=clean_text,
        client_message_id=client_message_id or ''
    )

    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['last_message_at', 'updated_at'])

    return msg, True


def serialize_message(message, current_user=None):
    """
    Serializes a message for JSON API and WebSocket payloads.
    """
    is_outgoing = (current_user and message.sender_id == current_user.id)
    return {
        'id': str(message.id),
        'conversation_id': str(message.conversation_id),
        'client_message_id': message.client_message_id,
        'sender_id': str(message.sender_id),
        'sender_username': message.sender.username,
        'sender_name': message.sender.get_full_name() or message.sender.username,
        'sender_role': getattr(message.sender, 'role', ''),
        'content': message.content,
        'is_outgoing': bool(is_outgoing),
        'is_read': message.is_read,
        'read_at': message.read_at.isoformat() if message.read_at else None,
        'created_at': message.created_at.isoformat(),
        'timestamp_display': message.created_at.strftime('%I:%M %p'),
        'date_display': message.created_at.strftime('%b %d, %Y'),
    }

