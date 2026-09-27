from django.db import models
from django.conf import settings
from apps.common.models import BaseModel

class FinalProject(BaseModel):
    title = models.CharField(max_length=255, default="Cyber Security Capstone Project")
    slug = models.SlugField(unique=True)
    description = models.TextField()
    rubric = models.JSONField(
        default=dict,
        help_text="Grading criteria: Proposal (15%), Lab Design (20%), Assessment (25%), Report (20%), Viva (20%)"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class ProjectSubmission(BaseModel):
    project = models.ForeignKey(FinalProject, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_submissions')
    proposal_text = models.TextField()
    report_file = models.FileField(upload_to='capstone_reports/', null=True, blank=True)
    github_repo_url = models.URLField(blank=True)
    defense_date = models.DateTimeField(null=True, blank=True)
    viva_score = models.PositiveSmallIntegerField(null=True, blank=True)
    final_grade = models.CharField(max_length=16, blank=True)
    feedback = models.TextField(blank=True)
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluated_projects'
    )

    class Meta:
        unique_together = [('project', 'student')]

    def __str__(self):
        return f"{self.project.title} - {self.student.username}"

