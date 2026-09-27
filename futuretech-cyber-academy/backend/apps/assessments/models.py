from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import BaseModel
from apps.core.validators import validate_resource_file


class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = 'MULTIPLE_CHOICE', 'Multiple Choice (Single Answer)'
    MULTIPLE_SELECT = 'MULTIPLE_SELECT', 'Multiple Select (Multiple Answers)'
    TRUE_FALSE = 'TRUE_FALSE', 'True / False'
    SHORT_ANSWER = 'SHORT_ANSWER', 'Short Answer'
    PRACTICAL_LAB = 'PRACTICAL_LAB', 'Practical Lab Task'


class QuestionDifficulty(models.TextChoices):
    EASY = 'EASY', 'Easy'
    MEDIUM = 'MEDIUM', 'Medium'
    HARD = 'HARD', 'Hard'


class QuestionBank(BaseModel):
    """
    Central repository of reusable questions categorized by cyber security domain and difficulty.
    """
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=128, default="Cybersecurity", db_index=True)
    difficulty = models.CharField(max_length=32, choices=QuestionDifficulty.choices, default=QuestionDifficulty.MEDIUM)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='question_bank_items')

    def __str__(self):
        return f"[{self.category}] {self.title} ({self.difficulty})"


# ==============================================================================
# 1. QUIZ SYSTEM
# ==============================================================================

class Quiz(BaseModel):
    """
    Formative knowledge check per lesson or module with automated server-side grading.
    """
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='quizzes')
    module = models.ForeignKey('courses.CourseModule', on_delete=models.SET_NULL, null=True, blank=True, related_name='quizzes')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.SET_NULL, null=True, blank=True, related_name='quizzes')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    instructions_en = models.TextField(blank=True)
    instructions_my = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=15, help_text="Time limit in minutes. 0 for untimed.")
    passing_score = models.PositiveIntegerField(default=70, help_text="Passing score percentage (0-100)")
    max_attempts = models.PositiveIntegerField(default=3, help_text="Maximum allowed attempts")
    randomize_questions = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True, db_index=True)
    is_required = models.BooleanField(default=True)
    hide_answers_after_submission = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return f"{self.course.title}: {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_instructions(self, lang='en'):
        if lang == 'my' and self.instructions_my:
            return self.instructions_my
        return self.instructions_en or self.description

    @property
    def total_points(self):
        return sum(q.points for q in self.questions.filter(is_active=True))

    @property
    def question_count(self):
        return self.questions.filter(is_active=True).count()


class Question(BaseModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')
    question_bank = models.ForeignKey(QuestionBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    question_text = models.TextField()
    question_en = models.TextField(blank=True)
    question_my = models.TextField(blank=True)
    question_type = models.CharField(max_length=32, choices=QuestionType.choices, default=QuestionType.MULTIPLE_CHOICE)
    points = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    order = models.PositiveSmallIntegerField(default=1)
    explanation = models.TextField(blank=True, help_text="Educational explanation shown after quiz grading")
    explanation_en = models.TextField(blank=True)
    explanation_my = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:60]}"

    def get_question_text(self, lang='en'):
        if lang == 'my' and self.question_my:
            return self.question_my
        return self.question_en or self.question_text

    def get_explanation(self, lang='en'):
        if lang == 'my' and self.explanation_my:
            return self.explanation_my
        return self.explanation_en or self.explanation


class QuestionOption(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=512)
    option_en = models.CharField(max_length=512, blank=True)
    option_my = models.CharField(max_length=512, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.option_text} ({'Correct' if self.is_correct else 'Incorrect'})"

    def get_option_text(self, lang='en'):
        if lang == 'my' and self.option_my:
            return self.option_my
        return self.option_en or self.option_text


class QuizAttempt(BaseModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveSmallIntegerField(default=1)
    score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'quiz', 'passed']),
        ]

    def __str__(self):
        status = "PASSED" if self.passed else ("FAILED" if self.is_completed else "IN PROGRESS")
        return f"{self.student.username} - {self.quiz.title} (Attempt #{self.attempt_number}) [{status}: {self.percentage}%]"


class QuizAnswer(BaseModel):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='quiz_answers')
    selected_options = models.JSONField(default=list, blank=True)  # list of UUID strings
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Answer for Q: {self.question_id} - Points: {self.points_awarded}"


# ==============================================================================
# 2. ASSIGNMENT SYSTEM
# ==============================================================================

class AssignmentStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    CLOSED = 'CLOSED', 'Closed'


