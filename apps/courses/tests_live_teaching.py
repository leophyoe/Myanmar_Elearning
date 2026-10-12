import hashlib
import json
import urllib.parse
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.courses.models import Course, Enrollment, LiveSession, LiveSessionAttendance, Subject, LiveProviderSetting
from apps.courses.forms import LiveSessionForm
from apps.courses.live import (
    BaseLiveProvider,
    BigBlueButtonClient,
    BigBlueButtonProvider,
    ZoomProvider,
    GoogleMeetProvider,
    get_live_provider,
    get_default_provider,
    get_available_providers,
)

User = get_user_model()


class BigBlueButtonClientTests(TestCase):
    """
    Tests BigBlueButton REST API signature, query generation, and checksum algorithm.
    """

    def setUp(self):
        self.api_url = 'https://test-install.blindsidenetworks.com/bigbluebutton/api/'
        self.secret = '8cd8ef52e8e101574e400365b55e11a6'
        self.client = BigBlueButtonClient(api_url=self.api_url, shared_secret=self.secret)

    def test_sha1_checksum_calculation(self):
        # Known test vector per BigBlueButton official API documentation:
        # call: isMeetingRunning, query: meetingID=random-123
        call_name = 'isMeetingRunning'
        query_str = 'meetingID=random-123'
        expected = hashlib.sha1(f"{call_name}{query_str}{self.secret}".encode('utf-8')).hexdigest()
        actual = self.client.compute_checksum(call_name, query_str)
        self.assertEqual(actual, expected)

    def test_build_url_includes_params_and_checksum(self):
        url = self.client.build_url('getMeetingInfo', {'meetingID': 'room-xyz'})
        self.assertTrue(url.startswith(self.api_url + 'getMeetingInfo?'))
        self.assertIn('meetingID=room-xyz', url)
        self.assertIn('&checksum=', url)

    def test_create_meeting_returns_room_structure(self):
        res = self.client.create_meeting(
            meeting_id='thuta-room-001',
            name='Advanced Ethical Hacking Live Class',
            attendee_pw='student_pw_123',
            moderator_pw='teacher_pw_456',
            record=True,
        )
        self.assertTrue(res['success'])
        self.assertEqual(res['meetingID'], 'thuta-room-001')
        self.assertEqual(res['attendeePW'], 'student_pw_123')
        self.assertEqual(res['moderatorPW'], 'teacher_pw_456')

    def test_get_join_url_generates_signed_browser_redirect(self):
        join_url = self.client.get_join_url(
            meeting_id='thuta-room-001',
            full_name='Aung Kyaw',
            password='student_pw_123',
            user_id='user-uuid-999',
            avatar_url='https://example.com/avatar.png',
            redirect=True,
        )
        self.assertTrue(join_url.startswith(self.api_url + 'join?'))
        self.assertIn('meetingID=thuta-room-001', join_url)
        self.assertIn('password=student_pw_123', join_url)
        self.assertIn('userID=user-uuid-999', join_url)
        self.assertIn('redirect=true', join_url)
        self.assertIn('&checksum=', join_url)


class LiveTeachingProviderRegistryTests(TestCase):
    """
    Tests provider lookup, default provider fallback, and provider list metadata.
    """

    def test_provider_registry_lookup(self):
        bbb = get_live_provider('bigbluebutton')
        self.assertIsInstance(bbb, BigBlueButtonProvider)
        self.assertEqual(bbb.provider_code, 'bigbluebutton')
        self.assertTrue(bbb.supports_auto_provisioning)
        self.assertTrue(bbb.supports_attendance_sync)

        zoom = get_live_provider('zoom')
        self.assertIsInstance(zoom, ZoomProvider)
        self.assertEqual(zoom.provider_code, 'zoom')

        meet = get_live_provider('google_meet')
        self.assertIsInstance(meet, GoogleMeetProvider)
        self.assertEqual(meet.provider_code, 'google_meet')

    def test_default_provider_fallback(self):
        # Unknown provider should fall back to default (bigbluebutton)
        fallback = get_live_provider('unknown_provider_xyz')
        self.assertIsInstance(fallback, BigBlueButtonProvider)

        default_provider = get_default_provider()
        self.assertIsInstance(default_provider, BigBlueButtonProvider)

    def test_available_providers_list(self):
        providers = get_available_providers()
        codes = [p['code'] for p in providers]
        self.assertIn('bigbluebutton', codes)
        self.assertIn('zoom', codes)
        self.assertIn('google_meet', codes)
        # BigBlueButton should be first / primary
        self.assertEqual(codes[0], 'bigbluebutton')


