import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.core.validators import validate_resource_file


# ==============================================================================
# ENUMS & CHOICES
# ==============================================================================

class LabType(models.TextChoices):
    GUIDED = 'GUIDED', 'Guided Lab'
    MACHINE = 'MACHINE', 'Practice Machine'
    CHALLENGE = 'CHALLENGE', 'Standalone Challenge'
    BLUE_TEAM = 'BLUE_TEAM', 'Blue Team Defense'
    FORENSICS = 'FORENSICS', 'Digital Forensics'
    SOC = 'SOC', 'SOC Investigation'
    NETWORK = 'NETWORK', 'Network Analysis'
    CLOUD = 'CLOUD', 'Cloud Security'
    WEB = 'WEB', 'Web Security'
    WEB_APPLICATION = 'WEB_APPLICATION', 'Web Application Lab'
    PRACTICAL_EXAM = 'PRACTICAL_EXAM', 'Practical Exam'
    CAPSTONE = 'CAPSTONE', 'Capstone Enterprise Range'


class LabDifficulty(models.TextChoices):
    BEGINNER = 'BEGINNER', 'Beginner'
    EASY = 'EASY', 'Easy'
    MEDIUM = 'MEDIUM', 'Medium'
    HARD = 'HARD', 'Hard'
    ADVANCED = 'ADVANCED', 'Advanced'
    INSANE = 'INSANE', 'Insane'


class LabAccessType(models.TextChoices):
    TERMINAL = 'TERMINAL', 'Browser Terminal Only'
    WEB = 'WEB', 'Web Application Only'
    BOTH = 'BOTH', 'Terminal & Web Interface'
    NONE = 'NONE', 'Offline / Downloadable'


class LabInstanceStatus(models.TextChoices):
    CREATING = 'CREATING', 'Creating Environment'
    RUNNING = 'RUNNING', 'Running'
    STOPPING = 'STOPPING', 'Stopping'
    STOPPED = 'STOPPED', 'Stopped'
    EXPIRED = 'EXPIRED', 'Expired'
    RESETTING = 'RESETTING', 'Resetting'
    FAILED = 'FAILED', 'Failed'


class FlagType(models.TextChoices):
    STATIC_FLAG = 'STATIC_FLAG', 'Static Flag'
    DYNAMIC_FLAG = 'DYNAMIC_FLAG', 'Dynamic Instance Flag'


class CTFEventStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    UPCOMING = 'UPCOMING', 'Upcoming'
    LIVE = 'LIVE', 'Live'
    ENDED = 'ENDED', 'Ended'


# ==============================================================================
# 1. LAB CATEGORY & CORE LAB MODELS
# ==============================================================================

class LabCategory(BaseModel):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=64, default="terminal", help_text="Lucide or Tabler icon identifier")

    class Meta:
        verbose_name_plural = "Lab Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Lab(BaseModel):
    """
    Central definition of a cyber range training lab or machine.
    Uses an allowlisted configuration pattern for Docker isolation.
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    short_description = models.CharField(max_length=512)
    description = models.TextField()
    category = models.ForeignKey(LabCategory, on_delete=models.PROTECT, related_name='labs')
    difficulty = models.CharField(max_length=32, choices=LabDifficulty.choices, default=LabDifficulty.MEDIUM, db_index=True)
    module = models.ForeignKey('courses.CourseModule', on_delete=models.SET_NULL, null=True, blank=True, related_name='labs')
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='labs')
    type = models.CharField(max_length=32, choices=LabType.choices, default=LabType.GUIDED, db_index=True)
    estimated_minutes = models.PositiveIntegerField(default=60)
    points = models.PositiveIntegerField(default=100)

    # Allowlisted Container Specifications
    docker_image = models.CharField(max_length=255, default="cyber-range/linux-base:latest", help_text="Approved Docker image repository/tag")
    docker_compose_definition = models.TextField(blank=True, help_text="Multi-container lab definition in YAML format")

    # Access Gateways
    access_type = models.CharField(max_length=32, choices=LabAccessType.choices, default=LabAccessType.TERMINAL)
    terminal_enabled = models.BooleanField(default=True)
    web_access_enabled = models.BooleanField(default=False)

    # Resource Constraints
    max_runtime_minutes = models.PositiveIntegerField(default=60, help_text="Instance TTL timeout before auto-teardown")
    cpu_limit = models.CharField(max_length=16, default="1.0", help_text="Docker CPU limit quota e.g. '0.5' or '1.0'")
    memory_limit_mb = models.PositiveIntegerField(default=512, help_text="RAM ceiling in Megabytes")
    storage_limit_mb = models.PositiveIntegerField(default=1024, help_text="Storage quota in Megabytes")
    process_limit = models.PositiveIntegerField(default=100, help_text="PIDs limit to prevent fork bombs")

    # Source & Attribution Metadata
    source_name = models.CharField(max_length=128, default="Future Tech", blank=True, help_text="Origin of lab, e.g. LabEx, OWASP, Future Tech")
    source_url = models.URLField(blank=True, help_text="Upstream repository or source URL")
    source_type = models.CharField(max_length=64, default="INTERNAL", blank=True, help_text="INTERNAL, OPEN_SOURCE, COMMUNITY")
    attribution_required = models.BooleanField(default=False, help_text="Whether upstream attribution must be displayed")
    license_name = models.CharField(max_length=128, blank=True, default="Proprietary", help_text="License of upstream lab, e.g. Apache-2.0, MIT")
    display_order = models.PositiveIntegerField(default=0, db_index=True, help_text="Catalog display order")

    is_published = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_labs')

    class Meta:
        ordering = ['display_order', '-created_at']
        indexes = [
            models.Index(fields=['slug', 'is_published']),
            models.Index(fields=['type', 'difficulty']),
            models.Index(fields=['source_name', 'is_published']),
            models.Index(fields=['display_order']),
        ]

    def __str__(self):
        return f"[{self.get_type_display()}] {self.name} ({self.difficulty})"


class LabVersion(BaseModel):
    """
    Immutable version history of a lab's container definition and challenges.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    docker_image = models.CharField(max_length=255)
    docker_compose_definition = models.TextField(blank=True)
    changelog = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('lab', 'version_number')]

    def __str__(self):
        return f"{self.lab.name} v{self.version_number}"


