from rest_framework.permissions import BasePermission
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied


class IsStudentPermission(BasePermission):
    """Allows access to authenticated students."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)


class IsInstructorPermission(BasePermission):
    """Allows access to users with instructor teaching credentials."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_teacher)


class IsActiveInstructorPermission(BasePermission):
    """Allows access only when user has instructor credentials and is currently in Instructor Mode."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active_instructor_mode
        )


class IsPartnerPermission(BasePermission):
    """Allows access to accredited institution partners or administrators."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_partner)


class IsAdministratorPermission(BasePermission):
    """Allows access only to platform administrators."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


# -----------------------------------------------------------------------------
# Django Template View Mixins
# -----------------------------------------------------------------------------

class StudentRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_student:
            raise PermissionDenied("Student access privileges required.")
        return super().dispatch(request, *args, **kwargs)


class InstructorRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_teacher:
            raise PermissionDenied("Instructor teaching credentials required.")
        return super().dispatch(request, *args, **kwargs)


class AdministratorRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            raise PermissionDenied("Platform administrator privileges required.")
        return super().dispatch(request, *args, **kwargs)
