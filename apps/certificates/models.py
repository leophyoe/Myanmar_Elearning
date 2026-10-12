import secrets
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class CertificateTemplate(BaseModel):
    """
    Customizable certificate layout and styling template.
    Supports:
    1. Built-in aesthetic themes (Classic Gold, Academic Emerald, Cyber Tech, Minimalist Luxury)
    2. Custom background upload (PNG / JPG A4 template designed in Canva/Photoshop/Illustrator)
       with precision dynamic text & QR overlay coordinates.
    """
    class DesignMode(models.TextChoices):
        BUILTIN = 'builtin', 'Built-in Theme Designer'
        CUSTOM_UPLOAD = 'custom_upload', 'Upload Custom Template (PNG / Image)'

    class ThemeStyle(models.TextChoices):
        CLASSIC_GOLD = 'classic_gold', 'Royal Gold & Navy (Standard Diploma)'
        ACADEMIC_EMERALD = 'academic_emerald', 'Academic Emerald & Gold'
        CYBER_TECH = 'cyber_tech', 'Cyber Tech & Modern Cyan'
        MINIMAL_ELEGANT = 'minimal_elegant', 'Minimalist Luxury & Gold'

    class FontChoice(models.TextChoices):
        CINZEL = 'cinzel', 'Cinzel (Royal Classic Serif)'
        PLAYFAIR = 'playfair', 'Playfair Display (Academic Serif)'
        INTER = 'inter', 'Inter (Clean Modern Sans)'
        GREAT_VIBES = 'great_vibes', 'Great Vibes / Script (Calligraphy)'

    title = models.CharField(
        max_length=255,
        help_text="Template Name (e.g. 'THUTA Official Diploma', 'KBZ Institute Cyber Diploma', 'Zaw Zaw Python Masterclass')"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_certificate_templates',
        help_text="Instructor, Partner representative, or Admin who authored this template."
    )
    partner = models.ForeignKey(
        'partner.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certificate_templates',
        help_text="Partner Institution for co-branded certificates."
    )
    design_mode = models.CharField(
        max_length=32,
        choices=DesignMode.choices,
        default=DesignMode.BUILTIN,
    )
    theme_style = models.CharField(
        max_length=32,
        choices=ThemeStyle.choices,
        default=ThemeStyle.CLASSIC_GOLD,
    )
    background_image = models.ImageField(
        upload_to='certificates/backgrounds/',
        null=True,
        blank=True,
        help_text="High-resolution A4 landscape blank certificate image (PNG/JPG)."
    )
    institution_name = models.CharField(max_length=255, default="MYANMAR E-LEARNING (THUTA)")
    header_title = models.CharField(max_length=255, default="CERTIFICATE OF COMPLETION")
    subtitle = models.CharField(max_length=255, default="This is proudly awarded to", blank=True)
    body_text = models.CharField(
        max_length=255,
        default="for successfully demonstrating professional competence and mastering",
        blank=True
    )
    font_choice = models.CharField(
        max_length=32,
        choices=FontChoice.choices,
        default=FontChoice.CINZEL,
    )
    primary_color = models.CharField(max_length=16, default="#D97706")
    accent_color = models.CharField(max_length=16, default="#1E293B")

    name_pos_top = models.PositiveSmallIntegerField(default=44, help_text="Student Name Top offset (%)")
    name_color = models.CharField(max_length=16, default="#1E293B")
    name_font_size = models.PositiveSmallIntegerField(default=34, help_text="Font size in px")

    title_pos_top = models.PositiveSmallIntegerField(default=58, help_text="Course Title Top offset (%)")
    title_color = models.CharField(max_length=16, default="#0F172A")
    title_font_size = models.PositiveSmallIntegerField(default=22, help_text="Font size in px")

    date_pos_top = models.PositiveSmallIntegerField(default=78, help_text="Date Top offset (%)")
    date_pos_left = models.PositiveSmallIntegerField(default=22, help_text="Date Left offset (%)")

    qr_pos_top = models.PositiveSmallIntegerField(default=76, help_text="QR Code Top offset (%)")
    qr_pos_left = models.PositiveSmallIntegerField(default=50, help_text="QR Code Left offset (%)")

    serial_pos_top = models.PositiveSmallIntegerField(default=88, help_text="Serial Code Top offset (%)")
    serial_pos_left = models.PositiveSmallIntegerField(default=50, help_text="Serial Code Left offset (%)")

    logo_image = models.ImageField(upload_to='certificates/logos/', null=True, blank=True)
    partner_logo = models.ImageField(upload_to='certificates/logos/', null=True, blank=True)
    
    signature_1_image = models.ImageField(upload_to='certificates/signatures/', null=True, blank=True)
    signature_1_name = models.CharField(max_length=128, default="Academic Director", blank=True)
    signature_1_title = models.CharField(max_length=128, default="Myanmar E-Learning Board", blank=True)

    signature_2_image = models.ImageField(upload_to='certificates/signatures/', null=True, blank=True)
    signature_2_name = models.CharField(max_length=128, default="Lead Instructor", blank=True)
    signature_2_title = models.CharField(max_length=128, default="Faculty Chair", blank=True)

    show_qr_code = models.BooleanField(default=True)
    show_seal = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_design_mode_display()})"


