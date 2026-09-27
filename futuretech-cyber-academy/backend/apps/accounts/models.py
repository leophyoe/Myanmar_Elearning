import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
class RoleChoices(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Administrator'
    ACADEMY_ADMIN = 'ACADEMY_ADMIN', 'Academy Administrator'
    INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
    LAB_INSTRUCTOR = 'LAB_INSTRUCTOR', 'Lab Instructor'
    TEACHING_ASSISTANT = 'TEACHING_ASSISTANT', 'Teaching Assistant'
    STUDENT = 'STUDENT', 'Student'


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        username = extra_fields.get('username')
        if not username:
            extra_fields['username'] = email.split('@')[0]
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', RoleChoices.SUPER_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Primary user model for Future Tech Cyber Security Academy.
    Uses UUID primary keys and email-based authentication.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True, max_length=255)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(
        max_length=32,
        choices=RoleChoices.choices,
        default=RoleChoices.STUDENT,
        db_index=True
    )
    preferred_language = models.CharField(
        max_length=8,
        choices=[('en', 'English'), ('my', 'Myanmar')],
        default='en',
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['username']),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username

    @property
    def is_student(self):
        return self.role == RoleChoices.STUDENT

    @property
    def is_instructor(self):
        return self.role in [RoleChoices.INSTRUCTOR, RoleChoices.LAB_INSTRUCTOR, RoleChoices.TEACHING_ASSISTANT]

    @property
    def is_academy_admin(self):
        return self.role in [RoleChoices.ACADEMY_ADMIN, RoleChoices.SUPER_ADMIN] or self.is_superuser


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=32, unique=True, db_index=True)
    profile_photo = models.ImageField(upload_to='profiles/students/', null=True, blank=True)
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    joined_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=32, default="ACTIVE")

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"


class InstructorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    instructor_id = models.CharField(max_length=32, unique=True, db_index=True)
    bio = models.TextField(blank=True)
    specialization = models.CharField(max_length=255, blank=True)
    profile_photo = models.ImageField(upload_to='profiles/instructors/', null=True, blank=True)

    def __str__(self):
        return f"{self.instructor_id} - {self.user.get_full_name()}"


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    department = models.CharField(max_length=128, default="Academy Operations")

    def __str__(self):
        return f"Admin: {self.user.get_full_name()} ({self.department})"
