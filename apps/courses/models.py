from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel


class Subject(BaseModel):
    """
    Top-level subject / category that groups courses.

    Kind distinguishes general academic subjects from the integrated
    cyber security range (which exposes labs, CTF and the web terminal).
    """

    class Kind(models.TextChoices):
        GENERAL = 'general', 'General'
        CYBER = 'cyber', 'Cyber Security'

    title = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=64, default="book-open")
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.GENERAL,
        db_index=True,
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    @classmethod
    def ensure_default_subjects(cls):
        """
        Seeds standard subject disciplines:
        - Python Programming
        - Computer Science
        - ICT
        - IGCSE / O Level
        - GED
        - Artificial Intelligence
        - Cyber Security
        - Engineering
        - Non-IT subjects
        """
        categories = [
            {
                'slug': 'python-programming',
                'title': 'Python Programming',
                'description': 'Master Python from fundamentals to advanced automation and software development.',
                'icon_name': 'code-slash',
                'kind': cls.Kind.GENERAL,
                'order': 1,
            },
            {
                'slug': 'computer-science',
                'title': 'Computer Science',
                'description': 'Data structures, algorithms, operating systems, and computer architecture.',
                'icon_name': 'cpu',
                'kind': cls.Kind.GENERAL,
                'order': 2,
            },
            {
                'slug': 'ict',
                'title': 'Information & Communication Technology (ICT)',
                'description': 'Digital literacy, productivity tools, computer networking, and office systems.',
                'icon_name': 'laptop',
                'kind': cls.Kind.GENERAL,
                'order': 3,
            },
            {
                'slug': 'igcse-o-level',
                'title': 'IGCSE / O Level',
                'description': 'International curriculum preparation for IGCSE Computer Science, ICT, and Sciences.',
                'icon_name': 'mortarboard',
                'kind': cls.Kind.GENERAL,
                'order': 4,
            },
            {
                'slug': 'ged',
                'title': 'GED (General Educational Development)',
                'description': 'Comprehensive preparation for high school equivalency exams.',
                'icon_name': 'journal-bookmark',
                'kind': cls.Kind.GENERAL,
                'order': 5,
            },
            {
                'slug': 'artificial-intelligence',
                'title': 'Artificial Intelligence & Machine Learning',
                'description': 'Deep learning, computer vision, natural language processing, and modern GenAI.',
                'icon_name': 'robot',
                'kind': cls.Kind.GENERAL,
                'order': 6,
            },
            {
                'slug': 'cyber-security',
                'title': 'Cyber Security & Ethical Hacking',
                'description': 'Network defense, web security, reverse engineering, and hands-on CTF challenges.',
                'icon_name': 'shield-check',
                'kind': cls.Kind.CYBER,
                'order': 7,
            },
            {
                'slug': 'engineering',
                'title': 'Engineering & Technology',
                'description': 'Electrical engineering, embedded systems, robotics, and hardware principles.',
                'icon_name': 'gear',
                'kind': cls.Kind.GENERAL,
                'order': 8,
            },
            {
                'slug': 'non-it',
                'title': 'Non-IT & Academic Subjects',
                'description': 'Languages, business studies, mathematics, and professional development.',
                'icon_name': 'book',
                'kind': cls.Kind.GENERAL,
                'order': 9,
            },
        ]
        created = []
        for cat in categories:
            slug = cat.pop('slug')
            obj, _ = cls.objects.update_or_create(slug=slug, defaults=cat)
            created.append(obj)
        return created


