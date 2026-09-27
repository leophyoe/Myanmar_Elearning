from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin

class RoleRequiredMixin(AccessMixin):
    """CBV Mixin to restrict access based on user role."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Superusers always pass
        if request.user.is_superuser or request.user.role == 'super_admin':
            return super().dispatch(request, *args, **kwargs)

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied("You do not possess the required role permissions for this operation.")

        return super().dispatch(request, *args, **kwargs)


def role_required(allowed_roles):
    """Decorator for function-based views to enforce role-based access control."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.is_superuser or request.user.role == 'super_admin':
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
            return bool(request.user and request.user.is_authenticated and request.user.role in ['student', 'super_admin'])

    class IsInstructor(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.role in ['instructor', 'super_admin'])

    class IsLabAdmin(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.role in ['lab_admin', 'super_admin'])

    class IsSuperAdmin(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and (request.user.role == 'super_admin' or request.user.is_superuser))

except ImportError:
    pass

