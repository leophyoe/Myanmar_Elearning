from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin


# -----------------------------------------------------------------------------
# Multi-Role Verification Helpers (Single Source of Truth)
# -----------------------------------------------------------------------------

def has_role(user, role_name: str) -> bool:
    """
    Check if user holds a specified role (supports multi-role accounts).
    role_name can be 'student', 'instructor'/'teacher', 'partner', 'admin'/'administrator'.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
        return True
    if hasattr(user, 'has_role'):
        return user.has_role(role_name)
    return getattr(user, 'role', None) == role_name


def is_student(user) -> bool:
    """Check if user has student capabilities."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'is_student', False)


def is_instructor(user) -> bool:
    """Check if user has instructor/teaching capabilities."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'is_teacher', False) or getattr(user, 'is_instructor', False)


def is_teacher(user) -> bool:
    """Alias for is_instructor."""
    return is_instructor(user)


def is_partner(user) -> bool:
    """Check if user has accredited partner capabilities."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'is_partner', False)


def is_admin(user) -> bool:
    """Check if user has platform administrator capabilities."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)


# -----------------------------------------------------------------------------
# Django Template View Mixins (Class-Based Views)
# -----------------------------------------------------------------------------

class RoleRequiredMixin(AccessMixin):
    """
    Canonical CBV Mixin to restrict access based on user role.
    Supports multi-role checking via User.has_role() or User.role.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Administrators always pass
        if getattr(request.user, 'is_admin', False) or request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        if self.allowed_roles:
            has_matching_role = False
            for r in self.allowed_roles:
                if hasattr(request.user, 'has_role') and request.user.has_role(r):
                    has_matching_role = True
                    break
                elif getattr(request.user, 'role', None) == r:
                    has_matching_role = True
                    break
            if not has_matching_role:
                raise PermissionDenied("You do not possess the required role permissions for this operation.")

        return super().dispatch(request, *args, **kwargs)


class StudentRequiredMixin(RoleRequiredMixin):
    """Restricts a view to STUDENT accounts."""
    allowed_roles = ['student']


class TeacherRequiredMixin(RoleRequiredMixin):
    """Restricts a view to TEACHER / INSTRUCTOR and ADMIN accounts."""
    allowed_roles = ['teacher', 'instructor']


class InstructorRequiredMixin(TeacherRequiredMixin):
    """Alias for TeacherRequiredMixin."""
    pass


class AdminRequiredMixin(RoleRequiredMixin):
    """Restricts a view strictly to ADMIN accounts."""
    allowed_roles = ['admin', 'administrator']


class AdministratorRequiredMixin(AdminRequiredMixin):
    """Alias for AdminRequiredMixin."""
    pass


class PartnerRequiredMixin(RoleRequiredMixin):
    """Restricts a view to PARTNER institutions and ADMIN accounts."""
    allowed_roles = ['partner']


def role_required(allowed_roles):
    """Decorator for function-based views to enforce role-based access control."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if getattr(request.user, 'is_admin', False) or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            has_matching_role = False
            for r in allowed_roles:
                if hasattr(request.user, 'has_role') and request.user.has_role(r):
                    has_matching_role = True
                    break
                elif getattr(request.user, 'role', None) == r:
                    has_matching_role = True
                    break
            if not has_matching_role:
                raise PermissionDenied("You do not possess the required role permissions for this operation.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# -----------------------------------------------------------------------------
# Django REST Framework Permission Classes
# -----------------------------------------------------------------------------
try:
    from rest_framework.permissions import BasePermission

    class IsStudent(BasePermission):
        """Allows access to authenticated students."""
        def has_permission(self, request, view):
            return bool(request.user and is_student(request.user))

    class IsTeacher(BasePermission):
        """Allows access to users with instructor teaching credentials."""
        def has_permission(self, request, view):
            return bool(request.user and is_teacher(request.user))

    class IsInstructor(IsTeacher):
        """Alias for IsTeacher."""
        pass

    class IsActiveInstructorPermission(BasePermission):
        """Allows access only when user has instructor credentials and is currently in Instructor Mode."""
        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and getattr(request.user, 'is_active_instructor_mode', False)
            )

    class IsPartner(BasePermission):
        """Allows access to accredited institution partners or administrators."""
        def has_permission(self, request, view):
            return bool(request.user and is_partner(request.user))

    class IsAdmin(BasePermission):
        """Allows access only to platform administrators."""
        def has_permission(self, request, view):
            return bool(request.user and is_admin(request.user))

    class IsAdministrator(IsAdmin):
        """Alias for IsAdmin."""
        pass

    # Aliases for backwards compatibility
    IsStudentPermission = IsStudent
    IsInstructorPermission = IsInstructor
    IsPartnerPermission = IsPartner
    IsAdministratorPermission = IsAdministrator
    IsLabAdmin = IsAdmin
    IsSuperAdmin = IsAdmin

except ImportError:
    pass
