from typing import Optional
from django.db.models import QuerySet, Q
from .models import User, UserRole


def get_user_by_account_id(account_id: str) -> Optional[User]:
    """Retrieve an active user by their permanent MEL Account ID."""
    if not account_id:
        return None
    return User.objects.filter(account_id__iexact=account_id.strip()).first()


def get_user_by_email(email: str) -> Optional[User]:
    """Retrieve an active user by their normalized email address."""
    if not email:
        return None
    return User.objects.filter(email__iexact=email.strip()).first()


def get_user_by_username(username: str) -> Optional[User]:
    """Retrieve an active user by their username."""
    if not username:
        return None
    return User.objects.filter(username__iexact=username.strip()).first()


def get_user_by_identifier(identifier: str) -> Optional[User]:
    """
    Universal identifier lookup matching Account ID, Email, or Username.
    """
    if not identifier:
        return None
    token = identifier.strip()
    return (
        get_user_by_account_id(token)
        or get_user_by_email(token)
        or get_user_by_username(token)
    )


def list_active_instructors() -> QuerySet[User]:
    """Return all instructors eligible to teach on the platform."""
    return User.objects.filter(
        Q(role__in=[UserRole.TEACHER, UserRole.ADMIN]) | Q(groups__name='Instructor'),
        is_active=True
    ).distinct()


def list_students() -> QuerySet[User]:
    """Return all registered students."""
    return User.objects.filter(
        Q(role=UserRole.STUDENT) | Q(groups__name='Student'),
        is_active=True
    ).distinct()
