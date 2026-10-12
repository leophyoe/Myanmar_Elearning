import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.chat.models import Conversation, ConversationParticipant, Message
from apps.chat.permissions import can_access_conversation
from apps.chat.services import (
    send_message as service_send_message,
    serialize_message,
    RateLimitExceeded,
    MessageValidationError,
    PermissionDeniedError,
)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for THUTA Messenger.
    Handles real-time message sending, live read receipts, typing indicators,
    and user-specific unread badge updates.
    """

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4003)
            return

        self.user_group = f"chat_user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Check if connected to a specific conversation room
        self.conversation_id = self.scope.get('url_route', {}).get('kwargs', {}).get('conversation_id')
        self.room_group = None

        if self.conversation_id:
            has_access = await self.check_conversation_access(self.user, self.conversation_id)
            if not has_access:
                await self.close(code=4403)
                return
            self.room_group = f"chat_room_{self.conversation_id}"
            await self.channel_layer.group_add(self.room_group, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group') and self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if hasattr(self, 'room_group') and self.room_group:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON data.")
            return

        action = data.get('action')

        if action == 'send_message':
            await self.handle_send_message(data)
        elif action == 'mark_read':
            await self.handle_mark_read(data)
        elif action == 'typing':
            await self.handle_typing(data)
        elif action == 'join_room':
            await self.handle_join_room(data)
        else:
            await self.send_error(f"Unknown action: {action}")

    async def handle_join_room(self, data):
        new_conv_id = data.get('conversation_id')
        if not new_conv_id:
            return

        has_access = await self.check_conversation_access(self.user, new_conv_id)
        if not has_access:
            await self.send_error("Unauthorized conversation room.")
            return

        if self.room_group:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

        self.conversation_id = new_conv_id
        self.room_group = f"chat_room_{new_conv_id}"
        await self.channel_layer.group_add(self.room_group, self.channel_name)

        await self.send(text_data=json.dumps({
            'type': 'room_joined',
            'conversation_id': new_conv_id,
        }))

    async def handle_send_message(self, data):
        conversation_id = data.get('conversation_id') or self.conversation_id
        content = data.get('content', '')
        client_message_id = data.get('client_message_id', '')

        if not conversation_id:
            await self.send_error("Missing conversation ID.")
            return

        try:
            msg_data, other_user_id, unread_count = await self.db_send_message(
                self.user, conversation_id, content, client_message_id
            )
        except (RateLimitExceeded, MessageValidationError, PermissionDeniedError) as err:
            await self.send_error(str(err))
            return
        except Exception:
            await self.send_error("Failed to deliver message. Please retry.")
            return

        room_group = f"chat_room_{conversation_id}"

        # Broadcast message to conversation room
        await self.channel_layer.group_send(
            room_group,
            {
                'type': 'chat_message_event',
                'message': msg_data,
            }
        )

        # Notify recipient's personal group
        if other_user_id:
            recipient_group = f"chat_user_{other_user_id}"
            await self.channel_layer.group_send(
                recipient_group,
                {
                    'type': 'chat_notification_event',
                    'conversation_id': conversation_id,
                    'unread_count': unread_count,
                    'latest_message': msg_data['content'],
                    'sender_name': msg_data['sender_name'],
                }
            )

    async def handle_mark_read(self, data):
        conversation_id = data.get('conversation_id') or self.conversation_id
        if not conversation_id:
            return

        read_count, other_user_id = await self.db_mark_read(self.user, conversation_id)
        if read_count > 0:
            room_group = f"chat_room_{conversation_id}"
            await self.channel_layer.group_send(
                room_group,
                {
                    'type': 'chat_read_receipt_event',
                    'conversation_id': conversation_id,
                    'reader_id': str(self.user.id),
                    'read_at': timezone.now().isoformat(),
                }
            )

    async def handle_typing(self, data):
        conversation_id = data.get('conversation_id') or self.conversation_id
        is_typing = bool(data.get('is_typing', False))

        if not conversation_id:
            return

        room_group = f"chat_room_{conversation_id}"
        await self.channel_layer.group_send(
            room_group,
            {
                'type': 'chat_typing_event',
                'conversation_id': conversation_id,
                'user_id': str(self.user.id),
                'username': self.user.username,
                'is_typing': is_typing,
            }
        )

    # Group Event Handlers
    async def chat_message_event(self, event):
        msg = event['message']
        # Compute outgoing flag relative to current connection's user
        outgoing = (msg['sender_id'] == str(self.user.id))
        payload = dict(msg)
        payload['is_outgoing'] = outgoing
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': payload,
        }))

    async def chat_read_receipt_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'conversation_id': event['conversation_id'],
            'reader_id': event['reader_id'],
            'read_at': event['read_at'],
        }))

    async def chat_typing_event(self, event):
        if event['user_id'] != str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'conversation_id': event['conversation_id'],
                'username': event['username'],
                'is_typing': event['is_typing'],
            }))

    async def chat_notification_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'conversation_id': event['conversation_id'],
            'unread_count': event['unread_count'],
            'latest_message': event['latest_message'],
            'sender_name': event['sender_name'],
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
        }))

    # Database Helpers
    @database_sync_to_async
    def check_conversation_access(self, user, conversation_id):
        try:
            convo = Conversation.objects.get(id=conversation_id)
            return can_access_conversation(user, convo)
        except (Conversation.DoesNotExist, ValueError):
            return False

    @database_sync_to_async
    def db_send_message(self, sender, conversation_id, content, client_message_id):
        convo = Conversation.objects.get(id=conversation_id)
        msg, created = service_send_message(
            sender=sender,
            conversation=convo,
            content=content,
            client_message_id=client_message_id
        )
        serialized = serialize_message(msg, current_user=sender)
        other_user = convo.get_other_participant(sender)
        other_id = str(other_user.id) if other_user else None
        unread_count = convo.get_unread_count(other_user) if other_user else 0
        return serialized, other_id, unread_count

    @database_sync_to_async
    def db_mark_read(self, user, conversation_id):
        try:
            convo = Conversation.objects.get(id=conversation_id)
            if not can_access_conversation(user, convo):
                return 0, None

            now = timezone.now()
            unread_msgs = Message.objects.filter(
                conversation=convo,
                is_read=False
            ).exclude(sender=user)
            count = unread_msgs.update(is_read=True, read_at=now)

            ConversationParticipant.objects.filter(
                conversation=convo,
                user=user
            ).update(last_read_at=now)

            other = convo.get_other_participant(user)
            other_id = str(other.id) if other else None
            return count, other_id
        except (Conversation.DoesNotExist, ValueError):
            return 0, None

