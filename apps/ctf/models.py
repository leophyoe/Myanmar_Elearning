import hashlib
from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class ChallengeCategory(models.TextChoices):
    WEB = 'web', 'Web Application Security'
    LINUX = 'linux', 'Linux & Privilege Escalation'
    NETWORK = 'network', 'Network Security & PCAP'
    FORENSICS = 'forensics', 'Digital Forensics & Memory'
    OSINT = 'osint', 'Open Source Intelligence (OSINT)'
    CRYPTOGRAPHY = 'cryptography', 'Cryptography & Ciphers'
    PROGRAMMING = 'programming', 'Security Automation & Python'
    CLOUD = 'cloud', 'Cloud Security & Containers'
    SOC = 'soc', 'SOC & Threat Hunting'
    INCIDENT_RESPONSE = 'incident_response', 'Incident Response & IOCs'


class ChallengeDifficulty(models.TextChoices):
    EASY = 'easy', 'Easy'
    MEDIUM = 'medium', 'Medium'
    HARD = 'hard', 'Hard'


class Challenge(BaseModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=32, choices=ChallengeCategory.choices, db_index=True)
    difficulty = models.CharField(max_length=16, choices=ChallengeDifficulty.choices, default=ChallengeDifficulty.EASY)
    description = models.TextField()
    points = models.PositiveIntegerField(default=100)
    flag_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA-256 hash for static flags. (Dynamic flags use the associated LabInstance)."
    )
    is_dynamic = models.BooleanField(default=True, help_text="True if flag is generated dynamically per container")
    lab = models.OneToOneField(
        'labs.Lab',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ctf_challenge'
    )
    module = models.ForeignKey(
        'courses.Module',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='challenges'
    )
    hints = models.JSONField(default=list, blank=True, help_text="Array of hints: [{'hint': '...', 'cost': 10}]")
    max_attempts = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ['points', 'title']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title} ({self.points} pts)"

    def set_static_flag(self, flag_text):
        """Sets the flag as an irreversible SHA-256 hash. Plaintext is never stored."""
        self.flag_hash = hashlib.sha256(flag_text.strip().encode()).hexdigest()
        self.is_dynamic = False


class FlagSubmission(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flag_submissions')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='submissions')
    submitted_flag_clean = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempt_number = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "CORRECT" if self.is_correct else "INCORRECT"
        return f"{self.user.username} -> {self.challenge.title} [{status}]"


class SolvedChallenge(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solved_challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='solves')
    points_awarded = models.PositiveIntegerField()
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'challenge')]
        ordering = ['-solved_at']

    def __str__(self):
        return f"{self.user.username} solved {self.challenge.title} (+{self.points_awarded} pts)"