class Assignment(BaseModel):
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='assignments')
    module = models.ForeignKey('courses.CourseModule', on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    instructions = models.TextField(help_text="Detailed grading rubric and task instructions")
    instructions_en = models.TextField(blank=True)
    instructions_my = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('100.00'))
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('70.00'))
    allowed_file_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed extensions, e.g. ['pdf', 'docx', 'txt', 'zip']"
    )
    max_file_size_mb = models.PositiveIntegerField(default=25)
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=32, choices=AssignmentStatus.choices, default=AssignmentStatus.PUBLISHED, db_index=True)

    class Meta:
        ordering = ['due_date', 'created_at']

    def __str__(self):
        return f"{self.course.title}: {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_instructions(self, lang='en'):
        if lang == 'my' and self.instructions_my:
            return self.instructions_my
        return self.instructions_en or self.instructions


class SubmissionStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'Submitted (Pending Grading)'
    GRADED = 'GRADED', 'Graded'
    RESUBMITTED = 'RESUBMITTED', 'Resubmitted'


class AssignmentSubmission(BaseModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_submissions')
    submitted_file = models.FileField(
        upload_to='assignments/submissions/',
        validators=[validate_resource_file],
        null=True,
        blank=True
    )
    submission_text = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=SubmissionStatus.choices, default=SubmissionStatus.SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField(auto_now=True)
    version = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [('assignment', 'student')]
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['assignment', 'status']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.assignment.title} ({self.status})"

    @property
    def latest_feedback(self):
        return self.feedbacks.order_by('-graded_at').first()


class AssignmentFeedback(BaseModel):
    submission = models.ForeignKey(AssignmentSubmission, on_delete=models.CASCADE, related_name='feedbacks')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='graded_assignments')
    score = models.DecimalField(max_digits=6, decimal_places=2)
    feedback = models.TextField()
    graded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-graded_at']

    def __str__(self):
        return f"Feedback on {self.submission.id} by {self.instructor.username}: {self.score}"


# ==============================================================================
# 3. EXAMINATION SYSTEM
# ==============================================================================

class ExamType(models.TextChoices):
    MODULE_EXAM = 'MODULE_EXAM', 'Module Examination'
    MIDTERM = 'MIDTERM', 'Midterm Examination'
    PRACTICAL = 'PRACTICAL', 'Practical Lab Examination'
    FINAL = 'FINAL', 'Final Comprehensive Diploma Exam'


