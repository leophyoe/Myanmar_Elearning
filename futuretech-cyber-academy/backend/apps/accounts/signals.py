import random
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, StudentProfile, InstructorProfile, AdminProfile
from apps.core.permissions import RoleChoices

@receiver(post_save, sender=User)
def create_user_role_profile(sender, instance, created, **kwargs):
    """Ensures each user receives their appropriate role profile."""
    if created:
        if instance.role == RoleChoices.STUDENT:
            if not hasattr(instance, 'student_profile'):
                num = random.randint(1000, 9999)
                StudentProfile.objects.create(
                    user=instance,
                    student_id=f"FTCA-STU-{num}"
                )
        elif instance.role in [RoleChoices.INSTRUCTOR, RoleChoices.LAB_INSTRUCTOR, RoleChoices.TEACHING_ASSISTANT]:
            if not hasattr(instance, 'instructor_profile'):
                num = random.randint(100, 999)
                InstructorProfile.objects.create(
                    user=instance,
                    instructor_id=f"FTCA-INS-{num}"
                )
        elif instance.role in [RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN]:
            if not hasattr(instance, 'admin_profile'):
                AdminProfile.objects.create(
                    user=instance
                )

