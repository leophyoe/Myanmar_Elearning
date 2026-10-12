import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import AbstractUser
from apps.common.models import BaseModel


class UserRole(models.TextChoices):
    """Platform institutional roles."""
    ADMIN = 'admin', 'Administrator'
    TEACHER = 'teacher', 'Teacher'
    INSTRUCTOR = 'instructor', 'Instructor'
    STUDENT = 'student', 'Student'
    PARTNER = 'partner', 'Partner'


class InstructorLevel(models.TextChoices):
    """
    Instructor pedagogical and professional status hierarchy:
    - Teacher: Entry-level teaching status (qualifying free tutorial required, no paid courses)
    - Associate Instructor: Approved for paid courses (THUTA 60%, Instructor 40%)
    - Instructor: Approved for paid courses (THUTA 50%, Instructor 50%)
    - Professional Instructor: Approved for paid courses (THUTA 40%, Instructor 60%)
    """
    TEACHER = 'teacher', 'Teacher'
    ASSOCIATE_INSTRUCTOR = 'associate_instructor', 'Associate Instructor'
    INSTRUCTOR = 'instructor', 'Instructor'
    PROFESSIONAL_INSTRUCTOR = 'professional_instructor', 'Professional Instructor'
    # Legacy mappings for backward compatibility
    LEGACY_ASSOCIATE = 'associate', 'Associate Instructor'
    LEGACY_PROFESSIONAL = 'professional', 'Professional Instructor'
    LEGACY_MASTER = 'master', 'Master Instructor'


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

    # 48-Hour Scheduled Deletion & Account Lifecycle
    is_pending_deletion = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates if account is scheduled for deletion with a 48-hour cooling-off grace period."
    )
    deletion_scheduled_at = models.DateTimeField(null=True, blank=True)
    deletion_due_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Timestamp after 48 hours when account will permanently exit the system."
    )
    deletion_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_deletions',
        help_text="Administrator who initiated account deletion."
    )
    deletion_reason = models.TextField(blank=True, default='')

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
        if self.role in (UserRole.TEACHER, UserRole.INSTRUCTOR, UserRole.ADMIN) and self.active_mode == ActiveMode.STUDENT and self._state.adding:
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

    @property
    def can_sell_paid_courses(self) -> bool:
        tp = getattr(self, 'teacher_profile', None)
        return tp.can_sell_paid_courses if tp else False

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

        group_map = {
            UserRole.STUDENT: 'Student',
            UserRole.TEACHER: 'Instructor',
            UserRole.PARTNER: 'Partner',
            UserRole.ADMIN: 'Administrator',
        }
        group_name = group_map.get(canonical_role)
        if group_name and self.role != canonical_role:
            from django.contrib.auth.models import Group
            g = Group.objects.filter(name=group_name).first()
            if g:
                self.groups.remove(g)

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
            if self.role == UserRole.INSTRUCTOR or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role=UserRole.INSTRUCTOR, is_active=True).exists()):
                active_roles.add(UserRole.INSTRUCTOR)
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
            self.role in (UserRole.TEACHER, UserRole.INSTRUCTOR, UserRole.ADMIN)
            or self.groups.filter(name__in=['Instructor', 'Teacher']).exists()
            or (hasattr(self, 'role_assignments') and self.role_assignments.filter(role__in=[UserRole.TEACHER, UserRole.INSTRUCTOR], is_active=True).exists())
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

    @property
    def is_verified(self):
        """
        Returns True if user has verified status (Blue Mark):
        - Platform administrators and staff are verified.
        - Teachers/Instructors with verified TeacherProfile (must be reviewed and approved by admin).
        - Institutional partner coordinators with verified institution and signed MoU.
        - Students who have earned official merit achievement (is_associate / AssociateCredential).
        """
        if self.is_admin or self.is_superuser:
            return True
        try:
            teacher_prof = getattr(self, 'teacher_profile', None)
            if teacher_prof and getattr(teacher_prof, 'is_verified', False):
                return True
        except (ObjectDoesNotExist, AttributeError):
            pass
        if self.role == UserRole.PARTNER:
            try:
                from apps.partner.models import Institution
                return Institution.objects.filter(
                    contact_person=self,
                    is_verified=True,
                    mou_signed=True
                ).exists()
            except Exception:
                return False
        if self.role == UserRole.STUDENT and getattr(self, 'is_associate', False):
            return True
        return False

    @property
    def member_level_display(self):
        """
        Returns human-readable member / professional level:
        - For instructors/teachers: pedagogical rank display (e.g. "Professional Instructor", "Associate Instructor", "Teacher")
        - For students: active subscription plan tier/name (e.g. "Premium Member", "Standard Member", "Starter Member")
        - For partners: "Partner Coordinator"
        - For admins: "Administrator"
        """
        if self.is_admin or self.is_superuser:
            return "Administrator"

        if self.role in (UserRole.TEACHER, UserRole.INSTRUCTOR):
            try:
                teacher_prof = getattr(self, 'teacher_profile', None)
                if teacher_prof:
                    level = getattr(teacher_prof, 'canonical_level', None)
                    level_map = {
                        'teacher': 'Teacher',
                        'associate_instructor': 'Associate Instructor',
                        'instructor': 'Instructor',
                        'professional_instructor': 'Professional Instructor',
                    }
                    if level and level in level_map:
                        return level_map[level]
            except (ObjectDoesNotExist, AttributeError):
                pass
            return "Instructor"

        if self.role == UserRole.PARTNER:
            return "Partner Coordinator"

        try:
            if hasattr(self, 'subscriptions'):
                sub = self.subscriptions.filter(is_active=True, status='active').select_related('plan').first()
                if sub and sub.plan:
                    return f"{sub.plan.name} Member"
        except Exception:
            pass

        return "Starter Member"

    # ------------------------------------------------------------------
    # 48-Hour Scheduled Deletion & Account Lifecycle
    # ------------------------------------------------------------------
    def schedule_deletion(self, requested_by=None, reason='', hours=48):
        """
        Schedules account deletion with a 48-hour cooling-off grace period.
        ADMINISTRATOR ACCOUNTS CANNOT BE DELETED.
        Account is deactivated immediately so user cannot log in.
        """
        if self.is_admin or self.role == UserRole.ADMIN or self.is_superuser:
            raise ValueError("Administrator accounts cannot be deleted for platform security reasons.")
        now = timezone.now()
        self.is_pending_deletion = True
        self.is_active = False
        self.deletion_scheduled_at = now
        self.deletion_due_at = now + timezone.timedelta(hours=hours)
        self.deletion_requested_by = requested_by
        self.deletion_reason = reason
        self.save(update_fields=[
            'is_pending_deletion', 'is_active', 'deletion_scheduled_at',
            'deletion_due_at', 'deletion_requested_by', 'deletion_reason', 'updated_at'
        ])

    def cancel_deletion(self):
        """Cancels pending deletion and restores user account to active status."""
        self.is_pending_deletion = False
        self.deletion_scheduled_at = None
        self.deletion_due_at = None
        self.deletion_requested_by = None
        self.deletion_reason = ''
        self.is_active = True
        self.save(update_fields=[
            'is_pending_deletion', 'is_active', 'deletion_scheduled_at',
            'deletion_due_at', 'deletion_requested_by', 'deletion_reason', 'updated_at'
        ])

    @property
    def is_deletion_due(self):
        if not self.is_pending_deletion or not self.deletion_due_at:
            return False
        return timezone.now() >= self.deletion_due_at

    @property
    def deletion_time_remaining_display(self):
        if not self.is_pending_deletion or not self.deletion_due_at:
            return ""
        diff = self.deletion_due_at - timezone.now()
        total_seconds = int(diff.total_seconds())
        if total_seconds <= 0:
            return "Ready to purge / အပြီးဖျက်နိုင်ပါပြီ"
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"



