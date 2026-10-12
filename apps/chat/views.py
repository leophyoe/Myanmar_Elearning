import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Q, Max
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.courses.models import Course
from apps.chat.models import Conversation, ConversationParticipant, Message, UserBlock, MessageReport
from apps.chat.permissions import can_user_message, can_access_conversation, get_allowed_recipients
from apps.chat.services import (
    send_message as service_send_message,
    serialize_message,
    RateLimitExceeded,
    MessageValidationError,
    PermissionDeniedError,
)

User = get_user_model()


class InboxView(LoginRequiredMixin, View):
    """
    Primary two-panel Messenger interface for THUTA LMS.
    Renders conversations list, unread counters, and active conversation thread.
    """
    def get(self, request):
        user = request.user
        convo_id = request.GET.get('c')

        # Load user conversations ordered by last message time
        participations = ConversationParticipant.objects.filter(
            user=user,
            is_archived=False
        ).select_related('conversation', 'conversation__course').prefetch_related(
            'conversation__participants__user',
            'conversation__participants__user__teacher_profile',
            'conversation__participants__user__subscriptions__plan',
            'conversation__messages'
        )

        conversations_data = []
        active_conversation = None
        active_recipient = None
        active_messages = []
        is_blocked_by_me = False
        is_blocked_by_other = False

        for part in participations:
            convo = part.conversation
            other_user = convo.get_other_participant(user)
            if not other_user:
                continue

            latest_msg = convo.get_latest_message()
            unread_count = convo.get_unread_count(user)

            is_active = (str(convo.id) == str(convo_id))

            convo_item = {
                'id': str(convo.id),
                'other_user': other_user,
                'course': convo.course,
                'latest_message': latest_msg,
                'unread_count': unread_count,
                'last_message_at': convo.last_message_at or convo.created_at,
                'is_active': is_active,
            }
            conversations_data.append(convo_item)

            if is_active:
                active_conversation = convo
                active_recipient = other_user

        # If no active conversation chosen but conversations exist, default to the first one on desktop
        # On mobile, we only activate if ?c= is specified
        if not active_conversation and convo_id:
            try:
                requested_convo = Conversation.objects.get(id=convo_id)
                if can_access_conversation(user, requested_convo):
                    active_conversation = requested_convo
                    active_recipient = requested_convo.get_other_participant(user)
            except (Conversation.DoesNotExist, ValueError):
                pass

        if active_conversation and active_recipient:
            # Check blocks
            is_blocked_by_me = UserBlock.objects.filter(blocker=user, blocked_user=active_recipient).exists()
            is_blocked_by_other = UserBlock.objects.filter(blocker=active_recipient, blocked_user=user).exists()

            # Mark messages read
            now = timezone.now()
            Message.objects.filter(
                conversation=active_conversation,
                is_read=False
            ).exclude(sender=user).update(is_read=True, read_at=now)
            ConversationParticipant.objects.filter(
                conversation=active_conversation,
                user=user
            ).update(last_read_at=now)

            # Broadcast read receipt via Channels
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"chat_room_{active_conversation.id}",
                    {
                        'type': 'chat_read_receipt_event',
                        'conversation_id': str(active_conversation.id),
                        'reader_id': str(user.id),
                        'read_at': now.isoformat(),
                    }
                )

            # Load message history (latest 100 messages)
            messages_qs = Message.objects.filter(
                conversation=active_conversation
            ).select_related('sender').order_by('created_at')[:100]
            active_messages = [serialize_message(m, current_user=user) for m in messages_qs]

        # Allowed recipients for "Start New Chat" modal
        recipients = get_allowed_recipients(user)

        context = {
            'conversations': conversations_data,
            'active_conversation': active_conversation,
            'active_recipient': active_recipient,
            'active_messages': active_messages,
            'is_blocked_by_me': is_blocked_by_me,
            'is_blocked_by_other': is_blocked_by_other,
            'recipients': recipients,
            'total_unread_count': sum(c['unread_count'] for c in conversations_data),
        }
        return render(request, 'chat/inbox.html', context)


class StartConversationView(LoginRequiredMixin, View):
    """
    Initiates or opens a 1-to-1 conversation with an authorized user.
    Enforces role-based contact permissions.
    """
    def post(self, request, recipient_id=None):
        target_id = recipient_id or request.POST.get('recipient_id')
        course_id = request.POST.get('course_id')

        if not target_id:
            return JsonResponse({'status': 'error', 'message': 'Recipient is required.'}, status=400)

        recipient = get_object_or_404(User, id=target_id)
        course = None
        if course_id:
            course = Course.objects.filter(id=course_id).first()

        allowed, reason = can_user_message(request.user, recipient, course=course)
        if not allowed:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': reason}, status=403)
            return render(request, 'chat/permission_denied.html', {'reason': reason}, status=403)

        convo, created = Conversation.get_or_create_direct(request.user, recipient, course=course)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'success',
                'conversation_id': str(convo.id),
                'redirect_url': f"{reverse('chat:inbox')}?c={convo.id}",
                'created': created
            })

        return redirect(f"{reverse('chat:inbox')}?c={convo.id}")

    def get(self, request, recipient_id):
        return self.post(request, recipient_id=recipient_id)


class ConversationMessagesAPIView(LoginRequiredMixin, View):
    """
    Returns message history for a conversation.
    """
    def get(self, request, conversation_id):
        convo = get_object_or_404(Conversation, id=conversation_id)
        if not can_access_conversation(request.user, convo):
            return HttpResponseForbidden("Access denied to conversation.")

        messages_qs = Message.objects.filter(
            conversation=convo
        ).select_related('sender').order_by('created_at')[:100]

        data = [serialize_message(m, current_user=request.user) for m in messages_qs]
        return JsonResponse({
            'status': 'success',
            'conversation_id': str(convo.id),
            'messages': data,
        })


