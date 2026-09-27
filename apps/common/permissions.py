from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin


class RoleRequiredMixin(AccessMixin):
    """CBV Mixin to restrict access based on user role."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Administrators always pass
        if request.user.is_admin:
            return super().dispatch(request, *args, **kwargs)

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied("You do not possess the required role permissions for this operation.")

        return super().dispatch(request, *args, **kwargs)


class TeacherRequiredMixin(RoleRequiredMixin):
    """Restricts a view to TEACHER and ADMIN accounts."""
    allowed_roles = ['teacher']


def role_required(allowed_roles):
    """Decorator for function-based views to enforce role-based access control."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.is_admin:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                raise PermissionDenied("You do not possess the required role permissions for this operation.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# Optional DRF permission classes (if rest_framework is installed)
try:
    from rest_framework.permissions import BasePermission

    class IsStudent(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.is_student)

    class IsTeacher(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.is_teacher)

    class IsAdmin(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.is_admin)

    # Legacy aliases
    IsInstructor = IsTeacher
    IsLabAdmin = IsAdmin
    IsSuperAdmin = IsAdmin

except ImportError:
    pass
