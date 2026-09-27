from django.conf import settings

def platform_context(request):
    """Expose platform-wide configurations and user role flags to all templates."""
    context = {
        'PLATFORM_NAME': getattr(settings, 'PLATFORM_NAME', 'Myanmar E-Learning'),
        'ORGANIZATION_NAME': getattr(settings, 'ORGANIZATION_NAME', 'Myanmar E-Learning'),
        'DIPLOMA_PROGRAM_TITLE': getattr(settings, 'DIPLOMA_PROGRAM_TITLE', 'Diploma in Cyber Security'),
        'DIPLOMA_DURATION_MONTHS': getattr(settings, 'DIPLOMA_DURATION_MONTHS', 10),
    }

    if request.user.is_authenticated:
        role = getattr(request.user, 'role', 'student')
        context.update({
            'is_student': role == 'student',
            'is_instructor': role == 'instructor',
            'is_lab_admin': role == 'lab_admin',
            'is_super_admin': role == 'super_admin' or request.user.is_superuser,
            'user_role_display': request.user.get_role_display() if hasattr(request.user, 'get_role_display') else role,
        })
    return context