class Course(BaseModel):
    """
    Top-level academic program (e.g. Diploma in Cyber Security).
    """

    class BillingPeriod(models.TextChoices):
        ONE_TIME = 'one_time', 'One-time payment'
        MONTHLY = 'monthly', 'Monthly subscription'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'
        REJECTED = 'rejected', 'Rejected'

    class OwnerType(models.TextChoices):
        PLATFORM = 'platform', 'Myanmar E-Learning Platform'
        INSTRUCTOR = 'instructor', 'Instructor'
        PARTNER = 'partner', 'Partner Organization'

    class AccessType(models.TextChoices):
        FREE = 'free', 'Free'
        STARTER = 'starter', 'Starter Tier'
        STANDARD = 'standard', 'Standard Tier'
        PREMIUM = 'premium', 'Premium Tier'
        PARTNER_ONLY = 'partner_only', 'Partner Organization Only'
        PAID = 'paid', 'Paid (Direct Purchase)'
        INSTRUCTOR_COURSE = 'instructor_course', 'Instructor Course'

    class MembershipTierRequired(models.TextChoices):
        STARTER = 'starter', 'Starter (Free / Exploratory)'
        STANDARD = 'standard', 'Standard Tier'
        PREMIUM = 'premium', 'Premium Tier'

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        ALL_LEVELS = 'all_levels', 'All Levels'

    class Language(models.TextChoices):
        BURMESE = 'my', 'Myanmar'
        ENGLISH = 'en', 'English'
        BILINGUAL = 'bi', 'Bilingual (Myanmar + English)'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
        help_text="Course editorial lifecycle state."
    )
    owner_type = models.CharField(
        max_length=20,
        choices=OwnerType.choices,
        default=OwnerType.PLATFORM,
        db_index=True,
        help_text="Course ownership classification (Platform, Instructor, or Partner)."
    )
    access_type = models.CharField(
        max_length=20,
        choices=AccessType.choices,
        default=AccessType.STANDARD,
        db_index=True,
        help_text="Primary access entitlement required for course."
    )
    membership_tier_required = models.CharField(
        max_length=16,
        choices=MembershipTierRequired.choices,
        default=MembershipTierRequired.STANDARD,
        db_index=True,
        help_text="Minimum membership tier required to access this course."
    )
    certificate_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Additional certificate issuance fee (in MMK). 0 if included in course/membership."
    )
    title = models.CharField(max_length=255, default="Diploma in Cyber Security")
    slug = models.SlugField(unique=True, db_index=True)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
    )
    description = models.TextField()
    level = models.CharField(
        max_length=16,
        choices=Level.choices,
        default=Level.ALL_LEVELS,
        db_index=True,
    )
    language = models.CharField(
        max_length=8,
        choices=Language.choices,
        default=Language.BURMESE,
    )
    is_premium = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Requires Premium membership tier or individual course purchase.",
    )
    certificate_eligible = models.BooleanField(
        default=True,
        help_text="Grants verified completion certificate upon passing criteria.",
    )
    certificate_template = models.ForeignKey(
        'certificates.CertificateTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        help_text="Custom or branded certificate design template awarded upon completion.",
    )
    exam_required = models.BooleanField(
        default=False,
        help_text="Requires passing an official proctored examination before certification.",
    )
    exam_voucher_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Price for specialized proctored examination voucher (in MMK). 0 if included in course.",
    )
    duration_months = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=True, db_index=True)
    is_official = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates official Myanmar E-Learning platform course created/owned by administration."
    )
    is_free_tutorial = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates this course as a qualifying free tutorial submission."
    )
    thumbnail = models.ImageField(upload_to='courses/', null=True, blank=True)

    # Editorial Review fields
    admin_review_notes = models.TextField(
        blank=True,
        help_text="Editorial feedback or review notes from administrators."
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_courses',
        help_text="Administrator who conducted editorial review."
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the latest editorial review."
    )

    # Commercial settings — teachers price their own courses; the platform keeps
    # settings.PAYMENT_PLATFORM_COMMISSION_RATE of every approved payment.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_courses',
        help_text="Teacher who publishes this course and receives the revenue share.",
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Price per billing period. Set 0 to publish the course for free.",
    )
    currency = models.CharField(max_length=8, default='MMK', editable=False)
    billing_period = models.CharField(
        max_length=16,
        choices=BillingPeriod.choices,
        default=BillingPeriod.ONE_TIME,
    )
    partner_institution = models.ForeignKey(
        'partner.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partner_courses',
        help_text="Institutional partner offering or endorsing this curriculum."
    )
    partner_revenue_share_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75.00,
        help_text="Partner revenue share percentage (e.g. 75.00% for partner, 25.00% for MEL).",
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Promotional discounted price for marketing campaigns.",
    )
    partner_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Special discounted price for students affiliated with partner institution.",
    )
    special_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Special temporary price override.",
    )
    partner_discount_allowed = models.BooleanField(
        default=True,
        help_text="Allow affiliated partner students to receive discounted partner pricing.",
    )
    public_preview = models.BooleanField(
        default=True,
        help_text="Allow public guests to preview course outline.",
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def exam_available(self):
        return self.exam_required or self.quizzes.filter(quiz_type='exam').exists()

    @property
    def exam_fee(self):
        return self.exam_voucher_price

    @property
    def certificate_available(self):
        return self.certificate_eligible

    @property
    def membership_required(self):
        return self.access_type in [self.AccessType.STANDARD, self.AccessType.PREMIUM]

    @property
    def instructor_price(self):
        return self.price

    def get_effective_price(self, user=None):
        """Returns pricing breakdown dictionary for course and given user."""
        return self.calculate_price_for_user(user)

    def calculate_price_for_user(self, user=None):
        """
        Single server-side source of truth for course pricing.
        Zero trust: never rely on client parameters.
        Evaluates in order:
        1. Free course check (price == 0 or access_type == FREE)
        2. Active user membership tier coverage (Standard / Premium) -> 0 MMK
        3. Partner student affiliation discount -> partner_price
        4. Special temporary price override -> special_price
        5. Promotional discount price -> discount_price
        6. Standard course price -> price
        """
        # 1. Base free check
        if self.is_free or self.access_type == self.AccessType.FREE:
            return {
                'final_price': Decimal('0.00'),
                'original_price': self.price or Decimal('0.00'),
                'is_free': True,
                'pricing_tier': 'free',
                'discount_amount': Decimal('0.00'),
                'currency': self.currency,
                'reason': 'This course is free.',
            }

        # 2. Check student membership subscription
        if user and getattr(user, 'is_authenticated', False):
            from apps.billing.models import active_subscription_for
            sub = active_subscription_for(user)
            if sub and sub.is_current:
                # If course requires Standard and user has Standard or Premium
                if self.access_type == self.AccessType.STANDARD and sub.plan.has_all_standard_courses:
                    return {
                        'final_price': Decimal('0.00'),
                        'original_price': self.price,
                        'is_free': True,
                        'pricing_tier': 'membership',
                        'discount_amount': self.price,
                        'currency': self.currency,
                        'reason': f"Covered by your {sub.plan.name} Membership.",
                    }
                # If course requires Premium and user has Premium
                if self.access_type == self.AccessType.PREMIUM and sub.plan.has_premium_courses:
                    return {
                        'final_price': Decimal('0.00'),
                        'original_price': self.price,
                        'is_free': True,
                        'pricing_tier': 'membership',
                        'discount_amount': self.price,
                        'currency': self.currency,
                        'reason': f"Covered by your {sub.plan.name} Membership.",
                    }

        # 3. Special temporary price override (takes precedence over partner and promotional pricing)
        if self.special_price is not None:
            effective_price = max(self.special_price, Decimal('0.00'))
            discount = max(self.price - effective_price, Decimal('0.00'))
            return {
                'final_price': effective_price,
                'original_price': self.price,
                'is_free': effective_price <= 0,
                'pricing_tier': 'special',
                'discount_amount': discount,
                'currency': self.currency,
                'reason': 'Special limited-time pricing.',
            }

        # 4. Check partner student affiliation
        if user and getattr(user, 'is_authenticated', False) and self.partner_institution and self.partner_price is not None:
            from apps.partner.models import PartnerStudent, PartnerMembership
            is_partner_student = PartnerStudent.objects.filter(
                institution=self.partner_institution, student=user, status=PartnerStudent.Status.ACTIVE
            ).exists() or PartnerMembership.objects.filter(
                institution=self.partner_institution, user=user, status=PartnerMembership.Status.ACTIVE
            ).exists()
            if is_partner_student:
                effective_price = max(self.partner_price, Decimal('0.00'))
                discount = max(self.price - effective_price, Decimal('0.00'))
                return {
                    'final_price': effective_price,
                    'original_price': self.price,
                    'is_free': effective_price <= 0,
                    'pricing_tier': 'partner',
                    'discount_amount': discount,
                    'currency': self.currency,
                    'reason': f"Partner institution pricing ({self.partner_institution.name}).",
                }

        # 5. Check promotional discount price
        if self.discount_price is not None:
            effective_price = max(self.discount_price, Decimal('0.00'))
            discount = max(self.price - effective_price, Decimal('0.00'))
            return {
                'final_price': effective_price,
                'original_price': self.price,
                'is_free': effective_price <= 0,
                'pricing_tier': 'discount',
                'discount_amount': discount,
                'currency': self.currency,
                'reason': 'Promotional discount pricing.',
            }

        # 6. Standard list price
        return {
            'final_price': self.price,
            'original_price': self.price,
            'is_free': False,
            'pricing_tier': 'standard',
            'discount_amount': Decimal('0.00'),
            'currency': self.currency,
            'reason': 'Standard course price.',
        }

    def clean(self):
        super().clean()
        if self.price and self.price > 0 and self.owner and not getattr(self.owner, 'is_admin', False):
            teacher_profile = getattr(self.owner, 'teacher_profile', None)
            if teacher_profile and not teacher_profile.can_sell_paid_courses:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    "Teachers at the entry-level Teacher rank may only publish free tutorials. "
                    "Promotion to Associate Instructor or higher is required before publishing paid courses."
                )

    def save(self, *args, **kwargs):
        if self.owner and hasattr(self.owner, 'is_admin') and self.owner.is_admin:
            self.is_official = True
        elif self.owner is None:
            self.is_official = True

        if self.partner_institution:
            self.owner_type = self.OwnerType.PARTNER
        elif self.owner and hasattr(self.owner, 'is_teacher') and self.owner.is_teacher and not (hasattr(self.owner, 'is_admin') and self.owner.is_admin):
            self.owner_type = self.OwnerType.INSTRUCTOR
        elif self.is_official_platform_course:
            self.owner_type = self.OwnerType.PLATFORM

        if self.status == self.Status.PUBLISHED:
            self.is_published = True
        elif self.status in (self.Status.DRAFT, self.Status.PENDING_REVIEW, self.Status.ARCHIVED, self.Status.REJECTED):
            self.is_published = False

        if self.is_free and self.access_type == self.AccessType.PAID:
            self.access_type = self.AccessType.FREE

        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.price and self.price > 0 and self.owner and not getattr(self.owner, 'is_admin', False):
            teacher_profile = getattr(self.owner, 'teacher_profile', None)
            if teacher_profile and not teacher_profile.can_sell_paid_courses:
                from django.core.exceptions import ValidationError
                raise ValidationError("Teachers at the entry-level Teacher rank may only publish free tutorials. Promotion to Associate Instructor or higher is required before publishing paid courses.")

    @property
    def is_free(self):
        return self.price is None or self.price <= 0

    @property
    def effective_price(self):
        if self.is_free:
            return Decimal('0.00')
        if self.discount_price is not None and self.price is not None and self.discount_price < self.price:
            return self.discount_price
        return self.price or Decimal('0.00')

    @property
    def has_discount(self):
        return bool(self.discount_price is not None and self.price is not None and self.discount_price < self.price)

    @property
    def is_new_course(self):
        if not self.created_at:
            return False
        from django.utils import timezone
        return (timezone.now() - self.created_at).days <= 30

    @property
    def instructor(self):
        return self.owner

    @property
    def difficulty(self):
        return self.level

    @property
    def duration_hours(self):
        return (self.duration_months or 1) * 10

    @property
    def tagline(self):
        desc = self.description or ""
        return (desc[:120] + "...") if len(desc) > 120 else desc

    @property
    def is_featured(self):
        return self.is_official or self.is_premium

    def can_publish(self, user=None):
        """
        Validates whether a user can publish this course.
        - Platform admins can publish any course.
        - Unverified teachers CANNOT publish courses.
        - Verified instructors can publish/submit courses.
        """
        if user is None:
            user = self.owner
        if not user:
            return False
        if getattr(user, 'is_admin', False):
            return True
        if getattr(user, 'is_teacher', False):
            teacher_profile = getattr(user, 'teacher_profile', None)
            return bool(teacher_profile and getattr(teacher_profile, 'is_verified', False))
        return False

    @property
    def exam_available(self):
        return bool(self.exam_required or self.quizzes.filter(quiz_type='course_exam').exists())

    @property
    def certificate_available(self):
        return bool(self.certificate_eligible)

    @property
    def is_official_platform_course(self):
        """Returns True if marked official or authored by administration / unassigned."""
        if self.is_official:
            return True
        if self.owner is None:
            return True
        if hasattr(self.owner, 'is_admin') and self.owner.is_admin:
            return True
        return False

    @property
    def publisher_display_name(self):
        """Displays 'Myanmar E-Learning' for official platform courses, or the instructor's name."""
        if self.is_official_platform_course:
            return "Myanmar E-Learning"
        return self.owner.get_full_name() or self.owner.username


