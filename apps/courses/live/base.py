from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class LiveMeetingInfo:
    """Standardized representation of a live meeting status across providers."""
    meeting_id: str
    is_running: bool = False
    participant_count: int = 0
    moderator_count: int = 0
    attendees: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LiveRecordingInfo:
    """Standardized representation of a session recording across providers."""
    record_id: str
    meeting_id: str
    name: str
    published: bool = True
    playback_url: str = ''
    length_minutes: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BaseLiveProvider(ABC):
    """
    Abstract base class for virtual classroom and video conferencing providers in THUTA.
    Enforces consistent behavior across BigBlueButton, Zoom, Google Meet, and future engines.
    """
    provider_code: str = ''
    name: str = ''
    description: str = ''
    supports_auto_provisioning: bool = False
    supports_attendance_sync: bool = False
    supports_recording_sync: bool = False
    supports_embedded_client: bool = False

    @abstractmethod
    def prepare_session(self, session, host_user=None) -> dict:
        """
        Prepares or initializes room metadata on session creation or update.
        For self-hosted providers like BigBlueButton, room credentials can be auto-generated.
        """
        pass

    @abstractmethod
    def get_join_url(self, session, user, is_host: bool = False) -> str:
        """
        Generates or resolves the secure, authorized URL for the user to join.
        Hosts (teachers/admins) join as moderators; students join as attendees.
        """
        pass

    def get_meeting_status(self, session) -> LiveMeetingInfo:
        """
        Queries the provider API for active participants and running state.
        Default implementation returns basic information from local database session.
        """
        return LiveMeetingInfo(
            meeting_id=session.meeting_id or str(session.id),
            is_running=session.is_live,
            participant_count=session.attendances.count(),
        )

    def end_meeting(self, session, host_user=None) -> bool:
        """Forces the remote room to terminate if supported by the provider."""
        return True

    def fetch_recordings(self, session) -> List[LiveRecordingInfo]:
        """Queries the provider API for published recordings/replays of this session."""
        if session.recording_url:
            return [
                LiveRecordingInfo(
                    record_id=session.bbb_recording_id or f"rec-{session.id}",
                    meeting_id=session.meeting_id or str(session.id),
                    name=session.title,
                    published=True,
                    playback_url=session.recording_url,
                )
            ]
        return []

