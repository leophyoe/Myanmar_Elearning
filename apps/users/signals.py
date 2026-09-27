from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserRole, StudentProfile, InstructorProfile
import random

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure the appropriate role profile is created automatically on user instantiation.
    """
    if created:
        if instance.role == UserRole.STUDENT:
            if not hasattr(instance, 'student_profile'):
                student_num = random.randint(1000, 9999)
                StudentProfile.objects.create(
                    user=instance,
                    student_id=f"FTCR-2026-{student_num}"
                )
        elif instance.role == UserRole.INSTRUCTOR:
            if not hasattr(instance, 'instructor_profile'):
                InstructorProfile.objects.create(
                    user=instance
                )