class LabInstance(BaseModel):
    """
    Isolated container session instantiated for a single student.
    Guaranteed zero cross-student interference.
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='instances')
    lab_version = models.ForeignKey(LabVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='instances')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_instances')
    container_id = models.CharField(max_length=128, blank=True, help_text="Internal Docker container ID")
    status = models.CharField(max_length=32, choices=LabInstanceStatus.choices, default=LabInstanceStatus.CREATING, db_index=True)
    internal_address = models.CharField(max_length=64, blank=True, help_text="Assigned isolated lab network IP")
    access_url = models.CharField(max_length=255, blank=True, help_text="Internal gateway access URI")
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    resource_usage = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['lab', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.lab.name} [{self.status}]"

    @property
    def is_running(self):
        return self.status == LabInstanceStatus.RUNNING

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def assigned_ip(self):
        return self.internal_address

    @assigned_ip.setter
    def assigned_ip(self, value):
        self.internal_address = value

    @property
    def port_mappings(self):
        if isinstance(self.resource_usage, dict):
            return self.resource_usage.get('port_mappings', '80/tcp, 443/tcp')
        return '80/tcp, 443/tcp'

    @port_mappings.setter
    def port_mappings(self, value):
        if not isinstance(self.resource_usage, dict):
            self.resource_usage = {}
        self.resource_usage['port_mappings'] = value


class LabAccess(BaseModel):
    """
    Explicit cohort or student access grant for private / restricted labs.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='access_grants')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_access_grants')
    is_unlocked = models.BooleanField(default=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('lab', 'student')]

    def __str__(self):
        return f"{self.student.username} access to {self.lab.name}"


class LabObjective(BaseModel):
    """
    Step-by-step practical targets within a lab scenario.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='objectives')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    points = models.PositiveIntegerField(default=25)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Objective {self.order}: {self.title} ({self.points} pts)"


class LabHint(BaseModel):
    """
    Progressive instructional hints with configurable score penalties.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='hints')
    order = models.PositiveSmallIntegerField(default=1)
    hint_text = models.TextField()
    penalty_percent = models.PositiveSmallIntegerField(default=10, help_text="Percentage deduction e.g. 10% penalty")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Hint {self.order} for {self.lab.name} (-{self.penalty_percent}%)"


class LabAttachment(BaseModel):
    """
    Downloadable forensic PCAP, binary artifacts, or triage memory images.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='labs/attachments/', validators=[validate_resource_file])
    filename = models.CharField(max_length=255)
    file_size_bytes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.filename} ({self.lab.name})"


class LabFlag(BaseModel):
    """
    Cryptographic flag representation.
    Never exposed in client HTML, API responses, or JS payloads.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='flags')
    objective = models.ForeignKey(LabObjective, on_delete=models.SET_NULL, null=True, blank=True, related_name='flags')
    flag_type = models.CharField(max_length=32, choices=FlagType.choices, default=FlagType.STATIC_FLAG)
    static_flag = models.CharField(max_length=255, blank=True, help_text="Server-side secret flag")
    dynamic_flag_pattern = models.CharField(max_length=255, default="FTCSA{instance_uuid}", help_text="Template for dynamic instance flags")
    points = models.PositiveIntegerField(default=50)

    def __str__(self):
        return f"Flag ({self.flag_type}) for {self.lab.name}: {self.points} pts"


