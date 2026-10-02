import secrets
from typing import Optional
from django.contrib.auth.models import Group
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import User, UserRole, ActiveMode, StudentProfile, TeacherProfile
from .selectors import get_user_by_identifier


def generate_unique_account_id() -> str:
    """
    Generates a permanent, unique Myanmar E-Learning Account ID.
    Format: MEL-XXXXXXXX (8 digits, e.g. MEL-00012345).
    """
    for _ in range(100):
        number = secrets.randbelow(90000000) + 10000000
        candidate = f"MEL-{number:08d}"
        if not User.objects.filter(account_id=candidate).exists():
            return candidate
    raise RuntimeError("Unable to generate unique Myanmar E-Learning Account ID.")


def ensure_default_groups():
    """Ensure the four canonical role groups exist in Django RBAC."""
    for role_name in ('Student', 'Instructor', 'Partner', 'Administrator'):
        Group.objects.get_or_create(name=role_name)


def assign_role_group(user: User, role_name: str):
    """Assign a canonical group role to a user."""
    ensure_default_groups()
    group = Group.objects.filter(name=role_name).first()
    if group:
        user.groups.add(group)


@transaction.atomic
def create_user_account(
    username: str,
    email: str,
    password: str,
    role: str = UserRole.STUDENT,
    first_name: str = "",
    last_name: str = "",
    **extra_fields
) -> User:
    """
    Universal user account factory creating user with permanent Account ID and role group.
    """
    account_id = extra_fields.pop('account_id', None) or generate_unique_account_id()

    active_mode = ActiveMode.INSTRUCTOR if role in (UserRole.TEACHER, UserRole.ADMIN) else ActiveMode.STUDENT

    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        account_id=account_id,
        role=role,
        active_mode=active_mode,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        **extra_fields
    )
    user.set_password(password)
    user.save()

    # Assign Django group based on primary role
    if role == UserRole.ADMIN:
        assign_role_group(user, 'Administrator')
        assign_role_group(user, 'Instructor')
    elif role == UserRole.TEACHER:
        assign_role_group(user, 'Instructor')
    else:
        assign_role_group(user, 'Student')

    # Ensure appropriate profile exists
    StudentProfile.objects.get_or_create(user=user)
    if role in (UserRole.TEACHER, UserRole.ADMIN):
        TeacherProfile.objects.update_or_create(user=user, defaults={'is_verified': True})

    return user


def authenticate_universal(
    identifier: str,
    password: str
) -> Optional[User]:
    """
    Authenticates a user via Account ID, Email, or Username paired with password.
    Returns authenticated user instance or None.
    """
    if not identifier or not password:
        return None

    user = get_user_by_identifier(identifier)
    if user and user.check_password(password) and user.is_active:
        return user
    return None


def switch_user_mode(user: User, target_mode: str) -> str:
    """
    Allows instructors to seamlessly toggle between Student Mode and Instructor Mode.
    """
    target = target_mode.lower().strip()
    if target not in (ActiveMode.STUDENT, ActiveMode.INSTRUCTOR):
        raise ValidationError(f"Invalid mode '{target_mode}'. Allowed: 'student', 'instructor'.")

    if target == ActiveMode.INSTRUCTOR:
        if not user.is_teacher:
            raise ValidationError("Only authorized instructors and administrators can switch to Instructor Mode.")
        if not user.is_admin and hasattr(user, 'teacher_profile') and not user.teacher_profile.is_verified:
            raise ValidationError("Instructor privileges must be verified by an administrator before switching to Instructor Mode.")

    user.active_mode = target
    user.save(update_fields=['active_mode'])
    return user.active_mode
