import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP address handling standard proxies."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit_event(user=None, action="", object_type="", object_id="", ip_address=None, metadata=None, request=None):
    """
    Records an immutable audit event for compliance, grading, and authentication audits.
    """
    try:
        if request and not ip_address:
            ip_address = get_client_ip(request)
        if request and not user and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user

        log = AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=action,
            object_type=object_type,
            object_id=str(object_id) if object_id else "",
            ip_address=ip_address,
            metadata=metadata or {}
        )
        return log
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        return None