class Module(BaseModel):
    """
    Modular division of the Diploma curriculum (14 modules).
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    order = models.PositiveSmallIntegerField(db_index=True)
    code = models.CharField(max_length=32, db_index=True, help_text="e.g., MOD-01, MOD-14")
    title = models.CharField(max_length=255)
    summary = models.TextField()
    learning_objectives = models.JSONField(default=list, blank=True)
    icon_name = models.CharField(max_length=64, default="shield-check")

    class Meta:
        ordering = ['order']
        unique_together = [('course', 'order'), ('course', 'code')]

    def __str__(self):
        return f"{self.code}: {self.title}"

    @property
    def description(self):
        return self.summary


class LessonType(models.TextChoices):
    TEXT = 'text', 'Text / Article'
    VIDEO = 'video', 'Video'
    PDF = 'pdf', 'PDF Document'
    QUIZ = 'quiz', 'Quiz'
    ASSIGNMENT = 'assignment', 'Assignment'
    LAB = 'lab', 'Hands-on Lab'
    CTF = 'ctf', 'CTF Challenge'


class Lesson(BaseModel):
    """
    Structured learning unit inside a module.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    order = models.PositiveSmallIntegerField(db_index=True)
    title = models.CharField(max_length=255)
    lesson_type = models.CharField(
        max_length=16,
        choices=LessonType.choices,
        default=LessonType.TEXT,
        db_index=True,
        help_text="Determines how the lesson body is rendered for students.",
    )
    content_markdown = models.TextField(help_text="Detailed theoretical lecture in Markdown format")
    video_url = models.URLField(
        blank=True,
        help_text="External video link (YouTube, Vimeo, ...). Used when no file is uploaded.",
    )
    video_file = models.FileField(
        upload_to='lessons/video/%Y/%m/',
        null=True,
        blank=True,
        help_text="Uploaded video file (mp4/webm).",
    )
    document_file = models.FileField(
        upload_to='lessons/docs/%Y/%m/',
        null=True,
        blank=True,
        help_text="Attached document, e.g. a PDF handout.",
    )
    estimated_minutes = models.PositiveIntegerField(default=45)
    has_lab = models.BooleanField(default=False)
    has_quiz = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        unique_together = [('module', 'order')]

    def __str__(self):
        return f"{self.module.code} - L{self.order}: {self.title}"

    @property
    def course(self):
        return self.module.course

    @property
    def has_video(self):
        return bool(self.video_file or self.video_url)

    @property
    def video_embed_url(self):
        """
        Derives embeddable URL for YouTube, Vimeo, Bunny Stream, Cloudflare Stream, or direct video.
        """
        url = (self.video_url or '').strip()
        if not url:
            return None
        import re
        # YouTube
        yt_match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})', url)
        if yt_match:
            return f"https://www.youtube-nocookie.com/embed/{yt_match.group(1)}?rel=0&modestbranding=1"

        # Vimeo
        vimeo_match = re.search(r'vimeo\.com\/(?:channels\/(?:\w+\/)?|groups\/([^\/]*)\/videos\/|album\/(\d+)\/video\/|video\/|)(\d+)', url)
        if vimeo_match:
            vid_id = vimeo_match.group(3) or vimeo_match.group(2) or vimeo_match.group(1)
            return f"https://player.vimeo.com/video/{vid_id}"

        # Bunny Stream embed URL
        if 'iframe.mediadelivery.net' in url or 'bunnycdn.com' in url or 'b-cdn.net' in url:
            return url

        # Cloudflare Stream embed URL
        if 'cloudflarestream.com' in url or 'watch.cloudflarestream.com' in url:
            return url

        # Google Drive Video Preview
        gdrive_match = re.search(r'drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)', url)
        if gdrive_match:
            return f"https://drive.google.com/file/d/{gdrive_match.group(1)}/preview"

        # Loom Video Embed
        loom_match = re.search(r'loom\.com\/(?:share|embed)\/([a-zA-Z0-9]+)', url)
        if loom_match:
            return f"https://www.loom.com/embed/{loom_match.group(1)}"

        return url

    @property
    def has_document(self):
        return bool(self.document_file)

    @property
    def document_extension(self):
        if not self.document_file or not self.document_file.name:
            return ''
        import os
        return os.path.splitext(self.document_file.name)[1].lower().lstrip('.')

    @property
    def is_pdf(self):
        if self.document_extension:
            return self.document_extension == 'pdf'
        return self.lesson_type == 'pdf'

    @property
    def is_presentation(self):
        if self.document_extension:
            return self.document_extension in ['ppt', 'pptx', 'odp', 'key', 'pps', 'ppsx']
        return self.lesson_type in ['slides', 'presentation', 'ppt', 'pptx']

    @property
    def has_slides(self):
        return bool(self.document_file and (self.is_pdf or self.is_presentation))

    @property
    def slide_viewer_type(self):
        if self.is_presentation:
            return 'presentation'
        if self.is_pdf:
            return 'pdf'
        return 'document'

    @property
    def slide_deck(self):
        from apps.courses.services.slides import get_lesson_slide_deck
        return get_lesson_slide_deck(self)

    @property
    def duration_minutes(self):
        return self.estimated_minutes

    @property
    def content(self):
        return self.content_markdown

    @property
    def is_preview(self):
        return getattr(self, '_is_preview', False) or (self.order == 1)

    @is_preview.setter
    def is_preview(self, value):
        self._is_preview = bool(value)

    @property
    def slug(self):
        from django.utils.text import slugify
        return slugify(self.title) or f"lesson-{self.id}"

    @property
    def attachment_url(self):
        return self.document_file.url if self.document_file else None


