from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserRole, StudentProfile, TeacherProfile, AdminProfile
import random


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure the role-appropriate profile is created automatically on user creation.
    """
    if not created:
        return

    if instance.role == UserRole.STUDENT:
        if not hasattr(instance, 'student_profile'):
            student_id = instance.account_id or f"MEL-{instance.id or instance.username}"
            StudentProfile.objects.create(
                user=instance,
                student_id=student_id
            )
    elif instance.role in (UserRole.TEACHER, UserRole.INSTRUCTOR):
        if not hasattr(instance, 'teacher_profile'):
            TeacherProfile.objects.create(user=instance)
    elif instance.role == UserRole.ADMIN:
        if not hasattr(instance, 'admin_profile'):
            AdminProfile.objects.create(user=instance)
