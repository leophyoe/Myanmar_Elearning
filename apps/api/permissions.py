from rest_framework.permissions import BasePermission
from apps.common.permissions import (
    IsStudent, IsTeacher, IsInstructor, IsPartner, IsAdmin, IsActiveInstructorPermission
)


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission allowing access only to the owner of the object or admins.
    Handles models with user, student, or owner field.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_admin', False) or request.user.is_superuser:
            return True

        owner = getattr(obj, 'user', None) or getattr(obj, 'student', None) or getattr(obj, 'owner', None)
        return owner == request.user