class Topic(BaseModel):
    """
    Granular topic or theoretical section within a lesson.
    """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='topics')
    order = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=255)
    content_markdown = models.TextField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.lesson.title} -> {self.title}"


class Quiz(BaseModel):
    """
    Knowledge and competency evaluation for a course, module, or lesson.
    Supports quizzes, practice exams, course exams, final exams, practical assessments, and projects.
    """
    class AssessmentType(models.TextChoices):
        QUIZ = 'quiz', 'Quiz'
        PRACTICE_EXAM = 'practice_exam', 'Practice Exam'
        COURSE_EXAM = 'course_exam', 'Course Exam'
        FINAL_EXAM = 'final_exam', 'Final Exam'
        PRACTICAL = 'practical', 'Practical Assessment'
        ASSIGNMENT = 'assignment', 'Assignment'
        PROJECT = 'project', 'Project Assessment'
        EXAM = 'exam', 'Course Exam'

    # Backwards compatibility alias
    QuizType = AssessmentType

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='quizzes',
        null=True,
        blank=True,
        help_text="Course to which this assessment belongs.",
    )
    module = models.ForeignKey(
        'courses.Module',
        on_delete=models.SET_NULL,
        related_name='quizzes',
        null=True,
        blank=True,
        help_text="Optional module to which this assessment belongs.",
    )
    lesson = models.OneToOneField(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        related_name='quiz',
        null=True,
        blank=True,
        help_text="Optional lesson if this assessment is directly attached to a lesson unit.",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, help_text="Overview, instructions, or exam guidelines.")
    quiz_type = models.CharField(
        max_length=32,
        choices=AssessmentType.choices,
        default=AssessmentType.QUIZ,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
        help_text="Editorial status of this assessment.",
    )
    time_limit_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Time limit in minutes (0 = untimed)."
    )
    passing_percentage = models.PositiveSmallIntegerField(
        default=75,
        help_text="Passing score percentage required (0-100)."
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=3,
        help_text="Maximum allowed attempts (0 = unlimited)."
    )
    randomize_questions = models.BooleanField(
        default=False,
        help_text="Randomize question presentation order per attempt."
    )
    randomize_choices = models.BooleanField(
        default=False,
        help_text="Randomize choice options per question."
    )
    available_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of assessment availability window."
    )
    available_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deadline after which no new attempts are accepted."
    )
    is_required = models.BooleanField(
        default=True,
        help_text="Whether passing this assessment is required for course completion."
    )
    is_standalone = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Can be taken directly via Exam Center without course enrollment.",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Price for standalone exam access in MMK (0 = Free Exam).",
    )
    currency = models.CharField(max_length=8, default='MMK')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_quizzes',
        help_text="Author/Instructor who owns this assessment.",
    )
    assigned_instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_grading_quizzes',
        help_text="Designated instructor/evaluator for manual grading.",
    )
    institution = models.ForeignKey(
        'partner.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes',
        help_text="Partner institution if this is an institutional exam.",
    )
    requires_manual_grading = models.BooleanField(
        default=False,
        help_text="Requires instructor/evaluator review before finalizing score and issuing certificate.",
    )
    certificate_type = models.CharField(
        max_length=32,
        choices=[
            ('course_completion', 'Course Completion'),
            ('exam_verified', 'Exam-Based Verified'),
            ('none', 'No Certificate'),
        ],
        default='course_completion',
        help_text="Type of certificate awarded upon passing.",
    )
    certificate_template = models.ForeignKey(
        'certificates.CertificateTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes',
        help_text="Custom or branded certificate design template awarded upon passing.",
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.get_quiz_type_display()}: {self.title}"

    @property
    def is_exam(self):
        return self.is_standalone or self.quiz_type in (
            self.AssessmentType.COURSE_EXAM,
            self.AssessmentType.FINAL_EXAM,
            self.AssessmentType.EXAM,
        )

    @property
    def is_free(self):
        return (self.price or Decimal('0.00')) <= Decimal('0.00')

    @property
    def has_manual_questions(self):
        return self.requires_manual_grading or self.questions.filter(
            question_type__in=[
                Question.QuestionType.SHORT_ANSWER,
                Question.QuestionType.CODING,
                Question.QuestionType.PRACTICAL_LAB,
                Question.QuestionType.FILE_SUBMISSION,
                Question.QuestionType.PROJECT_EVALUATION,
            ]
        ).exists()


