import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class Institution(BaseModel):
    """
    Partner educational institution (University, College, School, or Academy).
    """

    class InstitutionType(models.TextChoices):
        UNIVERSITY = 'university', 'University / College'
        HIGH_SCHOOL = 'high_school', 'High School / Secondary'
        TRAINING_CENTER = 'training_center', 'Training Center / Academy'
        ENTERPRISE = 'enterprise', 'Enterprise / Corporate Partner'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    institution_type = models.CharField(
        max_length=32,
        choices=InstitutionType.choices,
        default=InstitutionType.TRAINING_CENTER,
    )
    contact_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_institutions',
        help_text="Partner admin / representative for this institution.",
    )
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='partners/logos/', null=True, blank=True)

    is_verified = models.BooleanField(default=False, db_index=True)
    mou_signed = models.BooleanField(default=False)
    max_student_seats = models.PositiveIntegerField(default=100)
    organization_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Permanent Partner Organization ID, e.g. MEL-ORG-00012345"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_institution_type_display()})"

    def save(self, *args, **kwargs):
        if not self.organization_id:
            import secrets
            hex_token = secrets.token_hex(4).upper()
            self.organization_id = f"MEL-ORG-{hex_token}"
        super().save(*args, **kwargs)


class InstitutionCohort(BaseModel):
    """
    Class batch / cohort managed under a partner institution.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='cohorts'
    )
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, help_text="e.g. YU-CS-2026-A")
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='institution_cohorts',
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('institution', 'code')]

    def __str__(self):
        return f"{self.institution.name} - {self.name} ({self.code})"


class CohortStudent(BaseModel):
    """
    Student membership in an institutional cohort.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cohort = models.ForeignKey(
        InstitutionCohort, on_delete=models.CASCADE, related_name='students'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrolled_cohorts'
    )
    student_id_number = models.CharField(
        max_length=64, blank=True, help_text="Roll number or student card ID"
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-joined_at']
        unique_together = [('cohort', 'student')]

    def __str__(self):
        return f"{self.student.username} in {self.cohort.name}"


class PartnerMembership(BaseModel):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner / Principal'
        ADMIN = 'admin', 'Institutional Admin'
        TEACHER = 'teacher', 'Institutional Instructor'
        STAFF = 'staff', 'Academic Staff / Registrar'
        VIEWER = 'viewer', 'Auditor / Viewer'

    StaffRole = Role

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INVITED = 'invited', 'Invited'
        SUSPENDED = 'suspended', 'Suspended'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='partner_memberships'
    )
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.STAFF
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    title = models.CharField(max_length=128, blank=True)
    department = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ['institution', 'role']
        unique_together = [('institution', 'user')]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} at {self.institution.name}"


class PartnerStudent(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Invitation'
        ACTIVE = 'active', 'Active'
        DECLINED = 'declined', 'Declined'
        COMPLETED = 'completed', 'Completed'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='partner_students'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='partner_affiliations'
    )
    external_student_id = models.CharField(
        max_length=64, blank=True, help_text="Institutional student card/roll ID."
    )
    class_group = models.CharField(
        max_length=64, blank=True, help_text="Class/group name within institution"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    invitation_note = models.TextField(blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [('institution', 'student')]

    def __str__(self):
        return f"{self.student.username} ({self.institution.name}) - {self.get_status_display()}"


class PartnerApplication(BaseModel):
    """
    Formal application submitted by teacher or educational leader to establish a Partner Organization.
    Workflow: Applied (Pending) -> Under Review -> Approved / Rejected.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='partner_applications',
        help_text="MEL account submitting the partnership application."
    )
    organization_name = models.CharField(max_length=255)
    institution_type = models.CharField(
        max_length=32,
        choices=Institution.InstitutionType.choices,
        default=Institution.InstitutionType.TRAINING_CENTER
    )
    country = models.CharField(max_length=64, default='Myanmar')
    city = models.CharField(max_length=64, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    contact_person_name = models.CharField(max_length=128, blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=32, blank=True)
    registration_number = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_partner_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PartnerApplication({self.organization_name} by {self.applicant.username} - {self.status})"

    def approve(self, reviewed_by=None):
        """Activates institution, assigns PARTNER role to applicant, and sets up owner membership."""
        from django.utils.text import slugify
        self.status = self.Status.APPROVED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        base_slug = slugify(self.organization_name) or 'partner-org'
        slug = base_slug
        idx = 1
        while Institution.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{idx}"
            idx += 1

        inst, _ = Institution.objects.get_or_create(
            name=self.organization_name,
            defaults={
                'slug': slug,
                'institution_type': self.institution_type,
                'contact_person': self.applicant,
                'email': self.contact_email,
                'phone': self.contact_phone,
                'address': self.address,
                'website': self.website,
                'is_verified': True,
                'mou_signed': True,
            }
        )

        # Grant partner role to applicant without removing other roles
        self.applicant.add_role('partner', assigned_by=reviewed_by)
        PartnerMembership.objects.get_or_create(
            institution=inst,
            user=self.applicant,
            defaults={
                'role': PartnerMembership.Role.OWNER,
                'status': PartnerMembership.Status.ACTIVE,
                'title': 'Organization Representative',
            }
        )
        return inst


class PartnerRevenueShareRule(BaseModel):
    """
    Configurable partner revenue-sharing business rules.
    Default: 75% Partner, 25% MEL platform.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner_type = models.CharField(max_length=32, default='all')
    course_type = models.CharField(max_length=32, default='all')
    partner_share_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('75.00'))
    platform_share_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))
    effective_date = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-effective_date']

    def __str__(self):
        return f"Rule({self.partner_type}/{self.course_type}: {self.partner_share_pct}% Partner / {self.platform_share_pct}% Platform)"

    @classmethod
    def get_share_pct(cls, institution=None, course=None):
        """Returns (partner_share_pct, platform_share_pct) based on active configuration."""
        rule = cls.objects.filter(is_active=True).first()
        if rule:
            return rule.partner_share_pct, rule.platform_share_pct
        default_partner = Decimal(str(getattr(settings, 'PARTNER_DEFAULT_REVENUE_SHARE_PCT', 75.0)))
        return default_partner, Decimal('100.00') - default_partner