class Exam(BaseModel):
    """
    Summative formal examination with server-enforced countdown timer.
    """
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='exams')
    module = models.ForeignKey('courses.CourseModule', on_delete=models.SET_NULL, null=True, blank=True, related_name='exams')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    instructions_en = models.TextField(blank=True)
    instructions_my = models.TextField(blank=True)
    exam_type = models.CharField(max_length=32, choices=ExamType.choices, default=ExamType.MODULE_EXAM)
    duration_minutes = models.PositiveIntegerField(default=60, help_text="Strict server-enforced exam duration in minutes")
    passing_score = models.PositiveIntegerField(default=70, help_text="Passing percentage (0-100)")
    max_attempts = models.PositiveIntegerField(default=1, help_text="Number of exam sittings allowed (typically 1)")
    randomize_questions = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.get_exam_type_display()}] {self.course.title} - {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_instructions(self, lang='en'):
        if lang == 'my' and self.instructions_my:
            return self.instructions_my
        return self.instructions_en or self.description

    @property
    def total_points(self):
        return sum(q.points for q in self.questions.filter(is_active=True))


class ExamQuestion(BaseModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_en = models.TextField(blank=True)
    question_my = models.TextField(blank=True)
    question_type = models.CharField(max_length=32, choices=QuestionType.choices, default=QuestionType.MULTIPLE_CHOICE)
    points = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    order = models.PositiveSmallIntegerField(default=1)
    explanation = models.TextField(blank=True)
    explanation_en = models.TextField(blank=True)
    explanation_my = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Exam Q{self.order}: {self.question_text[:60]}"

    def get_question_text(self, lang='en'):
        if lang == 'my' and self.question_my:
            return self.question_my
        return self.question_en or self.question_text

    def get_explanation(self, lang='en'):
        if lang == 'my' and self.explanation_my:
            return self.explanation_my
        return self.explanation_en or self.explanation


class ExamOption(BaseModel):
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=512)
    option_en = models.CharField(max_length=512, blank=True)
    option_my = models.CharField(max_length=512, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.option_text} ({'Correct' if self.is_correct else 'Incorrect'})"

    def get_option_text(self, lang='en'):
        if lang == 'my' and self.option_my:
            return self.option_my
        return self.option_en or self.option_text


class ExamAttempt(BaseModel):
    """
    Formal exam attempt. Timing is strictly enforced via `expires_at` calculated server-side.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_attempts')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveSmallIntegerField(default=1)
    score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['student', 'exam', 'passed']),
        ]

    def __str__(self):
        status = "PASSED" if self.passed else ("FAILED" if self.is_completed else "IN PROGRESS")
        return f"{self.student.username} - {self.exam.title} [{status}: {self.percentage}%]"

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        # 60 seconds grace period for network latency
        return timezone.now() > (self.expires_at + timezone.timedelta(seconds=60))


class ExamAnswer(BaseModel):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='exam_answers')
    selected_options = models.JSONField(default=list, blank=True)
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"ExamAnswer {self.question_id} - Points: {self.points_awarded}"


class PracticalLabTask(BaseModel):
    """
    Architectural placeholder interface for Phase 3 Cyber Range isolated container labs.
    Allows exams and courses to specify lab exercises that will launch Docker containers in Phase 3.
    """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='lab_tasks', null=True, blank=True)
    title = models.CharField(max_length=255)
    instructions = models.TextField()
    docker_template_id = models.CharField(max_length=128, default="cyber-range/linux-security-lab")
    points = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))
    verification_method = models.CharField(max_length=64, default="AUTOMATED_FLAG")

    def __str__(self):
        return f"Lab Task: {self.title} ({self.docker_template_id})"


# ==============================================================================
# 4. GRADEBOOK & ASSESSMENT WEIGHTS
# ==============================================================================

class AssessmentWeight(BaseModel):
    """
    Configurable grading weight formula per course.
    Defaults conform to the institutional diploma rubric:
    Assignments: 10%
    Quizzes: 10%
    Practical Labs: 25%
    Module Exams: 20%
    Practical Exam: 15%
    Final Project: 20%
    Total = 100%
    """
    course = models.OneToOneField('courses.Course', on_delete=models.CASCADE, related_name='assessment_weight')
    assignments_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    quizzes_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    labs_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('25.00'))
    module_exams_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    practical_exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('15.00'))
    final_project_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))

    def __str__(self):
        return f"Weights for {self.course.title}"

    @property
    def total_weight(self):
        return (
            self.assignments_weight +
            self.quizzes_weight +
            self.labs_weight +
            self.module_exams_weight +
            self.practical_exam_weight +
            self.final_project_weight
        )


# ==============================================================================
# 5. FINAL PROJECT & CAPSTONE SYSTEM
# ==============================================================================

class ProjectStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SUBMITTED = 'SUBMITTED', 'Submitted (Pending Review)'
    GRADING = 'GRADING', 'Under Review'
    GRADED = 'GRADED', 'Graded & Approved'
    RETURNED = 'RETURNED', 'Returned for Revision'
    RESUBMISSION_REQUIRED = 'RESUBMISSION_REQUIRED', 'Resubmission Required'


class FinalProject(BaseModel):
    course = models.OneToOneField('courses.Course', on_delete=models.CASCADE, related_name='final_project')
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    title_my = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    description_en = models.TextField(blank=True)
    description_my = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    requirements_en = models.TextField(blank=True)
    requirements_my = models.TextField(blank=True)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('100.00'))
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('70.00'))
    is_required = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Final Project: {self.course.title} - {self.title}"

    def get_title(self, lang='en'):
        if lang == 'my' and self.title_my:
            return self.title_my
        return self.title_en or self.title

    def get_description(self, lang='en'):
        if lang == 'my' and self.description_my:
            return self.description_my
        return self.description_en or self.description


class ProjectSubmission(BaseModel):
    project = models.ForeignKey(FinalProject, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_submissions')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    repository_url = models.URLField(blank=True)
    submitted_file = models.FileField(
        upload_to='projects/submissions/',
        validators=[validate_resource_file],
        null=True,
        blank=True
    )
    status = models.CharField(max_length=32, choices=ProjectStatus.choices, default=ProjectStatus.SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField(auto_now=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    feedback = models.TextField(blank=True)
    presentation_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    presentation_feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_projects')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('project', 'student')]
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.project.title} ({self.status}: {self.score})"

    @property
    def passed(self):
        return self.status == ProjectStatus.GRADED and self.score >= self.project.passing_score