class Question(BaseModel):
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'multiple_choice', 'Multiple Choice (Single Answer)'
        MULTIPLE_SELECT = 'multiple_select', 'Multiple Select (Multi-Choice)'
        TRUE_FALSE = 'true_false', 'True / False'
        FILL_IN_BLANK = 'fill_in_blank', 'Fill in the Blank'
        SHORT_ANSWER = 'short_answer', 'Short Answer'
        CODING = 'coding', 'Coding Problem'
        PRACTICAL_LAB = 'practical_lab', 'Hands-on Lab Exercise'
        FILE_SUBMISSION = 'file_submission', 'File Submission'
        PROJECT_EVALUATION = 'project_evaluation', 'Project Evaluation'

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveSmallIntegerField(default=1)
    prompt = models.TextField()
    question_type = models.CharField(
        max_length=32,
        choices=QuestionType.choices,
        default=QuestionType.MULTIPLE_CHOICE,
        db_index=True,
    )
    points = models.PositiveSmallIntegerField(default=10)
    correct_text_answer = models.CharField(
        max_length=512,
        blank=True,
        help_text="Expected answer for Fill in the Blank or exact Short Answer (pipe '|' separated for accepted variants)."
    )
    rubric_criteria = models.TextField(
        blank=True,
        help_text="Grading criteria for short answer, coding, or practical evaluations."
    )
    explanation = models.TextField(blank=True, help_text="Explanatory feedback shown after attempt")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.prompt[:60]}..."