class SendMessageAPIView(LoginRequiredMixin, View):
    """
    REST fallback endpoint to send a message within a conversation.
    Synchronously records message and broadcasts through Django Channels.
    """
    def post(self, request, conversation_id):
        convo = get_object_or_404(Conversation, id=conversation_id)
        if not can_access_conversation(request.user, convo):
            return HttpResponseForbidden("Access denied.")

        try:
            if request.content_type == 'application/json':
                payload = json.loads(request.body.decode('utf-8'))
                content = payload.get('content', '')
                client_message_id = payload.get('client_message_id', '')
            else:
                content = request.POST.get('content', '')
                client_message_id = request.POST.get('client_message_id', '')

            msg, created = service_send_message(
                sender=request.user,
                conversation=convo,
                content=content,
                client_message_id=client_message_id
            )

            serialized = serialize_message(msg, current_user=request.user)

            # Broadcast over Channel Layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"chat_room_{convo.id}",
                    {
                        'type': 'chat_message_event',
                        'message': serialized,
                    }
                )

                other = convo.get_other_participant(request.user)
                if other:
                    unread_count = convo.get_unread_count(other)
                    async_to_sync(channel_layer.group_send)(
                        f"chat_user_{other.id}",
                        {
                            'type': 'chat_notification_event',
                            'conversation_id': str(convo.id),
                            'unread_count': unread_count,
                            'latest_message': serialized['content'],
                            'sender_name': serialized['sender_name'],
                        }
                    )

            return JsonResponse({'status': 'success', 'message': serialized})

        except (RateLimitExceeded, MessageValidationError, PermissionDeniedError) as err:
            return JsonResponse({'status': 'error', 'message': str(err)}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'Internal delivery failure.'}, status=500)


class MarkReadAPIView(LoginRequiredMixin, View):
    """
    Marks messages as read in a conversation.
    """
    def post(self, request, conversation_id):
        convo = get_object_or_404(Conversation, id=conversation_id)
        if not can_access_conversation(request.user, convo):
            return HttpResponseForbidden("Access denied.")

        now = timezone.now()
        count = Message.objects.filter(
            conversation=convo,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True, read_at=now)

        ConversationParticipant.objects.filter(
            conversation=convo,
            user=request.user
        ).update(last_read_at=now)

        channel_layer = get_channel_layer()
        if channel_layer and count > 0:
            async_to_sync(channel_layer.group_send)(
                f"chat_room_{convo.id}",
                {
                    'type': 'chat_read_receipt_event',
                    'conversation_id': str(convo.id),
                    'reader_id': str(request.user.id),
                    'read_at': now.isoformat(),
                }
            )

        return JsonResponse({'status': 'success', 'read_count': count})


class UnreadCountAPIView(LoginRequiredMixin, View):
    """
    Returns total unread count for current user across all active conversations.
    """
    def get(self, request):
        user = request.user
        unread_count = Message.objects.filter(
            conversation__participants__user=user,
            is_read=False
        ).exclude(sender=user).count()

        return JsonResponse({
            'status': 'success',
            'unread_count': unread_count
        })


class EligibleRecipientsAPIView(LoginRequiredMixin, View):
    """
    Returns users the current user is permitted to start a conversation with.
    Supports search by Name, Account ID, Username, Email, and Role.
    """
    def get(self, request):
        q = request.GET.get('q', '').strip()
        users = get_allowed_recipients(request.user, query=q)

        results = []
        for u in users:
            results.append({
                'id': str(u.id),
                'username': u.username,
                'name': u.get_full_name() or u.username,
                'account_id': getattr(u, 'account_id', '') or '',
                'role': getattr(u, 'role', ''),
                'role_display': u.get_role_display() if hasattr(u, 'get_role_display') else getattr(u, 'role', ''),
                'member_level': getattr(u, 'member_level_display', ''),
                'is_verified': bool(getattr(u, 'is_verified', False)),
                'avatar_url': u.avatar.url if getattr(u, 'avatar', None) else None,
                'initials': (u.username[:2]).upper(),
                'start_url': reverse('chat:start-conversation', kwargs={'recipient_id': u.id}),
            })

        return JsonResponse({'status': 'success', 'results': results})


class BlockUserView(LoginRequiredMixin, View):
    """
    Blocks or unblocks a user.
    """
    def post(self, request, user_id):
        target = get_object_or_404(User, id=user_id)
        if target.id == request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Cannot block yourself.'}, status=400)

        existing = UserBlock.objects.filter(blocker=request.user, blocked_user=target).first()
        if existing:
            existing.delete()
            return JsonResponse({'status': 'success', 'action': 'unblocked', 'message': f'Unblocked {target.username}'})
        else:
            reason = request.POST.get('reason', '')
            UserBlock.objects.create(blocker=request.user, blocked_user=target, reason=reason)
            return JsonResponse({'status': 'success', 'action': 'blocked', 'message': f'Blocked {target.username}'})


class ReportMessageView(LoginRequiredMixin, View):
    """
    Files an abuse or harassment report for a message.
    """
    def post(self, request, message_id):
        msg = get_object_or_404(Message, id=message_id)
        # Verify reporter has access to the conversation of the message
        if not can_access_conversation(request.user, msg.conversation):
            return HttpResponseForbidden("Access denied.")

        reason = request.POST.get('reason', MessageReport.Reason.HARASSMENT)
        details = request.POST.get('details', '')

        report, created = MessageReport.objects.get_or_create(
            reporter=request.user,
            message=msg,
            defaults={'reason': reason, 'details': details}
        )

        return JsonResponse({
            'status': 'success',
            'report_id': str(report.id),
            'message': 'Report received. Our moderation team will review this message.'
        })

