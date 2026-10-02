import uuid
from django.conf import settings
from django.db import models

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
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_institution_type_display()})"


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
