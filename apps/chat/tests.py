import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from channels.testing import WebsocketCommunicator

from apps.courses.models import Course, Enrollment, Subject
from apps.partner.models import Institution, InstitutionCohort, CohortStudent
from apps.chat.models import Conversation, ConversationParticipant, Message, UserBlock, MessageReport
from apps.chat.permissions import can_user_message, can_access_conversation, get_allowed_recipients
from apps.chat.services import (
    send_message,
    sanitize_content,
    check_rate_limit,
    RateLimitExceeded,
    MessageValidationError,
    PermissionDeniedError,
)
from apps.chat.consumers import ChatConsumer

User = get_user_model()


class ChatModelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(
            username='instructor_bob',
            email='bob@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@thuta.edu',
            password='Password123!',
            role='student'
        )

    def test_conversation_creation_and_methods(self):
        convo, created = Conversation.get_or_create_direct(self.teacher, self.student)
        self.assertTrue(created)
        self.assertEqual(convo.participants.count(), 2)
        self.assertEqual(convo.get_other_participant(self.teacher), self.student)
        self.assertEqual(convo.get_other_participant(self.student), self.teacher)

        # Re-fetch returns existing
        convo2, created2 = Conversation.get_or_create_direct(self.student, self.teacher)
        self.assertFalse(created2)
        self.assertEqual(convo.id, convo2.id)

    def test_message_creation_and_unread_count(self):
        convo, _ = Conversation.get_or_create_direct(self.teacher, self.student)
        msg1 = Message.objects.create(
            conversation=convo,
            sender=self.teacher,
            content="Welcome to the course, Alice!",
            client_message_id="msg_001"
        )
        self.assertEqual(convo.get_latest_message(), msg1)
        self.assertEqual(convo.get_unread_count(self.student), 1)
        self.assertEqual(convo.get_unread_count(self.teacher), 0)

        # Mark read
        msg1.is_read = True
        msg1.read_at = timezone.now()
        msg1.save()
        self.assertEqual(convo.get_unread_count(self.student), 0)

    def test_user_block_and_report_models(self):
        block = UserBlock.objects.create(
            blocker=self.student,
            blocked_user=self.teacher,
            reason="Unwanted messages"
        )
        self.assertIn("blocked", str(block))

        convo, _ = Conversation.get_or_create_direct(self.teacher, self.student)
        msg = Message.objects.create(conversation=convo, sender=self.teacher, content="Test report")
        report = MessageReport.objects.create(
            reporter=self.student,
            message=msg,
            reason=MessageReport.Reason.HARASSMENT,
            details="Offensive language"
        )
        self.assertEqual(report.status, MessageReport.Status.PENDING)


class ChatPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='admin_thuta',
            email='admin@thuta.edu',
            password='Password123!',
            role='admin'
        )
        self.teacher1 = User.objects.create_user(
            username='teacher_bob',
            email='bob@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.teacher2 = User.objects.create_user(
            username='teacher_clara',
            email='clara@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.student1 = User.objects.create_user(
            username='student_alice',
            email='alice@thuta.edu',
            password='Password123!',
            role='student'
        )
        self.student2 = User.objects.create_user(
            username='student_dave',
            email='dave@thuta.edu',
            password='Password123!',
            role='student'
        )

        # Course owned by teacher1
        self.course = Course.objects.create(
            title="Cyber Defense 101",
            slug="cyber-defense-101",
            description="Introductory course",
            owner=self.teacher1,
            is_published=True
        )

    def test_cannot_message_self(self):
        allowed, reason = can_user_message(self.student1, self.student1)
        self.assertFalse(allowed)

    def test_blocked_users_cannot_message(self):
        UserBlock.objects.create(blocker=self.teacher1, blocked_user=self.student1)
        allowed, reason = can_user_message(self.student1, self.teacher1)
        self.assertFalse(allowed)

        # Reverse check
        allowed2, _ = can_user_message(self.teacher1, self.student1)
        self.assertFalse(allowed2)

    def test_student_can_only_message_enrolled_instructor(self):
        # Before enrollment: cannot message teacher1
        allowed, _ = can_user_message(self.student1, self.teacher1)
        self.assertFalse(allowed)

        # After active enrollment in teacher1's course: ALLOWED
        Enrollment.objects.create(
            course=self.course,
            student=self.student1,
            status=Enrollment.Status.ACTIVE
        )
        allowed, _ = can_user_message(self.student1, self.teacher1)
        self.assertTrue(allowed)

        # Student CANNOT message teacher2 (not enrolled in teacher2's courses)
        allowed_t2, _ = can_user_message(self.student1, self.teacher2)
        self.assertFalse(allowed_t2)

        # Student CANNOT message random student2
        allowed_s2, _ = can_user_message(self.student1, self.student2)
        self.assertFalse(allowed_s2)

    def test_teacher_permissions(self):
        # Teacher can message fellow teacher
        allowed_faculty, _ = can_user_message(self.teacher1, self.teacher2)
        self.assertTrue(allowed_faculty)

        # Teacher cannot message unenrolled student2
        allowed_s2, _ = can_user_message(self.teacher1, self.student2)
        self.assertFalse(allowed_s2)

        # Teacher can message enrolled student1
        Enrollment.objects.create(
            course=self.course,
            student=self.student1,
            status=Enrollment.Status.ACTIVE
        )
        allowed_s1, _ = can_user_message(self.teacher1, self.student1)
        self.assertTrue(allowed_s1)

    def test_admin_privacy_barrier(self):
        """
        Privacy-first rule:
        Administrators do NOT have blanket permission to read private student-teacher chats
        unless they are explicitly added as participants.
        """
        convo, _ = Conversation.get_or_create_direct(self.teacher1, self.student1)
        self.assertTrue(can_access_conversation(self.teacher1, convo))
        self.assertTrue(can_access_conversation(self.student1, convo))

        # Admin is NOT a participant, so access is denied
        self.assertFalse(can_access_conversation(self.admin, convo))

    def test_partner_permissions(self):
        partner_user = User.objects.create_user(
            username='partner_univ',
            email='univ@partner.edu',
            password='Password123!',
            role='partner'
        )
        institution = Institution.objects.create(
            name="Yangon Tech Academy",
            slug="yta",
            contact_person=partner_user
        )
        cohort = InstitutionCohort.objects.create(
            institution=institution,
            name="Cohort 2026",
            code="YTA-2026-A",
            course=self.course
        )
        CohortStudent.objects.create(cohort=cohort, student=self.student1)

        # Partner can message student in their cohort
        allowed, _ = can_user_message(partner_user, self.student1)
        self.assertTrue(allowed)

        # Partner cannot message unrelated student2
        allowed_unrelated, _ = can_user_message(partner_user, self.student2)
        self.assertFalse(allowed_unrelated)


class ChatServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(
            username='instructor_bob',
            email='bob@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@thuta.edu',
            password='Password123!',
            role='student'
        )
        self.course = Course.objects.create(
            title="Course 101",
            slug="course-101",
            description="Desc",
            owner=self.teacher,
            is_published=True
        )
        Enrollment.objects.create(
            course=self.course,
            student=self.student,
            status=Enrollment.Status.ACTIVE
        )
        self.convo, _ = Conversation.get_or_create_direct(self.teacher, self.student)

    def test_sanitize_content(self):
        with self.assertRaises(MessageValidationError):
            sanitize_content("")
        with self.assertRaises(MessageValidationError):
            sanitize_content("   ")
        with self.assertRaises(MessageValidationError):
            sanitize_content("a" * 4001)

        cleaned = sanitize_content("  Hello world!\x00  ")
        self.assertEqual(cleaned, "Hello world!")

    def test_rate_limiting(self):
        user_id = self.student.id
        for _ in range(30):
            check_rate_limit(user_id)

        with self.assertRaises(RateLimitExceeded):
            check_rate_limit(user_id)

    def test_idempotent_send_message(self):
        msg1, created1 = send_message(
            sender=self.student,
            conversation=self.convo,
            content="Hello teacher",
            client_message_id="cli_123"
        )
        self.assertTrue(created1)

        # Sending same client_message_id returns existing message without duplicate
        msg2, created2 = send_message(
            sender=self.student,
            conversation=self.convo,
            content="Hello teacher",
            client_message_id="cli_123"
        )
        self.assertFalse(created2)
        self.assertEqual(msg1.id, msg2.id)
        self.assertEqual(Message.objects.filter(conversation=self.convo).count(), 1)


class ChatViewsAndAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='instructor_bob',
            email='bob@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@thuta.edu',
            password='Password123!',
            role='student'
        )
        self.unrelated_student = User.objects.create_user(
            username='student_stranger',
            email='stranger@thuta.edu',
            password='Password123!',
            role='student'
        )

        self.course = Course.objects.create(
            title="Network Security",
            slug="network-security",
            description="Course desc",
            owner=self.teacher,
            is_published=True
        )
        Enrollment.objects.create(
            course=self.course,
            student=self.student,
            status=Enrollment.Status.ACTIVE
        )

    def test_inbox_view_requires_login(self):
        resp = self.client.get(reverse('chat:inbox'))
        self.assertEqual(resp.status_code, 302)

    def test_inbox_view_authenticated(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse('chat:inbox'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "THUTA Messenger")

    def test_start_conversation_success_and_forbidden(self):
        self.client.force_login(self.student)

        # Student starts conversation with enrolled instructor: ALLOWED (redirects to inbox with convo ID)
        resp = self.client.post(reverse('chat:start-conversation', kwargs={'recipient_id': self.teacher.id}))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("c=", resp.url)

        # Student tries to message unrelated student: FORBIDDEN 403
        resp_bad = self.client.post(reverse('chat:start-conversation', kwargs={'recipient_id': self.unrelated_student.id}))
        self.assertEqual(resp_bad.status_code, 403)

    def test_send_and_fetch_messages_api(self):
        convo, _ = Conversation.get_or_create_direct(self.student, self.teacher)
        self.client.force_login(self.student)

        # Send message via REST API
        resp = self.client.post(
            reverse('chat:api-send-message', kwargs={'conversation_id': convo.id}),
            data=json.dumps({'content': 'Good morning Teacher Bob', 'client_message_id': 'c_1001'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['message']['content'], 'Good morning Teacher Bob')

        # Fetch messages via API
        resp_fetch = self.client.get(reverse('chat:api-messages', kwargs={'conversation_id': convo.id}))
        self.assertEqual(resp_fetch.status_code, 200)
        self.assertEqual(len(resp_fetch.json()['messages']), 1)

        # Non-participant gets 403
        self.client.force_login(self.unrelated_student)
        resp_denied = self.client.get(reverse('chat:api-messages', kwargs={'conversation_id': convo.id}))
        self.assertEqual(resp_denied.status_code, 403)

    def test_mark_read_and_unread_count_api(self):
        convo, _ = Conversation.get_or_create_direct(self.student, self.teacher)
        Message.objects.create(
            conversation=convo,
            sender=self.teacher,
            content="Check chapter 2."
        )

        self.client.force_login(self.student)
        # Check unread count API
        resp_count = self.client.get(reverse('chat:api-unread-count'))
        self.assertEqual(resp_count.status_code, 200)
        self.assertEqual(resp_count.json()['unread_count'], 1)

        # Mark read
        resp_read = self.client.post(reverse('chat:api-mark-read', kwargs={'conversation_id': convo.id}))
        self.assertEqual(resp_read.status_code, 200)

        # Count should now be 0
        resp_count2 = self.client.get(reverse('chat:api-unread-count'))
        self.assertEqual(resp_count2.json()['unread_count'], 0)

    def test_block_user_toggle(self):
        self.client.force_login(self.student)
        resp = self.client.post(reverse('chat:block-user', kwargs={'user_id': self.teacher.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['action'], 'blocked')
        self.assertTrue(UserBlock.objects.filter(blocker=self.student, blocked_user=self.teacher).exists())

        # Unblock toggle
        resp2 = self.client.post(reverse('chat:block-user', kwargs={'user_id': self.teacher.id}))
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['action'], 'unblocked')
        self.assertFalse(UserBlock.objects.filter(blocker=self.student, blocked_user=self.teacher).exists())

    def test_report_message(self):
        convo, _ = Conversation.get_or_create_direct(self.student, self.teacher)
        msg = Message.objects.create(conversation=convo, sender=self.teacher, content="Inappropriate test")
        self.client.force_login(self.student)

        resp = self.client.post(
            reverse('chat:report-message', kwargs={'message_id': msg.id}),
            data={'reason': 'harassment', 'details': 'Report details'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MessageReport.objects.filter(message=msg, reporter=self.student).exists())


class ChatWebSocketConsumerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(
            username='instructor_bob',
            email='bob@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        self.student = User.objects.create_user(
            username='student_alice',
            email='alice@thuta.edu',
            password='Password123!',
            role='student'
        )
        self.course = Course.objects.create(
            title="Live Course",
            slug="live-course",
            description="Live class",
            owner=self.teacher,
            is_published=True
        )
        Enrollment.objects.create(
            course=self.course,
            student=self.student,
            status=Enrollment.Status.ACTIVE
        )
        self.convo, _ = Conversation.get_or_create_direct(self.student, self.teacher)

    async def test_websocket_connect_and_message_delivery(self):
        # Authenticated student communicator
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.convo.id}/"
        )
        communicator.scope['user'] = self.student
        communicator.scope['url_route'] = {'kwargs': {'conversation_id': str(self.convo.id)}}

        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        # Send chat message via WebSocket
        await communicator.send_json_to({
            'action': 'send_message',
            'conversation_id': str(self.convo.id),
            'content': 'Hello from WebSocket!',
            'client_message_id': 'ws_msg_101'
        })

        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'new_message')
        self.assertEqual(response['message']['content'], 'Hello from WebSocket!')
        self.assertTrue(response['message']['is_outgoing'])

        # Send mark read
        await communicator.send_json_to({
            'action': 'mark_read',
            'conversation_id': str(self.convo.id)
        })

        # Disconnect
        await communicator.disconnect()


class UserSearchAndBadgeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_boss',
            email='admin@thuta.edu',
            password='Password123!',
            role='admin'
        )
        self.teacher = User.objects.create_user(
            username='prof_smith',
            first_name='John',
            last_name='Smith',
            email='smith@thuta.edu',
            password='Password123!',
            role='teacher'
        )
        # Ensure teacher_profile exists and is verified
        if hasattr(self.teacher, 'teacher_profile') and self.teacher.teacher_profile:
            self.teacher.teacher_profile.is_verified = True
            self.teacher.teacher_profile.level = 'associate_instructor'
            self.teacher.teacher_profile.save()

        self.student = User.objects.create_user(
            username='student_kyaw',
            first_name='Kyaw',
            last_name='Zin',
            email='kyaw@thuta.edu',
            password='Password123!',
            role='student'
        )

        subject = Subject.objects.create(title='DevOps', slug='devops')
        self.course = Course.objects.create(
            title='DevOps Engineering',
            slug='devops-engineering',
            subject=subject,
            owner=self.teacher,
            status=Course.Status.PUBLISHED
        )
        Enrollment.objects.create(
            course=self.course,
            student=self.student,
            status=Enrollment.Status.ACTIVE
        )

    def test_verified_blue_mark(self):
        # Admin is verified
        self.assertTrue(self.admin.is_verified)
        # Verified teacher is verified
        self.assertTrue(self.teacher.is_verified)
        # Regular student is not verified
        self.assertFalse(self.student.is_verified)

    def test_member_level_display(self):
        self.assertEqual(self.admin.member_level_display, 'Administrator')
        self.assertEqual(self.teacher.member_level_display, 'Associate Instructor')
        self.assertEqual(self.student.member_level_display, 'Starter Member')

    def test_search_by_account_id_and_name(self):
        # Student searches for teacher by account_id
        teacher_account_id = self.teacher.account_id
        results_by_id = list(get_allowed_recipients(self.student, query=teacher_account_id))
        self.assertIn(self.teacher, results_by_id)

        # Student searches by name
        results_by_name = list(get_allowed_recipients(self.student, query='Smith'))
        self.assertIn(self.teacher, results_by_name)

    def test_eligible_recipients_api_returns_badges(self):
        self.client.force_login(self.student)
        url = reverse('chat:api-recipients')
        response = self.client.get(url, {'q': 'Smith'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(len(data['results']) >= 1)
        recipient_item = data['results'][0]
        self.assertEqual(recipient_item['username'], 'prof_smith')
        self.assertEqual(recipient_item['account_id'], self.teacher.account_id)
        self.assertTrue(recipient_item['is_verified'])
        self.assertEqual(recipient_item['member_level'], 'Associate Instructor')

    def test_block_and_unblock_user_toggle(self):
        self.client.force_login(self.student)
        url = reverse('chat:block-user', kwargs={'user_id': self.teacher.id})

        # Block
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['action'], 'blocked')
        self.assertTrue(UserBlock.objects.filter(blocker=self.student, blocked_user=self.teacher).exists())

        # Unblock
        resp2 = self.client.post(url)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['action'], 'unblocked')
        self.assertFalse(UserBlock.objects.filter(blocker=self.student, blocked_user=self.teacher).exists())