class UserRoleAssignment(BaseModel):
    """
    Dynamic role assignment allowing a single user account to hold multiple roles
    (e.g., Student + Instructor + Partner) simultaneously without separate accounts.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='role_assignments'
    )
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_role_assignments'
    )

    class Meta:
        unique_together = [('user', 'role')]
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['user', 'role', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.get_role_display()} ({'active' if self.is_active else 'inactive'})"


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
        max_length=32,
        choices=InstructorLevel.choices,
        default=InstructorLevel.TEACHER,
        db_index=True,
        help_text="Pedagogical rank of the instructor."
    )
    free_tutorial_approved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Administrator verified qualifying free tutorial submission."
    )
    total_live_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    total_recorded_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    @property
    def canonical_level(self):
        lvl = (self.level or '').lower()
        if lvl in ('associate', 'associate_instructor'):
            return InstructorLevel.ASSOCIATE_INSTRUCTOR
        if lvl in ('professional', 'professional_instructor', 'master'):
            return InstructorLevel.PROFESSIONAL_INSTRUCTOR
        if lvl in ('instructor',):
            return InstructorLevel.INSTRUCTOR
        return InstructorLevel.TEACHER

    @property
    def can_sell_paid_courses(self) -> bool:
        """
        Enforce role & level permissions:
        Only approved Associate Instructor, Instructor, or Professional Instructor
        are permitted to publish and sell paid courses.
        Entry-level Teachers may only publish free tutorials.
        """
        if not self.is_verified:
            return False
        return self.canonical_level in (
            InstructorLevel.ASSOCIATE_INSTRUCTOR,
            InstructorLevel.INSTRUCTOR,
            InstructorLevel.PROFESSIONAL_INSTRUCTOR,
        )

    @property
    def platform_revenue_share_pct(self) -> int:
        """
        Platform revenue share split percentage:
        - Associate Instructor: THUTA 60%, Instructor 40%
        - Instructor: THUTA 50%, Instructor 50%
        - Professional Instructor: THUTA 40%, Instructor 60%
        - Teacher: 0% (no paid course permission)
        """
        if not self.can_sell_paid_courses:
            return 0
        clvl = self.canonical_level
        if clvl == InstructorLevel.ASSOCIATE_INSTRUCTOR:
            return 60
        if clvl == InstructorLevel.INSTRUCTOR:
            return 50
        if clvl == InstructorLevel.PROFESSIONAL_INSTRUCTOR:
            return 40
        return 50

    @property
    def instructor_revenue_share_pct(self) -> int:
        """
        Instructor revenue share percentage:
        - Associate Instructor: 40%
        - Instructor: 50%
        - Professional Instructor: 60%
        - Teacher: 0%
        """
        if not self.can_sell_paid_courses:
            return 0
        return 100 - self.platform_revenue_share_pct

    @property
    def recorded_revenue_share_pct(self):
        return self.instructor_revenue_share_pct

    @property
    def live_revenue_share_pct(self):
        return self.instructor_revenue_share_pct

    def check_has_approved_free_tutorial(self) -> bool:
        """Checks if teacher has satisfied the mandatory free tutorial contribution."""
        if self.free_tutorial_approved:
            return True
        from apps.courses.models import Course
        return Course.objects.filter(
            owner=self.user,
            is_published=True,
            price=0
        ).exists()

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
        TEACHER = 'teacher', 'Teacher (Free Tutorials Only)'
        ASSOCIATE = 'associate_instructor', 'Associate Instructor'
        INSTRUCTOR = 'instructor', 'Instructor'
        PROFESSIONAL = 'professional_instructor', 'Professional Instructor'
        # Legacy mappings for backward compatibility
        LEGACY_ASSOCIATE = 'associate', 'Associate Instructor (Legacy)'
        LEGACY_PROFESSIONAL = 'professional', 'Professional Instructor (Legacy)'
        LEGACY_MASTER = 'master', 'Master Instructor (Legacy)'

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
    sample_lecture_url = models.URLField(blank=True, help_text='Link to sample teaching video or lecture.')
    free_tutorial_url = models.URLField(blank=True, default='', help_text='Link to qualifying free tutorial on THUTA or sample lecture.')
    free_tutorial_title = models.CharField(max_length=255, blank=True, default='', help_text='Title of the qualifying free tutorial.')
    terms_accepted = models.BooleanField(default=False, help_text='Explicit agreement to faculty terms & code of conduct.')
    terms_version = models.CharField(max_length=32, default='2026.1', help_text='Version of terms accepted.')
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    requested_level = models.CharField(
        max_length=32,
        choices=AwardedLevel.choices,
        default=AwardedLevel.TEACHER,
        help_text='Level requested by applicant or eligible for review.',
    )
    awarded_level = models.CharField(
        max_length=32,
        choices=AwardedLevel.choices,
        default=AwardedLevel.TEACHER,
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
    # Requirement 18 fields
    bio = models.TextField(default='', blank=True, help_text="Personal biography and philosophy.")
    location = models.CharField(max_length=128, default='', blank=True, help_text="City/Region, Myanmar or Overseas.")
    education_degree = models.CharField(max_length=255, default='', blank=True, help_text="Highest degree / diploma achieved.")
    education_institution = models.CharField(max_length=255, default='', blank=True, help_text="Awarding university / college.")
    graduation_year = models.CharField(max_length=16, default='', blank=True, help_text="Year completed.")
    skills = models.TextField(default='', blank=True, help_text="Subject matter and technical skills.")
    work_experience_years = models.PositiveIntegerField(default=0, help_text="Total years of industry experience.")
    teaching_experience_years = models.PositiveIntegerField(default=0, help_text="Total years of teaching/lecturing.")
    website = models.URLField(default='', blank=True)
    github_url = models.URLField(default='', blank=True)
    linkedin_url = models.URLField(default='', blank=True)
    teaching_sample_topic = models.CharField(max_length=255, default='', blank=True, help_text="Topic presented in sample video.")
    teaching_sample_duration_mins = models.PositiveIntegerField(default=0)
    exam_passed = models.BooleanField(default=False, help_text="MEL Instructor Assessment passed.")
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rejection_feedback = models.TextField(default='', blank=True, help_text="Guidance for resubmission.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"InstructorApplication({self.user.username} - {self.status})"


class StudentRecognition(BaseModel):
    """
    Merit-based student achievement/recognition (Associate Learner, Professional Learner, Advanced Learner).
    Decoupled from authentication roles and membership tiers.
    """
    class RecognitionLevel(models.TextChoices):
        ASSOCIATE = 'associate', 'Associate Learner'
        PROFESSIONAL = 'professional', 'Professional Learner'
        ADVANCED = 'advanced', 'Advanced Learner'

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_recognitions'
    )
    level = models.CharField(
        max_length=32,
        choices=RecognitionLevel.choices,
        default=RecognitionLevel.ASSOCIATE,
        db_index=True
    )
    title = models.CharField(max_length=128, default='Associate Learner')
    credential_code = models.CharField(max_length=64, unique=True, db_index=True)
    awarded_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at']

    def __str__(self):
        return f"{self.title} - {self.student.username} ({self.credential_code})"


class Notification(BaseModel):
    """
    In-app and mobile push notification delivery for academic & platform updates.
    """
    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Success'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    level = models.CharField(
        max_length=16,
        choices=Level.choices,
        default=Level.INFO,
    )
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"Notification({self.user.username}: {self.title})"

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class PushDevice(BaseModel):
    """
    Registered mobile or web push device tokens for Android and iOS clients.
    """
    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'
        WEB = 'web', 'Web'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=16, choices=Platform.choices, default=Platform.ANDROID)
    device_name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"PushDevice({self.user.username} - {self.platform} - {self.device_name or 'unnamed'})"


class TermAgreement(BaseModel):
    """
    Versioned record of user agreement to platform policies and legal declarations.
    Enforces active acceptance during student registration, teacher application,
    instructor promotion, partner onboarding, and course publishing.
    """
    class TermsType(models.TextChoices):
        STUDENT_REGISTRATION = 'student_registration', 'Student Registration Terms & Privacy'
        TEACHER_APPLICATION = 'teacher_application', 'Teacher Application & Free Tutorial Commitment'
        INSTRUCTOR_PROMOTION = 'instructor_promotion', 'Instructor Promotion & Paid Content Terms'
        PARTNER_AGREEMENT = 'partner_agreement', 'Partner Institution Terms & MOU'
        COURSE_PUBLISHING = 'course_publishing', 'Course Quality & Content Ownership Declaration'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='term_agreements'
    )
    terms_type = models.CharField(
        max_length=64,
        choices=TermsType.choices,
        db_index=True
    )
    terms_version = models.CharField(
        max_length=32,
        default='2026.1',
        db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    agreed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-agreed_at']
        indexes = [
            models.Index(fields=['user', 'terms_type', 'terms_version']),
        ]

    def __str__(self):
        return f"{self.user.username} agreed to {self.get_terms_type_display()} (v{self.terms_version})"


class InstructorLevelHistory(BaseModel):
    """
    Audit trail recording every change, promotion, or suspension of instructor professional level.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_level_history'
    )
    previous_level = models.CharField(max_length=32, blank=True)
    new_level = models.CharField(max_length=32)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_level_changes'
    )
    reason = models.TextField(blank=True, help_text="Administrative justification, promotion scorecard notes, or violation details.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Level change for {self.user.username}: {self.previous_level} -> {self.new_level}"


