import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.common.models import BaseModel


class UserRole(models.TextChoices):
    """Three institutional roles. ADMIN is a superset of every capability."""
    ADMIN = 'admin', 'Administrator'
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'


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

    # ------------------------------------------------------------------
    # Role capability checks
    # ------------------------------------------------------------------
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_teacher(self):
        return self.role in (UserRole.TEACHER, UserRole.ADMIN)

    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    # Legacy aliases kept so older templates/queries keep working.
    @property
    def is_instructor(self):
        return self.is_teacher

    @property
    def is_lab_admin(self):
        return self.is_admin

    @property
    def is_super_admin(self):
        return self.is_admin


class StudentProfile(BaseModel):
    """
    Academic profile for enrolled students.
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
        help_text="Official institution student ID, e.g., MEL-2026-0042"
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


class TeacherProfile(BaseModel):
    """
    Professional profile for course authors, lecturers and graders.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    department = models.CharField(max_length=128, default="Academic Department")
    title = models.CharField(max_length=128, default="Lecturer")
    qualifications = models.TextField(
        blank=True,
        help_text="Degrees, certifications and teaching experience"
    )

    def __str__(self):
        return f"{self.title} {self.user.get_full_name() or self.user.username}"


class AdminProfile(BaseModel):
    """
    Operational profile for platform administrators.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_profile'
    )
    department = models.CharField(max_length=128, default="Administration")
    title = models.CharField(max_length=128, default="Platform Administrator")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} {self.user.get_full_name() or self.user.username}"