class LabSubmission(BaseModel):
    """
    Audit log of flag submissions with automated server-side verification.
    """
    instance = models.ForeignKey(LabInstance, on_delete=models.SET_NULL, null=True, blank=True, related_name='submissions')
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_submissions')
    flag_submitted = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['student', 'lab', 'is_correct']),
        ]

    def __str__(self):
        res = "CORRECT" if self.is_correct else "INCORRECT"
        return f"{self.student.username} -> {self.lab.name} [{res} - {self.points_awarded} pts]"


# ==============================================================================
# 2. STANDALONE CHALLENGE SYSTEM
# ==============================================================================

class ChallengeCategory(BaseModel):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=64, default="flag")

    class Meta:
        verbose_name_plural = "Challenge Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Challenge(BaseModel):
    """
    Jeopardy-style CTF challenge (Web, Crypto, Forensics, Reverse Engineering, OSINT).
    """
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    category = models.ForeignKey(ChallengeCategory, on_delete=models.PROTECT, related_name='challenges')
    difficulty = models.CharField(max_length=32, choices=LabDifficulty.choices, default=LabDifficulty.EASY, db_index=True)
    points = models.PositiveIntegerField(default=100)
    description = models.TextField()
    instructions = models.TextField(blank=True)
    flag = models.CharField(max_length=255, help_text="Stored strictly server-side")
    is_active = models.BooleanField(default=True, db_index=True)
    solves_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['difficulty', 'points']

    def __str__(self):
        return f"[{self.category.name}] {self.title} ({self.points} pts)"


class ChallengeSubmission(BaseModel):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_submissions')
    flag_submitted = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['student', 'challenge', 'is_correct']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.challenge.title} ({'Solved' if self.is_correct else 'Failed'})"


# ==============================================================================
# 3. CTF EVENTS, TEAMS & LEADERBOARDS
# ==============================================================================

class CTFEvent(BaseModel):
    """
    Scheduled competitive CTF tournament with live scoreboard.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    registration_start = models.DateTimeField(null=True, blank=True)
    registration_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=CTFEventStatus.choices, default=CTFEventStatus.DRAFT, db_index=True)
    max_participants = models.PositiveIntegerField(default=100)
    is_team_event = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.name} [{self.get_status_display()}]"

    @property
    def is_live(self):
        now = timezone.now()
        return self.status == CTFEventStatus.LIVE or (self.start_time <= now <= self.end_time)


class CTFEventChallenge(BaseModel):
    event = models.ForeignKey(CTFEvent, on_delete=models.CASCADE, related_name='event_challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='event_appearances')
    points = models.PositiveIntegerField(default=100)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = [('event', 'challenge')]

    def __str__(self):
        return f"{self.event.name} -> {self.challenge.title} ({self.points} pts)"


class CTFTeam(BaseModel):
    event = models.ForeignKey(CTFEvent, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=128)
    join_code = models.CharField(max_length=32, unique=True)
    leader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='led_teams')
    score = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('event', 'name')]

    def __str__(self):
        return f"Team {self.name} ({self.score} pts)"


class CTFTeamMember(BaseModel):
    team = models.ForeignKey(CTFTeam, on_delete=models.CASCADE, related_name='members')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('team', 'student')]

    def __str__(self):
        return f"{self.student.username} in {self.team.name}"


class CTFScore(BaseModel):
    """
    Cumulative student scoring ledger across labs and CTF challenges.
    """
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ctf_score')
    points = models.PositiveIntegerField(default=0, db_index=True)
    lab_points = models.PositiveIntegerField(default=0)
    challenge_points = models.PositiveIntegerField(default=0)
    solves_count = models.PositiveIntegerField(default=0)
    labs_completed_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-points', '-updated_at']

    def __str__(self):
        return f"{self.student.username}: {self.points} pts (Solves: {self.solves_count})"


# ==============================================================================
# 4. CYBER RANGE BADGES
# ==============================================================================

class Badge(BaseModel):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    icon = models.CharField(max_length=64, default="shield")
    points = models.PositiveIntegerField(default=50)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} (+{self.points} pts)"


class StudentBadge(BaseModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awarded_students')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('student', 'badge')]
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.student.username} earned {self.badge.title}"


# ==============================================================================
# 5. EXTERNAL CHALLENGE & PRACTICE RESOURCES
# ==============================================================================

class ExternalResource(BaseModel):
    """
    Catalog of accredited external cybersecurity challenge and practice resources.
    Integrated strictly as source links without scraping or reproducing proprietary third-party content.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    url = models.URLField(help_text="Official external resource URL")
    source_type = models.CharField(max_length=64, default="EXTERNAL_RESOURCE")
    description = models.TextField(blank=True)
    category = models.ForeignKey(ChallengeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='external_resources')
    attribution = models.CharField(max_length=255, default="HackerTest.net", help_text="Upstream credit and platform attribution")
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Associated learning path disciplines e.g. Cyber Security Fundamentals, Ethical Hacking, Web Security, Security Challenges")

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "External Practice Resource"
        verbose_name_plural = "External Practice Resources"

    def __str__(self):
        return f"{self.name} ({self.attribution})"

