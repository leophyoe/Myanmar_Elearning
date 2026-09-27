import hashlib
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.common.models import BaseModel

class LabCategory(models.TextChoices):
    LINUX = 'linux', 'Linux & System Security'
    NETWORKING = 'networking', 'Networking & Packet Analysis'
    WEB = 'web', 'Web Application Security & OWASP'
    WINDOWS = 'windows', 'Windows & Active Directory'
    SOC = 'soc', 'SOC, SIEM & Incident Response'
    FORENSICS = 'forensics', 'Digital Forensics & Malware'
    CLOUD = 'cloud', 'Cloud Security & DevSecOps'
    CAPSTONE = 'capstone', 'Integrated Cyber Range Capstone'


class LabDifficulty(models.TextChoices):
    EASY = 'easy', 'Easy'
    MEDIUM = 'medium', 'Medium'
    HARD = 'hard', 'Hard'


class LabType(models.TextChoices):
    GUIDED = 'guided', 'Guided Lab'
    CHALLENGE = 'challenge', 'Challenge'
    CTF = 'ctf', 'CTF'
    INVESTIGATION = 'investigation', 'Investigation'
    DEFENSIVE = 'defensive', 'Defensive Lab'
    ATTACK_SIMULATION = 'attack_simulation', 'Attack Simulation'
    CAPSTONE = 'capstone', 'Capstone'


class InstanceStatus(models.TextChoices):
    STOPPED = 'stopped', 'Stopped'
    PROVISIONING = 'provisioning', 'Provisioning'
    RUNNING = 'running', 'Running'
    STOPPING = 'stopping', 'Stopping'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'


class LabTemplate(BaseModel):
    """
    Blueprint defining Docker image, compose configuration, and hard cgroup limits.
    """
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=32, choices=LabCategory.choices, default=LabCategory.LINUX)
    description = models.TextField()
    docker_compose_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to template directory inside lab_templates/"
    )
    image_name = models.CharField(
        max_length=255,
        default="ftcr-labs/base-target:latest",
        help_text="Docker image name to instantiate"
    )
    cpu_limit = models.CharField(max_length=16, default="0.5", help_text="e.g. 0.5 vCPU")
    mem_limit = models.CharField(max_length=16, default="512m", help_text="e.g. 512m or 1g")
    pids_limit = models.PositiveIntegerField(default=100, help_text="Max process threads (fork-bomb shield)")
    read_only_root = models.BooleanField(default=True, help_text="Mount root filesystem as read-only")
    default_duration_minutes = models.PositiveIntegerField(default=90)
    flag_pattern = models.CharField(max_length=64, default="FTCR{dynamic}")

    def __str__(self):
        return f"Template: {self.name} ({self.get_category_display()})"


class Lab(BaseModel):
    """
    Educational lab exercise associated with a curriculum lesson or CTF challenge.
    """
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='labs'
    )
    template = models.ForeignKey(LabTemplate, on_delete=models.PROTECT, related_name='labs')
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    difficulty = models.CharField(max_length=16, choices=LabDifficulty.choices, default=LabDifficulty.EASY)
    lab_type = models.CharField(max_length=32, choices=LabType.choices, default=LabType.GUIDED)
    description = models.TextField()
    learning_objectives = models.JSONField(default=list, blank=True)
    prerequisites = models.TextField(blank=True)
    tasks = models.JSONField(
        default=list,
        help_text="Array of tasks: [{'id': 1, 'title': '...', 'hint': '...', 'points': 20, 'flag_required': true}]"
    )
    points = models.PositiveIntegerField(default=100)
    estimated_minutes = models.PositiveIntegerField(default=60)
    instructor_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} [{self.get_difficulty_display()}]"


class LabInstance(BaseModel):
    """
    Active or historical runtime instance of a lab assigned to a student.
    """
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='instances')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lab_instances')
    container_id = models.CharField(max_length=128, blank=True, null=True)
    network_name = models.CharField(max_length=128, blank=True, null=True)
    target_ip = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=InstanceStatus.choices,
        default=InstanceStatus.STOPPED,
        db_index=True
    )
    dynamic_flag = models.CharField(max_length=255, blank=True, null=True)
    flag_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    extensions_used = models.PositiveSmallIntegerField(default=0)
    error_log = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f"LabInstance: {self.lab.title} for {self.user.username} ({self.status})"

    def generate_dynamic_flag(self):
        """Generates a cryptographically strong, non-reusable flag per student instance."""
        token = secrets.token_hex(16)
        flag = f"FTCR{{{self.lab.slug}_{token}}}"
        self.dynamic_flag = flag
        self.flag_hash = hashlib.sha256(flag.encode()).hexdigest()
        return flag

    def is_expired(self):
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    def remaining_seconds(self):
        if not self.expires_at:
            return 0
        diff = (self.expires_at - timezone.now()).total_seconds()
        return max(0, int(diff))


class LabNetwork(BaseModel):
    """
    Dedicated isolated Docker bridge network descriptor for a student instance.
    """
    instance = models.OneToOneField(LabInstance, on_delete=models.CASCADE, related_name='network_record')
    docker_network_id = models.CharField(max_length=128)
    subnet = models.CharField(max_length=32)
    gateway = models.CharField(max_length=32)
    is_internal_only = models.BooleanField(default=True)

    def __str__(self):
        return f"Net: {self.subnet} (Internal={self.is_internal_only})"

