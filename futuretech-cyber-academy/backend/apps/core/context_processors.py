from django.utils import timezone
from .permissions import RoleChoices

def academy_context(request):
    """Provides platform identity and role helpers to all templates."""
    context = {
        'ACADEMY_TITLE': 'Future Tech Academy',
        'ACADEMY_TAGLINE': 'Technology & Cybersecurity Institute',
        'CURRENT_YEAR': timezone.now().year,
    }

    if request.user.is_authenticated:
        role = getattr(request.user, 'role', RoleChoices.STUDENT)
        from apps.notifications.models import Notification
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        context.update({
            'is_student': role == RoleChoices.STUDENT,
            'is_instructor': role in [RoleChoices.INSTRUCTOR, RoleChoices.LAB_INSTRUCTOR, RoleChoices.TEACHING_ASSISTANT],
            'is_admin': role in [RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN] or request.user.is_superuser,
            'user_role_label': request.user.get_role_display() if hasattr(request.user, 'get_role_display') else role,
            'unread_notifications_count': unread_count,
        })

    # Language Preference (English / Myanmar)
    lang = 'en'
    if request.user.is_authenticated and hasattr(request.user, 'preferred_language') and request.user.preferred_language:
        lang = request.user.preferred_language
    elif 'preferred_language' in request.session:
        lang = request.session['preferred_language']
    elif request.COOKIES.get('preferred_language'):
        lang = request.COOKIES.get('preferred_language')

    context['current_language'] = lang
    context['is_myanmar'] = (lang == 'my')
    return context