class Certificate(BaseModel):
    """
    Cryptographically verifiable credential awarded upon diploma/course completion or exam verification.
    """
    class CertificateType(models.TextChoices):
        COURSE_COMPLETION = 'course_completion', 'Course Completion Certificate'
        EXAM_VERIFIED = 'exam_verified', 'Exam-Based Verified Certificate'
        PARTICIPATION = 'participation', 'Certificate of Participation'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.PROTECT,
        related_name='issued_certificates',
        null=True,
        blank=True,
    )
    exam = models.ForeignKey(
        'courses.Quiz',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_certificates',
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_certificates',
        help_text="Custom or branded layout template used to render this credential.",
    )
    certificate_type = models.CharField(
        max_length=32,
        choices=CertificateType.choices,
        default=CertificateType.COURSE_COMPLETION,
        db_index=True,
    )
    certificate_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Public certificate serial ID, e.g. MEL-CERT-2026-89A1 or MEL-EXAM-2026-89A1"
    )
    student_name = models.CharField(max_length=255)
    program_title = models.CharField(max_length=255, default="Course Completion Certificate")
    issued_at = models.DateTimeField(auto_now_add=True)
    completion_date = models.DateField(blank=True, null=True, help_text="Date requirements were satisfied.")
    grade = models.CharField(max_length=16, default="Distinction")
    exam_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Final score percentage earned on verified exam.",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_certificates',
        help_text="Designated instructor, examiner or administrator who audited this credential.",
    )
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.certificate_code} - {self.student_name}"

    def save(self, *args, **kwargs):
        if not self.student_name and self.student:
            self.student_name = self.student.get_full_name() or self.student.username
        if not self.program_title or self.program_title in ("Course Completion Certificate", "Exam-Based Verified Certificate"):
            if self.exam and getattr(self.exam, 'title', None):
                self.program_title = self.exam.title
            elif self.course and getattr(self.course, 'title', None):
                self.program_title = self.course.title
        super().save(*args, **kwargs)

    @property
    def certificate_id(self):
        return self.certificate_code

    @property
    def verification_code(self):
        return self.certificate_code

    @property
    def issue_date(self):
        return self.issued_at

    @property
    def course_name(self):
        if self.course:
            return self.course.title
        if self.exam:
            return self.exam.title
        return self.program_title

    @property
    def program(self):
        return self.program_title

    @property
    def effective_template(self):
        if self.template:
            return self.template
        if self.exam and getattr(self.exam, 'certificate_template', None):
            return self.exam.certificate_template
        if self.course and getattr(self.course, 'certificate_template', None):
            return self.course.certificate_template
        if self.course and getattr(self.course, 'partner_institution', None):
            partner_tpl = self.course.partner_institution.certificate_templates.filter(is_active=True).first()
            if partner_tpl:
                return partner_tpl
        return CertificateTemplate.objects.filter(is_default=True, is_active=True).first()

    def revoke(self, reason=""):
        self.is_revoked = True
        self.revocation_reason = reason
        self.save(update_fields=['is_revoked', 'revocation_reason'])

    def unrevoke(self):
        self.is_revoked = False
        self.revocation_reason = ""
        self.save(update_fields=['is_revoked', 'revocation_reason'])

    @property
    def sha256_hash(self):
        import hashlib
        ts = self.issued_at.isoformat() if self.issued_at else ""
        raw = f"THUTA:{self.certificate_code}:{self.student_name}:{ts}:{self.program_title}:{self.grade}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @property
    def is_exam_certificate(self):
        return bool(self.exam or self.certificate_type == self.CertificateType.EXAM_VERIFIED)

    @property
    def partner_institution(self):
        if self.course and getattr(self.course, 'partner_institution', None):
            return self.course.partner_institution
        tpl = self.effective_template
        if tpl and getattr(tpl, 'partner', None):
            return tpl.partner
        return None

    @classmethod
    def generate_code(cls, cert_type='course_completion'):
        rand = secrets.token_hex(4).upper()
        if cert_type == 'exam_verified':
            return f"MEL-EXAM-2026-{rand}"
        return f"MEL-CERT-2026-{rand}"


class AssociateCredential(BaseModel):
    """
    Earned Academic Merit Benchmark: "Associate of Myanmar E-Learning".
    Awarded automatically when a student satisfies the merit criteria:
    - completed courses
    - examinations / certificates
    - practical labs
    - projects
    - active learning hours
    """
    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='associate_credential'
    )
    credential_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Public credential serial ID, e.g. MEL-ASSOC-2026-89A1"
    )
    title = models.CharField(max_length=255, default="Associate of Myanmar E-Learning")
    awarded_at = models.DateTimeField(auto_now_add=True)
    courses_completed_count = models.PositiveSmallIntegerField(default=0)
    labs_solved_count = models.PositiveSmallIntegerField(default=0)
    capstones_completed_count = models.PositiveSmallIntegerField(default=0)
    active_learning_hours = models.PositiveIntegerField(default=0)
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at']

    def __str__(self):
        return f"{self.credential_code} - {self.student.username}"

    @classmethod
    def generate_code(cls):
        rand = secrets.token_hex(4).upper()
        return f"MEL-ASSOC-2026-{rand}"
