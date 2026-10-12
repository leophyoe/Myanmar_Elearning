import re
from typing import Optional
from .base import BaseLiveProvider, LiveMeetingInfo, LiveRecordingInfo


class GoogleMeetProvider(BaseLiveProvider):
    """
    Google Meet provider for THUTA LMS:
    - Connects Google Meet virtual sessions (e.g., https://meet.google.com/abc-defg-hij).
    - Instructors schedule or create Google Meet links with their institutional Google Workspace or personal accounts.
    - Students gain access through THUTA's enrollment check, preventing link leakage.
    - Attendance is logged in THUTA when attendees launch the room.
    """
    provider_code = 'google_meet'
    name = 'Google Meet'
    description = 'Google Meet virtual classes. Requires host to provide Google Meet meeting URL.'
    supports_auto_provisioning = False
    supports_attendance_sync = False
    supports_recording_sync = False
    supports_embedded_client = False

    def prepare_session(self, session, host_user=None) -> dict:
        url = (session.join_url or '').strip()
        if url and not session.meeting_id:
            match = re.search(r'meet\.google\.com/([a-z0-9\-]+)', url)
            if match:
                session.meeting_id = match.group(1)
        return {'meeting_id': session.meeting_id, 'join_url': session.join_url}

    def get_join_url(self, session, user, is_host: bool = False) -> str:
        return (session.join_url or '').strip()