class Choice(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=512)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{'[✓]' if self.is_correct else '[ ]'} {self.text[:50]}"

    @property
    def order(self):
        return getattr(self, '_order', 1)

    @order.setter
    def order(self, val):
        self._order = val


class QuizAttempt(BaseModel):
    """
    Pedagogical audit trail for every student attempt at a quiz or exam.
    """
    class AttemptStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        PENDING_REVIEW = 'pending_review', 'Pending Manual Grading'
        GRADED = 'graded', 'Graded & Finalized'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=32,
        choices=AttemptStatus.choices,
        default=AttemptStatus.SUBMITTED,
        db_index=True,
    )
    score_percentage = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    points_earned = models.PositiveIntegerField(default=0)
    answers_data = models.JSONField(default=dict, blank=True)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_quiz_attempts',
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True, help_text="Evaluator / Instructor comprehensive comments.")
    rubric_scores = models.JSONField(default=dict, blank=True, help_text="Structured rubric scores and criterion feedback.")
    certificate = models.ForeignKey(
        'certificates.Certificate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quiz_attempts',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title} (Attempt #{self.attempt_number}: {self.score_percentage}%)"


class Assessment(Quiz):
    """Proxy model providing a domain-neutral alias for Quiz."""
    class Meta:
        proxy = True
        verbose_name = 'Assessment'
        verbose_name_plural = 'Assessments'


class AssessmentAttempt(QuizAttempt):
    """Proxy model providing a domain-neutral alias for QuizAttempt."""
    class Meta:
        proxy = True
        verbose_name = 'Assessment Attempt'
        verbose_name_plural = 'Assessment Attempts'


class Assignment(BaseModel):
    """
    Practical or written assignment for instructor grading.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField()
    max_score = models.PositiveIntegerField(default=100)
    due_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Assignment: {self.title} ({self.module.code})"


class AssignmentSubmission(BaseModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_text = models.TextField(blank=True)
    submission_file = models.FileField(upload_to='submissions/', null=True, blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_assignments')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('assignment', 'student')]

    def __str__(self):
        return f"Submission by {self.student.username} for {self.assignment.title}"


class UserProgress(BaseModel):
    """
    Tracks granular completion states for lessons, modules, and labs.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='user_progress')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True)
    lab = models.ForeignKey('labs.Lab', on_delete=models.CASCADE, null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('user', 'lesson')]
        indexes = [
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.lesson or self.module} ({'Done' if self.is_completed else 'Pending'})"


