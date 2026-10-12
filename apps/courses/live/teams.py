from .base import BaseLiveProvider


class TeamsProvider(BaseLiveProvider):
    """
    Microsoft Teams provider for enterprise/higher-ed partners.
    """
    provider_code = 'teams'
    name = 'Microsoft Teams'
    description = 'Enterprise online classes via Microsoft Teams.'
    supports_auto_provisioning = False
    supports_attendance_sync = False
    supports_recording_sync = False
    supports_embedded_client = False

    def prepare_session(self, session, host_user=None) -> dict:
        return {'meeting_id': session.meeting_id, 'join_url': session.join_url}

    def get_join_url(self, session, user, is_host: bool = False) -> str:
        return (session.join_url or '').strip()


class CustomLinkProvider(BaseLiveProvider):
    """
    Custom provider for arbitrary RTMP, YouTube Live, or external meeting links.
    """
    provider_code = 'other'
    name = 'Custom Link'
    description = 'Custom video broadcast or external conferencing URL.'
    supports_auto_provisioning = False
    supports_attendance_sync = False
    supports_recording_sync = False
    supports_embedded_client = False

    def prepare_session(self, session, host_user=None) -> dict:
        return {'meeting_id': session.meeting_id, 'join_url': session.join_url}

    def get_join_url(self, session, user, is_host: bool = False) -> str:
        return (session.join_url or '').strip()


class LegacyJitsiProvider(BaseLiveProvider):
    """
    Legacy Jitsi provider maintained for backward compatibility.
    """
    provider_code = 'jitsi'
    name = 'Jitsi Meet (Legacy)'
    description = 'Legacy Jitsi Meet room.'
    supports_auto_provisioning = False
    supports_attendance_sync = False
    supports_recording_sync = False
    supports_embedded_client = True

    def prepare_session(self, session, host_user=None) -> dict:
        return {'meeting_id': session.meeting_id, 'join_url': session.join_url}

    def get_join_url(self, session, user, is_host: bool = False) -> str:
        if session.join_url and session.join_url.strip():
            return session.join_url.strip()
        import urllib.parse
        full_name = user.get_full_name() if hasattr(user, 'get_full_name') and user.get_full_name() else getattr(user, 'username', 'THUTA Learner')
        encoded_name = urllib.parse.quote(full_name)
        return f"https://meet.jit.si/{session.meeting_id}#userInfo.displayName=%22{encoded_name}%22"

