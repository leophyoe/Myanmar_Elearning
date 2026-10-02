import uuid
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.common.models import BaseModel


class UserRole(models.TextChoices):
    """Platform institutional roles."""
    ADMIN = 'admin', 'Administrator'
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'
    PARTNER = 'partner', 'Partner'


class ActiveMode(models.TextChoices):
    STUDENT = 'student', 'Student Mode'
    INSTRUCTOR = 'instructor', 'Instructor Mode'


class User(AbstractUser):
    """
    Custom User model with UUID primary keys and first-class RBAC roles.
    Includes permanent Myanmar E-Learning Account ID (MEL-XXXXXXXX) and dual-mode support.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Permanent Account ID usable by students, teachers, partners and admins (e.g. MEL-00012345)"
    )
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True,
        help_text="Designates platform role and capability permissions."
    )
    active_mode = models.CharField(
        max_length=16,
        choices=ActiveMode.choices,
        default=ActiveMode.STUDENT,
        db_index=True,
        help_text="Current active UI workspace context."
    )
    is_associate = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Merit-based achievement status: Associate of Myanmar E-Learning."
    )
    associate_awarded_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)

    # Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['account_id']),
        ]

    def save(self, *args, **kwargs):
        if not self.account_id:
            from .services import generate_unique_account_id
            self.account_id = generate_unique_account_id()
        if self.role in (UserRole.TEACHER, UserRole.ADMIN) and self.active_mode == ActiveMode.STUDENT and self._state.adding:
            if not getattr(self, '_keep_student_mode', False):
                self.active_mode = ActiveMode.INSTRUCTOR
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} [{self.account_id or 'NO-ID'}] ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Role capability checks (Supports Multi-Role Architecture)
    # ------------------------------------------------------------------
    def has_role(self, role_name: str) -> bool:
        """
        Check if user holds a specified role (supports multi-role accounts).
        role_name can be 'student', 'instructor'/'teacher', 'partner', 'admin'/'administrator'.
        """
        r = str(role_name).lower().strip()
        if r in ('administrator', 'admin'):
            return self.is_admin
        if r in ('instructor', 'teacher'):
            return self.is_teacher
        if r == 'student':
            return self.is_student
        if r == 'partner':
            return self.is_partner

        if hasattr(self, 'role_assignments') and self.role_assignments.filter(role=r, is_active=True).exists():
            return True
        return self.role == r

    def add_role(self, role_name: str, assigned_by=None):
        """
        Assign an additional role to the user and synchronize Django Group RBAC.
        """
        r = str(role_name).lower().strip()
        role_map = {
            'instructor': UserRole.TEACHER,
            'teacher': UserRole.TEACHER,
            'student': UserRole.STUDENT,
            'partner': UserRole.PARTNER,
            'admin': UserRole.ADMIN,
            'administrator': UserRole.ADMIN,
        }
        canonical_role = role_map.get(r, r)
        assignment, _ = UserRoleAssignment.objects.get_or_create(
            user=self,
            role=canonical_role,
            defaults={'assigned_by': assigned_by, 'is_active': True}
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=['is_active'])

        group_map = {
            UserRole.STUDENT: 'Student',
            UserRole.TEACHER: 'Instructor',
            UserRole.PARTNER: 'Partner',
            UserRole.ADMIN: 'Administrator',
        }
        group_name = group_map.get(canonical_role)
        if group_name:
            from django.contrib.auth.models import Group
            group, _ = Group.objects.get_or_create(name=group_name)
            self.groups.add(group)

        if canonical_role == UserRole.TEACHER:
            TeacherProfile.objects.get_or_create(user=self)

    def remove_role(self, role_name: str):
        """Remove a role assignment without destructive account changes."""
        r = str(role_name).lower().strip()
        role_map = {
            'instructor': UserRole.TEACHER,
            'teacher': UserRole.TEACHER,
            'student': UserRole.STUDENT,
            'partner': UserRole.PARTNER,
            'admin': UserRole.ADMIN,
            'administrator': UserRole.ADMIN,
        }
        canonical_role = role_map.get(r, r)
        if hasattr(self, 'role_assignments'):
            self.role_assignments.filter(role=canonical_role).update(is_active=False)

    @property
    def roles(self):
        """Returns sorted list of all active role strings for the user."""
        active_roles = set()
        if self.role:
            active_roles.add(self.role)
        if hasattr(self, 'role_assignments'):
            for assignment in self.role_assignments.filter(is_active=True):
                active_roles.add(assignment.role)
        if self.is_admin:
            active_roles.add(UserRole.ADMIN)
        if self.is_teacher:
            active_roles.add(UserRole.TEACHER)
        if self.is_student:
            active_roles.add(UserRole.STUDENT)
        if self.is_partner:
            active_roles.add(UserRole.PARTNER)
        return sorted(list(active_roles))

    @property
    def is_admin(self):
        return (
            self.role == UserRole.ADMIN
            or self.is_superuser
            or self.groups.filter(name='Administrator').exists()
            or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role=UserRole.ADMIN, is_active=True).exists())
        )

    @property
    def is_teacher(self):
        return (
            self.role in (UserRole.TEACHER, UserRole.ADMIN)
            or self.groups.filter(name='Instructor').exists()
            or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role=UserRole.TEACHER, is_active=True).exists())
        )

    @property
    def is_student(self):
        return (
            self.role == UserRole.STUDENT
            or self.groups.filter(name='Student').exists()
            or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role=UserRole.STUDENT, is_active=True).exists())
        )

    @property
    def is_partner(self):
        if self.is_admin:
            return True
        return (
            self.role == UserRole.PARTNER
            or self.groups.filter(name='Partner').exists()
            or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role=UserRole.PARTNER, is_active=True).exists())
            or (hasattr(self, 'administered_institutions') and self.administered_institutions.exists())
            or (hasattr(self, 'managed_institutions') and self.managed_institutions.exists())
            or (hasattr(self, 'partner_memberships') and self.partner_memberships.filter(status='active').exists())
        )

    @property
    def is_active_instructor_mode(self):
        return self.is_teacher and self.active_mode == ActiveMode.INSTRUCTOR

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

    @property
    def profile(self):
        return UnifiedProfileAccessor(self)


class UnifiedProfileAccessor:
    """
    Unified virtual profile accessor on User.profile.
    Seamlessly merges Student, Teacher, and Admin profile attributes.
    """
    def __init__(self, user):
        self._user = user

    def __getattr__(self, name):
        if hasattr(self._user, 'student_profile') and hasattr(self._user.student_profile, name):
            return getattr(self._user.student_profile, name)
        if hasattr(self._user, 'teacher_profile') and hasattr(self._user.teacher_profile, name):
            return getattr(self._user.teacher_profile, name)
        if hasattr(self._user, 'admin_profile') and hasattr(self._user.admin_profile, name):
            return getattr(self._user.admin_profile, name)
        if hasattr(self._user, name):
            return getattr(self._user, name)
        raise AttributeError(f"'UnifiedProfile' object has no attribute '{name}'")


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
        blank=True,
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

    @property
    def score(self):
        return self.points

    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = self.user.account_id or f"MEL-{self.user.username}"
        super().save(*args, **kwargs)

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
    is_verified = models.BooleanField(default=False)
    level = models.CharField(
        max_length=20,
        choices=[
            ('associate', 'Associate Instructor'),
            ('professional', 'Professional Instructor'),
            ('master', 'Master Instructor'),
        ],
        default='associate',
        db_index=True,
        help_text="Pedagogical rank of the instructor."
    )
    total_live_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    total_recorded_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)

    @property
    def recorded_revenue_share_pct(self):
        if self.level == 'master':
            return 60
        if self.level == 'professional':
            return 50
        return 40

    @property
    def live_revenue_share_pct(self):
        if self.level == 'master':
            return 80
        if self.level == 'professional':
            return 75
        return 70

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


class InstructorApplication(BaseModel):
    """
    Application submitted by an aspiring teacher/instructor for admin review.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class AwardedLevel(models.TextChoices):
        ASSOCIATE = 'associate', 'Associate Instructor'
        PROFESSIONAL = 'professional', 'Professional Instructor'
        MASTER = 'master', 'Master Instructor'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_applications',
    )
    department = models.CharField(max_length=128, default='Academic Department')
    title = models.CharField(max_length=128, default='Lecturer / Instructor')
    qualifications = models.TextField(help_text='Degrees, certifications, and teaching credentials.')
    teaching_experience = models.TextField(help_text='Previous lecturing or mentoring experience.')
    target_subjects = models.CharField(max_length=255, blank=True, help_text='Disciplines the applicant intends to teach.')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    awarded_level = models.CharField(
        max_length=20,
        choices=AwardedLevel.choices,
        default=AwardedLevel.ASSOCIATE,
        help_text='Pedagogical rank granted upon approval.',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_instructor_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"InstructorApplication({self.user.username} - {self.status})"

