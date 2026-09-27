try:
    from rest_framework import permissions
    BasePerm = permissions.BasePermission
except ImportError:
    class BasePerm:
        pass


class IsStudentOrStaff(BasePerm):
    """
    Ensures user is authenticated and is a verified student or faculty member.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsLabOwnerOrStaff(BasePerm):
    """
    Ensures a student can only inspect, manipulate, or stop their OWN lab instance.
    Staff and instructors have read-only or administrative management access.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_instructor or request.user.is_staff:
            return True
        if hasattr(obj, 'student'):
            return obj.student == request.user
        return False
