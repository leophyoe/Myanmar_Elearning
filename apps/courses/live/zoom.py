import re
from typing import Optional
from .base import BaseLiveProvider, LiveMeetingInfo, LiveRecordingInfo


class ZoomProvider(BaseLiveProvider):
    """
    Zoom provider for THUTA LMS:
    - Connects external Zoom meetings to THUTA course live sessions.
    - Instructors configure their Zoom personal meeting or scheduled meeting URL.
    - Enrolled students access the verified Zoom link through THUTA's authenticated barrier.
    - Attendance is logged in THUTA when students and teachers launch the session.
    """
    provider_code = 'zoom'
    name = 'Zoom'
    description = 'Standard video conferencing via Zoom. Requires host to provide meeting link or ID.'
    supports_auto_provisioning = False
    supports_attendance_sync = False
    supports_recording_sync = False
    supports_embedded_client = False

    def prepare_session(self, session, host_user=None) -> dict:
        url = (session.join_url or '').strip()
        if url and not session.meeting_id:
            # Extract meeting ID from zoom.us/j/123456789 or pwd query
            match = re.search(r'/j/(\d+)', url)
            if match:
                session.meeting_id = match.group(1)
        return {'meeting_id': session.meeting_id, 'join_url': session.join_url}

    def get_join_url(self, session, user, is_host: bool = False) -> str:
        return (session.join_url or '').strip()