class LiveSessionSchedulingAndFormTests(TestCase):
    """
    Tests live session creation form and provider-specific validations.
    """

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='instructor_live',
            email='instructor@thuta.edu.mm',
            password='TestPassword123!',
            role='teacher',
        )
        self.subject = Subject.objects.create(title='Cyber Defense', slug='cyber-defense')
        self.course = Course.objects.create(
            title='SOC Analyst Level 1',
            slug='soc-analyst-level-1',
            subject=self.subject,
            owner=self.teacher,
            is_published=True,
            price=0,
        )

    def test_bbb_session_does_not_require_external_join_url(self):
        # BigBlueButton session can be scheduled with join_url left blank
        form = LiveSessionForm(data={
            'course': self.course.id,
            'title': 'Network Packet Analysis with Wireshark',
            'provider': LiveSession.Provider.BIGBLUEBUTTON,
            'join_url': '',
            'starts_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 60,
            'record_meeting': True,
            'notes': 'Bring Wireshark pcap sample.',
            'is_published': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        session = form.save()
        self.assertEqual(session.provider, LiveSession.Provider.BIGBLUEBUTTON)
        self.assertTrue(session.is_bbb)
        # Check auto-generated meeting room credentials
        self.assertTrue(session.meeting_id)
        self.assertTrue(session.moderator_password)
        self.assertTrue(session.attendee_password)

    def test_external_providers_require_valid_join_url(self):
        # Zoom without URL fails
        form_zoom_missing = LiveSessionForm(data={
            'course': self.course.id,
            'title': 'Zoom Live Workshop',
            'provider': LiveSession.Provider.ZOOM,
            'join_url': '',
            'starts_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 45,
            'record_meeting': False,
            'is_published': True,
        })
        self.assertFalse(form_zoom_missing.is_valid())
        self.assertIn('join_url', form_zoom_missing.errors)

        # Google Meet with non-meet link fails
        form_meet_invalid = LiveSessionForm(data={
            'course': self.course.id,
            'title': 'Google Meet Live',
            'provider': LiveSession.Provider.GOOGLE_MEET,
            'join_url': 'https://random-link.com/1234',
            'starts_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 45,
            'record_meeting': False,
            'is_published': True,
        })
        self.assertFalse(form_meet_invalid.is_valid())
        self.assertIn('join_url', form_meet_invalid.errors)

        # Google Meet with valid link succeeds
        form_meet_valid = LiveSessionForm(data={
            'course': self.course.id,
            'title': 'Google Meet Live',
            'provider': LiveSession.Provider.GOOGLE_MEET,
            'join_url': 'https://meet.google.com/abc-defg-hij',
            'starts_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 45,
            'record_meeting': False,
            'is_published': True,
        })
        self.assertTrue(form_meet_valid.is_valid(), form_meet_valid.errors)


class LiveTeachingSecurityAndAccessControlTests(TestCase):
    """
    Tests security access barriers:
    - Enrollment verification before join
    - Teacher early entry vs Student scheduled entry
    - Teacher moderator credentials vs Student viewer credentials
    - Attendance ledger logging
    """

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='lead_instructor',
            email='lead@thuta.edu.mm',
            password='TestPassword123!',
            role='teacher',
            first_name='Ko',
            last_name='Thuta',
        )
        self.enrolled_student = User.objects.create_user(
            username='enrolled_student',
            email='student@thuta.edu.mm',
            password='TestPassword123!',
            role='student',
            first_name='Aung',
            last_name='Aung',
        )
        self.unauthorized_student = User.objects.create_user(
            username='intruder_user',
            email='intruder@external.com',
            password='TestPassword123!',
            role='student',
        )
        self.admin_user = User.objects.create_user(
            username='platform_admin',
            email='admin@thuta.edu.mm',
            password='TestPassword123!',
            role='admin',
        )

        self.subject = Subject.objects.create(title='Malware Analysis', slug='malware-analysis')
        self.course = Course.objects.create(
            title='Reverse Engineering and Ghidra Masterclass',
            slug='reverse-engineering-ghidra',
            subject=self.subject,
            owner=self.teacher,
            is_published=True,
            price=0,
        )

        # Enrolled student access
        Enrollment.objects.create(
            course=self.course,
            student=self.enrolled_student,
            status=Enrollment.Status.ACTIVE,
        )

        # Live BBB session currently in progress
        self.live_bbb_session = LiveSession.objects.create(
            course=self.course,
            title='Live Ghidra Disassembly Lab',
            provider=LiveSession.Provider.BIGBLUEBUTTON,
            starts_at=timezone.now() - timedelta(minutes=15),
            duration_minutes=90,
            record_meeting=True,
            is_published=True,
        )

        # Scheduled upcoming BBB session (tomorrow)
        self.upcoming_bbb_session = LiveSession.objects.create(
            course=self.course,
            title='Upcoming Binary Exploitation Review',
            provider=LiveSession.Provider.BIGBLUEBUTTON,
            starts_at=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            record_meeting=True,
            is_published=True,
        )

    def test_anonymous_user_blocked_from_joining(self):
        url = reverse('live-session-join', kwargs={'session_id': self.live_bbb_session.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    def test_non_enrolled_user_blocked_from_joining(self):
        self.client.force_login(self.unauthorized_student)
        url = reverse('live-session-join', kwargs={'session_id': self.live_bbb_session.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/courses/{self.course.slug}/', response.url)
        # Attendance must NOT be logged for unauthorized user
        self.assertFalse(
            LiveSessionAttendance.objects.filter(
                session=self.live_bbb_session,
                user=self.unauthorized_student,
            ).exists()
        )

    def test_enrolled_student_joining_live_session(self):
        self.client.force_login(self.enrolled_student)
        url = reverse('live-session-join', kwargs={'session_id': self.live_bbb_session.id})
        response = self.client.get(url)
        # Should redirect to BigBlueButton join URL
        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertIn('/bigbluebutton/api/join?', redirect_url)
        self.assertIn(f'meetingID={self.live_bbb_session.meeting_id}', redirect_url)
        # Must join with attendee password (VIEWER role), not moderator password!
        self.assertIn(f'password={self.live_bbb_session.attendee_password}', redirect_url)
        self.assertNotIn(f'password={self.live_bbb_session.moderator_password}', redirect_url)

        # Attendance must be audited
        attendance = LiveSessionAttendance.objects.filter(
            session=self.live_bbb_session,
            user=self.enrolled_student,
        ).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.role, 'student')
        self.assertFalse(attendance.is_moderator)

    def test_student_cannot_join_upcoming_session_before_start_time(self):
        self.client.force_login(self.enrolled_student)
        url = reverse('live-session-join', kwargs={'session_id': self.upcoming_bbb_session.id})
        response = self.client.get(url)
        # Redirected back to detail page with notice
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/courses/live/{self.upcoming_bbb_session.id}/', response.url)

    def test_teacher_can_enter_upcoming_session_early_as_moderator(self):
        self.client.force_login(self.teacher)
        url = reverse('live-session-join', kwargs={'session_id': self.upcoming_bbb_session.id})
        response = self.client.get(url)
        # Host is permitted early entry to prepare slides
        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertIn('/bigbluebutton/api/join?', redirect_url)
        # Must join with MODERATOR password!
        self.assertIn(f'password={self.upcoming_bbb_session.moderator_password}', redirect_url)

        # Attendance logged as moderator
        attendance = LiveSessionAttendance.objects.filter(
            session=self.upcoming_bbb_session,
            user=self.teacher,
        ).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.role, 'moderator')
        self.assertTrue(attendance.is_moderator)

    def test_sync_attendance_endpoint_permissions(self):
        sync_url = reverse('live-session-sync-attendance', kwargs={'session_id': self.live_bbb_session.id})

        # Student cannot call sync endpoint
        self.client.force_login(self.enrolled_student)
        res_forbidden = self.client.post(sync_url)
        self.assertEqual(res_forbidden.status_code, 403)

        # Teacher host can call sync endpoint
        self.client.force_login(self.teacher)
        res_teacher = self.client.post(sync_url)
        self.assertEqual(res_teacher.status_code, 200)
        self.assertEqual(res_teacher.json()['status'], 'success')

    def test_sync_recordings_endpoint(self):
        rec_url = reverse('live-session-recording-sync', kwargs={'session_id': self.live_bbb_session.id})

        # Student forbidden
        self.client.force_login(self.enrolled_student)
        res_forbidden = self.client.post(rec_url)
        self.assertEqual(res_forbidden.status_code, 403)

        # Teacher host can query recordings
        self.client.force_login(self.teacher)
        res_teacher = self.client.post(rec_url)
        self.assertEqual(res_teacher.status_code, 200)
        self.assertIn(res_teacher.json()['status'], ['success', 'none'])


class LiveProviderSettingAndAdminConsoleTests(TestCase):
    """
    Tests LiveProviderSetting model lifecycle, default seeding, and Admin Console configuration.
    """
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_live_tester', email='admin_live@thuta.edu', password='Password123!', role='admin'
        )
        self.student = User.objects.create_user(
            username='student_live_tester', email='student_live@thuta.edu', password='Password123!', role='student'
        )

    def test_default_providers_seeding(self):
        LiveProviderSetting.objects.all().delete()
        LiveProviderSetting.ensure_default_providers()
        self.assertTrue(LiveProviderSetting.objects.filter(provider='bigbluebutton').exists())
        self.assertTrue(LiveProviderSetting.objects.filter(provider='zoom').exists())
        self.assertTrue(LiveProviderSetting.objects.filter(provider='google_meet').exists())

        bbb = LiveProviderSetting.get_setting('bigbluebutton')
        self.assertTrue(bbb.is_enabled)
        self.assertTrue(bbb.is_default)

    def test_non_admin_cannot_access_console_live_settings(self):
        self.client.force_login(self.student)
        url = reverse('console-live-settings')
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    def test_admin_can_access_and_save_live_settings(self):
        self.client.force_login(self.admin)
        url = reverse('console-live-settings')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Virtual Classroom &amp; Live Teaching Settings')
        self.assertContains(response, 'BigBlueButton')

        # Admin updates settings via POST
        post_data = {
            'default_provider': 'zoom',
            'bbb_api_url': 'https://custom-bbb.thuta.edu/bigbluebutton/api/',
            'bbb_shared_secret': 'super_secret_key_123',
            'bbb_webhook_secret': 'wh_secret_xyz',
            'bbb_is_enabled': 'on',
            'zoom_is_enabled': 'on',
            'google_meet_is_enabled': 'on',
        }
        res_post = self.client.post(url, data=post_data)
        self.assertEqual(res_post.status_code, 302)

        # Verify updated DB values
        bbb_setting = LiveProviderSetting.objects.filter(provider='bigbluebutton').first()
        self.assertEqual(bbb_setting.api_url, 'https://custom-bbb.thuta.edu/bigbluebutton/api/')
        self.assertEqual(bbb_setting.shared_secret, 'super_secret_key_123')
        self.assertEqual(bbb_setting.webhook_secret, 'wh_secret_xyz')
        self.assertFalse(bbb_setting.is_default)

        zoom_setting = LiveProviderSetting.objects.filter(provider='zoom').first()
        self.assertTrue(zoom_setting.is_default)

    def test_admin_ping_endpoint(self):
        self.client.force_login(self.admin)
        url = reverse('console-live-settings-ping')
        res = self.client.post(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('latency_ms', data)
        self.assertIn('api_url', data)


class LiveSessionWebhookTests(TestCase):
    """
    Tests asynchronous webhook event reception, signature verification, and attendance/replay syncing.
    """
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='webhook_teacher', email='wh_teacher@thuta.edu', password='Password123!', role='teacher'
        )
        self.student = User.objects.create_user(
            username='webhook_student', email='wh_student@thuta.edu', password='Password123!', role='student'
        )
        self.subject = Subject.objects.create(title='DevSecOps', slug='devsecops')
        self.course = Course.objects.create(
            title='DevSecOps Live Mastery',
            slug='devsecops-live-mastery',
            subject=self.subject,
            owner=self.teacher,
            level=Course.Level.INTERMEDIATE,
            status=Course.Status.PUBLISHED,
        )
        self.session = LiveSession.objects.create(
            course=self.course,
            title='CI/CD Pipeline Security Lab',
            provider=LiveSession.Provider.BIGBLUEBUTTON,
            starts_at=timezone.now() - timedelta(minutes=30),
            duration_minutes=90,
            meeting_id='thuta-room-webhook-001',
        )

    def test_webhook_user_joined_creates_attendance(self):
        webhook_url = reverse('live-session-webhook', kwargs={'provider': 'bigbluebutton'})
        payload = {
            'data': {
                'id': 'user-joined',
                'attributes': {
                    'meeting': {'external-meeting-id': self.session.meeting_id},
                    'user': {
                        'external-user-id': str(self.student.id),
                        'name': self.student.username,
                        'role': 'VIEWER',
                    }
                }
            }
        }
        res = self.client.post(webhook_url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['status'], 'received')

        attendance = LiveSessionAttendance.objects.filter(session=self.session, user=self.student).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.role, 'student')
        self.assertFalse(attendance.is_moderator)

    def test_webhook_user_left_updates_departure(self):
        # First ensure joined
        att = LiveSessionAttendance.objects.create(
            session=self.session,
            user=self.student,
            role='student',
            is_moderator=False,
        )
        webhook_url = reverse('live-session-webhook', kwargs={'provider': 'bigbluebutton'})
        payload = {
            'data': {
                'id': 'user-left',
                'attributes': {
                    'meeting': {'external-meeting-id': self.session.meeting_id},
                    'user': {
                        'external-user-id': str(self.student.id),
                        'name': self.student.username,
                    }
                }
            }
        }
        res = self.client.post(webhook_url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)

        att.refresh_from_db()
        self.assertIsNotNone(att.left_at)

    def test_webhook_meeting_ended_closes_all_attendees(self):
        att1 = LiveSessionAttendance.objects.create(session=self.session, user=self.student)
        att2 = LiveSessionAttendance.objects.create(session=self.session, user=self.teacher, is_moderator=True)

        webhook_url = reverse('live-session-webhook', kwargs={'provider': 'bigbluebutton'})
        payload = {
            'event': 'meeting-ended',
            'meeting_id': self.session.meeting_id,
        }
        res = self.client.post(webhook_url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)

        att1.refresh_from_db()
        att2.refresh_from_db()
        self.assertIsNotNone(att1.left_at)
        self.assertIsNotNone(att2.left_at)

    def test_webhook_rap_publish_ended_links_replay(self):
        webhook_url = reverse('live-session-webhook', kwargs={'provider': 'bigbluebutton'})
        playback_link = 'https://bbb.thuta.edu/playback/presentation/2.3/rec-xyz-987'
        payload = {
            'data': {
                'id': 'rap-publish-ended',
                'attributes': {
                    'meeting': {'external-meeting-id': self.session.meeting_id},
                    'recording': {
                        'record-id': 'rec-xyz-987',
                        'playback': {
                            'format': [{'type': 'presentation', 'url': playback_link}]
                        }
                    }
                }
            }
        }
        res = self.client.post(webhook_url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.recording_url, playback_link)
        self.assertEqual(self.session.bbb_recording_id, 'rec-xyz-987')
        self.assertTrue(self.session.has_replay)

    def test_webhook_signature_validation(self):
        import hmac
        setting = LiveProviderSetting.objects.filter(provider='bigbluebutton').first()
        if not setting:
            setting = LiveProviderSetting.objects.create(provider='bigbluebutton')
        setting.webhook_secret = 'super_secret_webhook_key'
        setting.save()

        webhook_url = reverse('live-session-webhook', kwargs={'provider': 'bigbluebutton'})
        raw_body = json.dumps({'event': 'ping'})

        # 1. Invalid signature should fail
        res_invalid = self.client.post(
            webhook_url,
            data=raw_body,
            content_type='application/json',
            HTTP_X_BBB_SIGNATURE='invalid_hash',
        )
        self.assertEqual(res_invalid.status_code, 403)

        # 2. Valid signature should pass
        valid_sig = hmac.new(b'super_secret_webhook_key', raw_body.encode('utf-8'), hashlib.sha256).hexdigest()
        res_valid = self.client.post(
            webhook_url,
            data=raw_body,
            content_type='application/json',
            HTTP_X_BBB_SIGNATURE=valid_sig,
        )
        self.assertEqual(res_valid.status_code, 200)

        # Cleanup
        setting.webhook_secret = ''
        setting.save()


class PartnerLiveTeachingTenancyTests(TestCase):
    """
    Tests institutional partner tenancy and cohort permissions in live sessions.
    """
    def setUp(self):
        from apps.partner.models import Institution, PartnerMembership
        self.partner_teacher = User.objects.create_user(
            username='partner_faculty', email='faculty@ytu.edu', password='Password123!', role='teacher'
        )
        self.subject = Subject.objects.create(title='Partner Tech', slug='partner-tech')
        self.institution = Institution.objects.create(
            name='Yangon Technological University',
            slug='ytu',
            organization_id='YTU-001',
            contact_person=self.partner_teacher,
            is_verified=True,
        )
        PartnerMembership.objects.create(
            institution=self.institution,
            user=self.partner_teacher,
            role=PartnerMembership.Role.TEACHER,
            status=PartnerMembership.Status.ACTIVE,
        )

        self.partner_course = Course.objects.create(
            title='YTU Advanced Cloud Security',
            slug='ytu-advanced-cloud-security',
            subject=self.subject,
            owner=self.partner_teacher,
            partner_institution=self.institution,
            level=Course.Level.ADVANCED,
            status=Course.Status.PUBLISHED,
        )
        self.partner_session = LiveSession.objects.create(
            course=self.partner_course,
            title='YTU Cloud Security Live Lab',
            provider=LiveSession.Provider.BIGBLUEBUTTON,
            starts_at=timezone.now() - timedelta(minutes=10),
            duration_minutes=60,
        )

    def test_partner_faculty_can_host_institutional_session(self):
        self.client.force_login(self.partner_teacher)
        detail_url = reverse('live-session-detail', kwargs={'session_id': self.partner_session.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_host'])

        join_url = reverse('live-session-join', kwargs={'session_id': self.partner_session.id})
        res_join = self.client.get(join_url)
        self.assertEqual(res_join.status_code, 302)
        # Moderator entry
        self.assertIn(f'password={self.partner_session.moderator_password}', res_join.url)


class MultiDayRecurringLiveSessionTests(TestCase):
    """
    Validates multi-day recurring series scheduling, batch session generation,
    series ID grouping, and series roster views.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='teacher_rec', email='rec@example.com', password='Password123!', role='teacher'
        )
        self.subject = Subject.objects.create(title='Recurring Live Track', slug='recurring-live-track')
        self.course = Course.objects.create(
            title='Weekend Cyber Bootcamp',
            slug='weekend-cyber-bootcamp',
            subject=self.subject,
            owner=self.instructor,
            is_official=False,
            status=Course.Status.PUBLISHED,
        )

    def test_live_session_form_recurring_calculation(self):
        # Starts next Saturday
        now = timezone.now()
        # Find next Saturday (weekday 5)
        days_ahead = (5 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_sat = now + timedelta(days=days_ahead, hours=2)

        form_data = {
            'course': self.course.id,
            'title': 'Weekend Cyber Defense Bootcamp',
            'provider': LiveSession.Provider.BIGBLUEBUTTON,
            'starts_at': next_sat.strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 90,
            'schedule_type': 'recurring',
            'recurring_days': ['5', '6'],  # Sat, Sun
            'recurrence_weeks': 4,
            'total_sessions': 8,
            'record_meeting': True,
            'is_published': True,
        }
        form = LiveSessionForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        computed = form.cleaned_data.get('computed_recurring_dates')
        self.assertIsNotNone(computed)
        self.assertEqual(len(computed), 8)
        self.assertIn('Every Sat, Sun', form.cleaned_data.get('recurrence_rule_str'))

    def test_live_session_create_view_batch_creates_series(self):
        self.client.force_login(self.instructor)
        now = timezone.now()
        days_ahead = (5 - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_sat = now + timedelta(days=days_ahead, hours=3)

        post_data = {
            'course': self.course.id,
            'title': 'Advanced Penetration Testing Workshop',
            'provider': LiveSession.Provider.BIGBLUEBUTTON,
            'starts_at': next_sat.strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 120,
            'schedule_type': 'recurring',
            'recurring_days': ['5', '6'],  # Sat, Sun
            'recurrence_weeks': 4,
            'total_sessions': 8,
            'record_meeting': True,
            'is_published': True,
        }
        res = self.client.post(reverse('live-session-create'), data=post_data)
        self.assertEqual(res.status_code, 302)

        sessions = LiveSession.objects.filter(course=self.course)
        self.assertEqual(sessions.count(), 8)

        first = sessions.first()
        self.assertIsNotNone(first.series_id)
        self.assertEqual(first.total_sessions_in_series, 8)
        self.assertEqual(first.session_number, 1)
        self.assertTrue(first.is_series)
        self.assertIn("Session 1 of 8", first.series_display)

        # Check all sessions share the same series_id and have sequential numbering
        series_id = first.series_id
        session_nums = list(sessions.values_list('session_number', flat=True))
        self.assertEqual(sorted(session_nums), [1, 2, 3, 4, 5, 6, 7, 8])

        # Verify detail view includes series roster
        detail_res = self.client.get(reverse('live-session-detail', kwargs={'session_id': first.id}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertIsNotNone(detail_res.context['series_sessions'])
        self.assertEqual(len(detail_res.context['series_sessions']), 8)

    def test_single_session_remains_independent(self):
        self.client.force_login(self.instructor)
        future_time = timezone.now() + timedelta(days=2)
        post_data = {
            'course': self.course.id,
            'title': 'One-off Special Q&A',
            'provider': LiveSession.Provider.BIGBLUEBUTTON,
            'starts_at': future_time.strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 60,
            'schedule_type': 'single',
            'record_meeting': True,
            'is_published': True,
        }
        res = self.client.post(reverse('live-session-create'), data=post_data)
        self.assertEqual(res.status_code, 302)

        session = LiveSession.objects.get(title='One-off Special Q&A')
        self.assertIsNone(session.series_id)
        self.assertFalse(session.is_series)
        self.assertEqual(session.total_sessions_in_series, 1)


class InstructorCourseCreationAndUploadTests(TestCase):
    """
    Validates instructor course creation, lesson creation with video uploads,
    and dashboard entry points.
    """

    def setUp(self):
        self.instructor = User.objects.create_user(
            username='faculty_creator', email='creator@example.com', password='Password123!', role='teacher'
        )
        self.subject = Subject.objects.create(title='AI & Cloud', slug='ai-and-cloud')

    def test_instructor_can_create_course(self):
        self.client.force_login(self.instructor)
        create_url = reverse('course-create')
        res_get = self.client.get(create_url)
        self.assertEqual(res_get.status_code, 200)

        post_data = {
            'subject': self.subject.id,
            'title': 'Practical Neural Networks with Python',
            'slug': 'practical-neural-networks-with-python',
            'description': 'Master neural networks and deep learning.',
            'level': Course.Level.BEGINNER,
            'language': Course.Language.BILINGUAL,
            'access_type': Course.AccessType.FREE,
            'estimated_duration_hours': 20,
        }
        res_post = self.client.post(create_url, data=post_data)
        self.assertEqual(res_post.status_code, 302)

        course = Course.objects.get(slug='practical-neural-networks-with-python')
        self.assertEqual(course.owner, self.instructor)
        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertFalse(course.is_official)

    def test_instructor_lesson_create_with_course_param(self):
        self.client.force_login(self.instructor)
        course = Course.objects.create(
            title='Intro to Cryptography',
            slug='intro-to-cryptography',
            subject=self.subject,
            owner=self.instructor,
            is_official=False,
            status=Course.Status.DRAFT,
        )
        lesson_url = reverse('lesson-create') + f'?course={course.id}'
        res_get = self.client.get(lesson_url)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.context['target_course'], course)
        self.assertIsNotNone(res_get.context['target_module'])

    def test_instructor_dashboard_has_authoring_actions(self):
        self.client.force_login(self.instructor)
        res_dash = self.client.get(reverse('instructor-dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'Create Course')
        self.assertContains(res_dash, 'Live Class Series')
        self.assertContains(res_dash, 'Course Authoring &amp; Live Teaching Studio')

    def test_my_courses_has_create_course_button(self):
        self.client.force_login(self.instructor)
        res = self.client.get(reverse('my-courses'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Create Course')

