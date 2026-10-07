import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from django.conf import settings


def get_jitsi_room_name(live_session) -> str:
    """
    Extracts or derives a clean, URL-safe Jitsi room identifier for a live session.
    If join_url has a path like /thuta-sqli-lab, extracts 'thuta-sqli-lab'.
    Otherwise generates an unguessable room slug based on session UUID.
    """
    if live_session.join_url:
        parsed = urllib.parse.urlparse(live_session.join_url)
        path = parsed.path.strip('/')
        if path:
            return path.split('/')[-1]
    
    clean_id = str(live_session.id).replace('-', '')[:16]
    return f"thuta-live-{clean_id}"


def generate_jitsi_jwt(user, live_session, expires_in_seconds: int = 14400) -> str:
    """
    Generates a cryptographically signed HS256 JWT for Jitsi Meet Prosody authentication.
    Teachers receive moderator=True; students receive moderator=False.
    If JITSI_APP_SECRET is not configured, returns an empty string (guest mode).
    """
    secret = getattr(settings, 'JITSI_APP_SECRET', '')
    if not secret:
        return ''

    app_id = getattr(settings, 'JITSI_APP_ID', 'thuta_lms')
    domain = getattr(settings, 'JITSI_DOMAIN', 'meet.jit.si')
    room_name = get_jitsi_room_name(live_session)

    is_moderator = bool(
        getattr(user, 'is_admin', False) or
        (live_session.course.owner_id and live_session.course.owner_id == user.id)
    )

    now = int(time.time())
    user_name = user.get_full_name() if hasattr(user, 'get_full_name') and user.get_full_name() else getattr(user, 'username', 'Learner')
    avatar = getattr(user, 'avatar_url', '') or ''

    header = {
        'alg': 'HS256',
        'typ': 'JWT',
    }

    payload = {
        'iss': app_id,
        'sub': domain,
        'aud': 'jitsi',
        'room': room_name,
        'iat': now,
        'nbf': now - 10,
        'exp': now + expires_in_seconds,
        'context': {
            'user': {
                'id': str(user.id),
                'name': user_name,
                'email': getattr(user, 'email', ''),
                'avatar': avatar,
                'moderator': is_moderator,
            },
            'features': {
                'recording': is_moderator,
                'livestreaming': is_moderator,
                'screen-sharing': True,
            },
        },
    }

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

    header_b64 = b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')

    signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    signature_b64 = b64url(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def get_jitsi_connection_config(user, live_session) -> dict:
    """
    Returns connection configuration parameters consumed by JitsiMeetExternalAPI.
    """
    domain = getattr(settings, 'JITSI_DOMAIN', 'meet.jit.si')
    room_name = get_jitsi_room_name(live_session)
    is_host = bool(
        getattr(user, 'is_admin', False) or
        (live_session.course.owner_id and live_session.course.owner_id == user.id)
    )
    user_name = user.get_full_name() if hasattr(user, 'get_full_name') and user.get_full_name() else getattr(user, 'username', 'Learner')
    jwt_token = generate_jitsi_jwt(user, live_session)

    return {
        'domain': domain,
        'room_name': room_name,
        'jwt': jwt_token,
        'display_name': user_name,
        'email': getattr(user, 'email', ''),
        'avatar_url': getattr(user, 'avatar_url', '') or '',
        'is_host': is_host,
        'subject': live_session.title,
    }