class Enrollment(BaseModel):
    """
    A student's registration on a course. Required before lessons can be opened.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DROPPED = 'dropped', 'Dropped'

    class Source(models.TextChoices):
        SELF = 'self', 'Self Enrolled'
        PAID = 'paid', 'Direct Payment'
        FREE = 'free', 'Free Access'
        PARTNER = 'partner', 'Partner Assigned'
        INSTRUCTOR = 'instructor', 'Instructor Enrolled'
        ADMIN = 'admin', 'Administrator Enrolled'
        COUPON = 'coupon', 'Coupon Redemption'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SELF,
        db_index=True,
        help_text="Source channel through which this enrollment occurred."
    )
    partner_institution = models.ForeignKey(
        'partner.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='institutional_enrollments',
        help_text="Partner institution associated with this enrollment if applicable."
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    progress_pct = models.PositiveSmallIntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True, db_index=True, help_text="First accessed lesson timestamp.")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = [('course', 'student')]
        indexes = [
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.course.title} ({self.get_status_display()})"

    @property
    def completed_lessons_count(self):
        from .models import UserProgress
        return UserProgress.objects.filter(
            user=self.student,
            lesson__module__course=self.course,
            is_completed=True,
        ).count()

    @property
    def completed_modules_count(self):
        total_completed = 0
        for mod in self.course.modules.prefetch_related('lessons').all():
            total_lessons = mod.lessons.count()
            if total_lessons > 0:
                completed = self.student.progress_records.filter(
                    lesson__module=mod,
                    is_completed=True,
                ).count()
                if completed >= total_lessons:
                    total_completed += 1
        return total_completed



import secrets
import uuid


class LiveSession(BaseModel):
    """
    A scheduled real-time class for a course (BigBlueButton, Zoom, Google Meet, Teams, ...).
    Only students with access to the course can join or see the link.
    Supports single-day sessions or recurring multi-day session series (e.g. Sat & Sun for 8 weeks).
    """

    class Provider(models.TextChoices):
        BIGBLUEBUTTON = 'bigbluebutton', 'BigBlueButton (THUTA Classroom)'
        ZOOM = 'zoom', 'Zoom'
        GOOGLE_MEET = 'google_meet', 'Google Meet'
        TEAMS = 'teams', 'Microsoft Teams'
        OTHER = 'other', 'Other / Custom Link'
        JITSI = 'jitsi', 'Jitsi Meet (Legacy)'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='live_sessions')
    title = models.CharField(max_length=255)
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.BIGBLUEBUTTON
    )
    join_url = models.URLField(
        blank=True, default='',
        help_text="Direct joining URL for external providers (Zoom/Meet), or auto-generated for BigBlueButton."
    )
    recording_url = models.URLField(
        blank=True, default='',
        help_text="Link to session recording or replay (YouTube, Vimeo, Google Drive, BBB, etc.)."
    )
    meeting_id = models.CharField(
        max_length=128, blank=True, default='', db_index=True,
        help_text="Unique room identifier on conferencing server."
    )
    moderator_password = models.CharField(
        max_length=64, blank=True, default='',
        help_text="Teacher / host entry key."
    )
    attendee_password = models.CharField(
        max_length=64, blank=True, default='',
        help_text="Student / attendee entry key."
    )
    record_meeting = models.BooleanField(
        default=True,
        help_text="Automatically record classroom session for student replay."
    )
    bbb_recording_id = models.CharField(
        max_length=128, blank=True, default='',
        help_text="BigBlueButton recording identifier."
    )
    starts_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=True, db_index=True)

    # Multi-day recurring series metadata
    series_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Grouping ID for recurring multi-day session series."
    )
    session_number = models.PositiveSmallIntegerField(
        default=1,
        help_text="Session sequence number (e.g. Session 1 of 8)."
    )
    total_sessions_in_series = models.PositiveSmallIntegerField(
        default=1,
        help_text="Total sessions in this series."
    )
    recurrence_rule = models.CharField(
        max_length=128, blank=True, default='',
        help_text="Human-readable schedule, e.g. 'Every Sat, Sun for 4 weeks'"
    )

    class Meta:
        ordering = ['starts_at']

    def save(self, *args, **kwargs):
        if not self.meeting_id:
            clean_id = str(self.id).replace('-', '')[:16]
            self.meeting_id = f"thuta-live-{clean_id}"
        if not self.moderator_password:
            self.moderator_password = secrets.token_urlsafe(12)
        if not self.attendee_password:
            self.attendee_password = secrets.token_urlsafe(12)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_provider_display()})"

    @property
    def is_bbb(self):
        return self.provider == self.Provider.BIGBLUEBUTTON

    @property
    def ends_at(self):
        from datetime import timedelta
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_upcoming(self):
        from django.utils import timezone
        return self.starts_at > timezone.now()

    @property
    def is_live(self):
        from django.utils import timezone
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    @property
    def is_ended(self):
        from django.utils import timezone
        return timezone.now() > self.ends_at

    @property
    def status(self):
        if self.is_live:
            return 'live'
        elif self.is_upcoming:
            return 'scheduled'
        return 'ended'

    @property
    def has_replay(self):
        return bool(self.recording_url and self.recording_url.strip())

    @property
    def is_series(self):
        return bool(self.series_id)

    @property
    def series_display(self):
        if self.series_id and self.total_sessions_in_series > 1:
            return f"Session {self.session_number} of {self.total_sessions_in_series}"
        return ""

    def get_series_sessions(self):
        if not self.series_id:
            return LiveSession.objects.filter(pk=self.pk)
        return LiveSession.objects.filter(series_id=self.series_id).order_by('session_number', 'starts_at')


class LiveSessionAttendance(BaseModel):
    """
    Audited log of student and instructor attendance in virtual classrooms.
    Records entry, exit, duration, role, and client details.
    """
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='attendances')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_session_attendances')
    role = models.CharField(max_length=32, default='student', help_text="Role: student, teacher, host, moderator")
    is_moderator = models.BooleanField(default=False, help_text="True if joined as classroom moderator/host.")
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-joined_at']
        verbose_name = 'Live Session Attendance'
        verbose_name_plural = 'Live Session Attendances'

    def __str__(self):
        return f"{self.user} ({self.role}) - {self.session.title} ({self.joined_at.strftime('%Y-%m-%d %H:%M')})"


class LiveProviderSetting(BaseModel):
    """
    Admin-configurable live teaching provider settings.
    Stored in database so administrators can modify URLs, API keys, and availability
    from the THUTA Admin Console without application restarts or code deployments.
    """
    class Provider(models.TextChoices):
        BIGBLUEBUTTON = 'bigbluebutton', 'BigBlueButton (THUTA Classroom)'
        ZOOM = 'zoom', 'Zoom'
        GOOGLE_MEET = 'google_meet', 'Google Meet'
        TEAMS = 'teams', 'Microsoft Teams'
        OTHER = 'other', 'Other / Custom Link'

    provider = models.CharField(max_length=32, choices=Provider.choices, unique=True)
    is_enabled = models.BooleanField(default=True, help_text="Allow teachers to select this provider.")
    is_default = models.BooleanField(default=False, help_text="Default provider for new live sessions.")
    api_url = models.CharField(max_length=255, blank=True, default='', help_text="Base API URL for self-hosted server.")
    shared_secret = models.CharField(max_length=255, blank=True, default='', help_text="Shared secret or API key.")
    webhook_secret = models.CharField(max_length=255, blank=True, default='', help_text="Signing secret for incoming webhooks.")
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['provider']
        verbose_name = 'Live Provider Setting'
        verbose_name_plural = 'Live Provider Settings'

    def __str__(self):
        return f"{self.get_provider_display()} ({'Enabled' if self.is_enabled else 'Disabled'})"

    @classmethod
    def ensure_default_providers(cls):
        """Ensures default records exist in DB for all supported providers."""
        from django.conf import settings
        default_configs = [
            {
                'provider': cls.Provider.BIGBLUEBUTTON,
                'is_enabled': True,
                'is_default': True,
                'api_url': getattr(settings, 'BBB_API_URL', 'https://test-install.blindsidenetworks.com/bigbluebutton/api/'),
                'shared_secret': getattr(settings, 'BBB_SHARED_SECRET', '8cd8ef52e8e101574e400365b55e11a6'),
                'notes': 'THUTA Primary Open-Source Virtual Classroom.',
            },
            {
                'provider': cls.Provider.ZOOM,
                'is_enabled': True,
                'is_default': False,
                'notes': 'External meeting links for Zoom.',
            },
            {
                'provider': cls.Provider.GOOGLE_MEET,
                'is_enabled': True,
                'is_default': False,
                'notes': 'External meeting links for Google Meet.',
            },
            {
                'provider': cls.Provider.TEAMS,
                'is_enabled': True,
                'is_default': False,
                'notes': 'External meeting links for Microsoft Teams.',
            },
            {
                'provider': cls.Provider.OTHER,
                'is_enabled': True,
                'is_default': False,
                'notes': 'Custom meeting link.',
            },
        ]
        for item in default_configs:
            prov = item['provider']
            if not cls.objects.filter(provider=prov).exists():
                cls.objects.create(**item)

    @classmethod
    def get_setting(cls, provider_code: str):
        try:
            cls.ensure_default_providers()
            return cls.objects.filter(provider=provider_code).first()
        except Exception:
            return None


