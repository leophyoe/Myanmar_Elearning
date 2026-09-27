import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.common.models import BaseModel

class UserRole(models.TextChoices):
    STUDENT = 'student', 'Student'
    INSTRUCTOR = 'instructor', 'Instructor'
    LAB_ADMIN = 'lab_admin', 'Lab Administrator'
    SUPER_ADMIN = 'super_admin', 'Super Administrator'


class User(AbstractUser):
    """
    Custom User model with UUID primary keys and first-class RBAC roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True,
        help_text="Designates platform role and capability permissions."
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    # Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'role']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    @property
    def is_instructor(self):
        return self.role in [UserRole.INSTRUCTOR, UserRole.SUPER_ADMIN]

    @property
    def is_lab_admin(self):
        return self.role in [UserRole.LAB_ADMIN, UserRole.SUPER_ADMIN]

    @property
    def is_super_admin(self):
        return self.role == UserRole.SUPER_ADMIN or self.is_superuser


class StudentProfile(BaseModel):
    """
    Academic profile for enrolled cyber security students.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    student_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Official institution student ID, e.g., FTCR-2026-0042"
    )
    batch = models.CharField(
        max_length=64,
        default="2026 Intake A",
        help_text="Class cohort / intake batch"
    )
    points = models.PositiveIntegerField(default=0, db_index=True)
    rank = models.PositiveIntegerField(default=1)
    bio = models.TextField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name() or self.user.username}"


class InstructorProfile(BaseModel):
    """
    Professional profile for faculty, course creators, and lab instructors.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='instructor_profile'
    )
    department = models.CharField(max_length=128, default="Cyber Security & Defense")
    title = models.CharField(max_length=128, default="Senior Cyber Security Lecturer")
    qualifications = models.TextField(blank=True, help_text="Industry certifications (OSCP, CISSP, CEH, etc.)")

    def __str__(self):
        return f"{self.title} {self.user.get_full_name() or self.user.username}"

