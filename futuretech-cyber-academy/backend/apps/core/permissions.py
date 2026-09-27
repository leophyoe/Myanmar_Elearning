from functools import wraps
from django.db import models
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin

from apps.accounts.models import RoleChoices


class RoleRequiredMixin(AccessMixin):
    """CBV Mixin to restrict view access to specific roles."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser or request.user.role == RoleChoices.SUPER_ADMIN:
            return super().dispatch(request, *args, **kwargs)

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied("Access Denied: You do not hold the required credentials for this section.")

        return super().dispatch(request, *args, **kwargs)


class StudentRequiredMixin(RoleRequiredMixin):
    allowed_roles = [RoleChoices.STUDENT, RoleChoices.SUPER_ADMIN]


class InstructorRequiredMixin(RoleRequiredMixin):
    allowed_roles = [
        RoleChoices.INSTRUCTOR,
        RoleChoices.LAB_INSTRUCTOR,
        RoleChoices.TEACHING_ASSISTANT,
        RoleChoices.ACADEMY_ADMIN,
        RoleChoices.SUPER_ADMIN,
    ]


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = [
        RoleChoices.ACADEMY_ADMIN,
        RoleChoices.SUPER_ADMIN,
    ]


def role_required(allowed_roles):
    """Decorator for FBVs to enforce role-based access control."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.is_superuser or request.user.role == RoleChoices.SUPER_ADMIN:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                raise PermissionDenied("Access Denied: Insufficient authorization level.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# DRF Permission Classes
try:
    from rest_framework.permissions import BasePermission, SAFE_METHODS

    class IsStudentUser(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.role in [RoleChoices.STUDENT, RoleChoices.SUPER_ADMIN])

    class IsInstructorUser(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.role in [
                RoleChoices.INSTRUCTOR, RoleChoices.LAB_INSTRUCTOR, RoleChoices.TEACHING_ASSISTANT,
                RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN
            ])

    class IsAcademyAdminUser(BasePermission):
        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and (
                request.user.role in [RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN] or request.user.is_superuser
            ))

    class IsInstructorOrReadOnly(BasePermission):
        def has_permission(self, request, view):
            if request.method in SAFE_METHODS:
                return True
            return bool(request.user and request.user.is_authenticated and request.user.role in [
                RoleChoices.INSTRUCTOR, RoleChoices.LAB_INSTRUCTOR, RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN
            ])

except ImportError:
    pass
