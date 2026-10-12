from typing import Dict, List, Optional, Any
from django.conf import settings

from .base import BaseLiveProvider
from .bigbluebutton import BigBlueButtonProvider
from .zoom import ZoomProvider
from .google_meet import GoogleMeetProvider
from .teams import TeamsProvider, CustomLinkProvider, LegacyJitsiProvider

_PROVIDERS: Dict[str, BaseLiveProvider] = {
    'bigbluebutton': BigBlueButtonProvider(),
    'zoom': ZoomProvider(),
    'google_meet': GoogleMeetProvider(),
    'teams': TeamsProvider(),
    'other': CustomLinkProvider(),
    'jitsi': LegacyJitsiProvider(),
}


def register_live_provider(code: str, provider: BaseLiveProvider) -> None:
    """Dynamically register or override a live conferencing provider."""
    _PROVIDERS[code] = provider


def get_live_provider(provider_code: Optional[str] = None) -> BaseLiveProvider:
    """
    Returns the provider instance for the given code.
    If code is empty or not found, falls back to the configured default provider.
    """
    if provider_code and provider_code in _PROVIDERS:
        return _PROVIDERS[provider_code]
    
    try:
        from apps.courses.models import LiveProviderSetting
        default_setting = LiveProviderSetting.objects.filter(is_default=True, is_enabled=True).first()
        if default_setting and default_setting.provider in _PROVIDERS:
            return _PROVIDERS[default_setting.provider]
    except Exception:
        pass

    default_code = getattr(settings, 'LIVE_TEACHING_DEFAULT_PROVIDER', 'bigbluebutton')
    return _PROVIDERS.get(default_code, _PROVIDERS['bigbluebutton'])


def get_default_provider() -> BaseLiveProvider:
    """Returns the default active live provider configured in THUTA settings."""
    return get_live_provider()


def get_available_providers() -> List[Dict[str, Any]]:
    """Returns metadata for all registered providers, suitable for UI dropdowns and settings."""
    order = ['bigbluebutton', 'zoom', 'google_meet', 'teams', 'other']
    settings_map = {}
    try:
        from apps.courses.models import LiveProviderSetting
        LiveProviderSetting.ensure_default_providers()
        settings_map = {s.provider: s for s in LiveProviderSetting.objects.all()}
    except Exception:
        pass

    providers_list = []
    for code in order:
        if code in _PROVIDERS:
            p = _PROVIDERS[code]
            setting = settings_map.get(code)
            providers_list.append({
                'code': p.provider_code,
                'name': p.name,
                'description': p.description,
                'supports_auto_provisioning': p.supports_auto_provisioning,
                'supports_attendance_sync': p.supports_attendance_sync,
                'supports_recording_sync': p.supports_recording_sync,
                'supports_embedded_client': p.supports_embedded_client,
                'is_enabled': setting.is_enabled if setting else True,
                'is_default': setting.is_default if setting else (code == 'bigbluebutton'),
                'api_url': setting.api_url if setting else '',
                'has_secret': bool(setting and setting.shared_secret),
                'notes': setting.notes if setting else '',
            })
    return providers_list
