from django.conf import settings
from django.urls import reverse


def _dashboard_url(user):
    """Return the dashboard route that matches the user's role."""
    if user.is_admin:
        return reverse('admin-dashboard')
    if getattr(user, 'role', None) == 'partner' or (user.is_partner and not user.is_teacher):
        return reverse('partner-dashboard')
    if user.is_teacher:
        return reverse('teacher-dashboard')
    if user.is_partner:
        return reverse('partner-dashboard')
    return reverse('dashboard')


def platform_context(request):
    """Expose platform-wide configurations and user role flags to all templates."""
    context = {
        'PLATFORM_NAME': getattr(settings, 'PLATFORM_NAME', 'Myanmar E-Learning'),
        'ORGANIZATION_NAME': getattr(settings, 'ORGANIZATION_NAME', 'Myanmar E-Learning'),
        'DIPLOMA_PROGRAM_TITLE': getattr(settings, 'DIPLOMA_PROGRAM_TITLE', 'Diploma in Cyber Security'),
        'DIPLOMA_DURATION_MONTHS': getattr(settings, 'DIPLOMA_DURATION_MONTHS', 10),
    }

    if request.user.is_authenticated:
        user = request.user
        context.update({
            'is_student': user.is_student,
            'is_teacher': user.is_teacher,
            'is_partner': user.is_partner,
            'is_admin': user.is_admin,
            # Legacy flags (deprecated - prefer is_admin / is_teacher)
            'is_instructor': user.is_teacher,
            'is_lab_admin': user.is_admin,
            'is_super_admin': user.is_admin,
            'user_role_display': user.get_role_display() if hasattr(user, 'get_role_display') else '',
            'DASHBOARD_URL': _dashboard_url(user),
        })
        try:
            from apps.chat.models import Message
            context['unread_chat_count'] = Message.objects.filter(
                conversation__participants__user=user,
                is_read=False
            ).exclude(sender=user).count()
        except Exception:
            context['unread_chat_count'] = 0
    return context
