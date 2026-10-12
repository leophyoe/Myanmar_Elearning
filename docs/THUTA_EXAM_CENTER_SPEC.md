# THUTA E-Learning Platform — Exam Center Specification & Architecture

**Document Version:** 1.0.0  
**Status:** Approved & Implemented  
**Author:** THUTA Engineering Team  
**Scope:** Standalone & Course-Embedded Examinations, Evaluator Rubric Grading, Cryptographic Credentialing, and Institutional Cohort Assessment

---

## 1. Executive Summary & Philosophy

In modern e-learning ecosystems, competency evaluation must not be artificially restricted to linear video lecture consumption. Learners possessing prior academic background, professional experience, or self-taught skills must have the freedom to validate their proficiency directly through standardized, proctored examinations.

THUTA introduces the **Exam Center** as a **first-class platform feature**, completely decoupled from mandatory course enrollment:
- **Dual Pathways:** Learners can pursue traditional Course Learning (`Enrollment -> Lessons -> Quizzes -> Final Exam -> Course Completion Certificate`) or take **Standalone Examinations** (`Exam Center -> Free/Paid Voucher -> Standardized Proctored Exam -> Exam-Based Verified Certificate`).
- **Cryptographic Credential Differentiation:** Course Completion Certificates (`MEL-CERT-2026-XXXX`) vs. Exam-Based Verified Certificates (`MEL-EXAM-2026-XXXX`) represent distinct pedagogical achievements.
- **Cheating & Answer Protection:** Strict zero-leak security architecture ensuring correct answers, rubric criteria, and explanations are never transmitted to client DOM or browser memory prior to final submission.
- **Evaluator Rubric Grading Queue:** Comprehensive manual assessment interface for subjective short-answer, coding, and hands-on lab problems based on standardized criterion levels (Levels 3, 2, 1, 0).

---

## 2. Architecture & Data Model

### 2.1 Model Extensions

#### `Quiz` (`apps/courses/models.py`)
```python
class Quiz(BaseModel):
    # Standalone & Pricing Fields
    is_standalone = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Can be taken directly via Exam Center without course enrollment."
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Price for standalone exam access in MMK (0 = Free Exam)."
    )
    currency = models.CharField(max_length=8, default='MMK')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='authored_quizzes',
    )
    assigned_instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_grading_quizzes',
    )
    institution = models.ForeignKey(
        'partner.Institution',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quizzes',
    )
    requires_manual_grading = models.BooleanField(
        default=False,
        help_text="Requires instructor/evaluator review before finalizing score and issuing certificate."
    )
    certificate_type = models.CharField(
        max_length=32,
        choices=[
            ('course_completion', 'Course Completion'),
            ('exam_verified', 'Exam-Based Verified'),
            ('none', 'No Certificate'),
        ],
        default='course_completion',
    )
```

#### `QuizAttempt` (`apps/courses/models.py`)
```python
class QuizAttempt(BaseModel):
    class AttemptStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        PENDING_REVIEW = 'pending_review', 'Pending Manual Grading'
        GRADED = 'graded', 'Graded & Finalized'

    status = models.CharField(
        max_length=32,
        choices=AttemptStatus.choices,
        default=AttemptStatus.SUBMITTED,
        db_index=True,
    )
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='graded_quiz_attempts',
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    rubric_scores = models.JSONField(default=dict, blank=True)
    certificate = models.ForeignKey(
        'certificates.Certificate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quiz_attempts',
    )
```

#### `Certificate` (`apps/certificates/models.py`)
```python
class Certificate(BaseModel):
    class CertificateType(models.TextChoices):
        COURSE_COMPLETION = 'course_completion', 'Course Completion Certificate'
        EXAM_VERIFIED = 'exam_verified', 'Exam-Based Verified Certificate'
        PARTICIPATION = 'participation', 'Certificate of Participation'

    certificate_type = models.CharField(
        max_length=32,
        choices=CertificateType.choices,
        default=CertificateType.COURSE_COMPLETION,
        db_index=True,
    )
    course = models.ForeignKey('courses.Course', null=True, blank=True, on_delete=models.PROTECT)
    exam = models.ForeignKey('courses.Quiz', null=True, blank=True, on_delete=models.SET_NULL)
    exam_score = models.PositiveSmallIntegerField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
```

---

## 3. Security & Anti-Cheating Architecture

1. **Zero-Leak Client Serialization:**
   - Prior to submission, `serialize_exam_for_student(assessment)` strips `Choice.is_correct`, `Question.correct_text_answer`, `Question.rubric_criteria`, and `Question.explanation`.
   - Inspection of browser DevTools (Network tab, DOM elements, or JavaScript variables) reveals only question prompts and clean option identifiers (`id` and `text`).
2. **State Protection & Disconnect Recovery:**
   - Candidate responses and review flags are continuously synchronized to client `localStorage`. If a browser window is accidentally closed or connection drops, candidate progress is restored seamlessly without loss.
3. **Server-Side Evaluation:**
   - All evaluation and point calculations execute inside `apps/courses/services/assessment.py` using atomic database transactions.
4. **Attempt Limits & Availability Windows:**
   - Server-side validation strictly enforces `max_attempts`, `available_from`, and `available_until` before admitting candidates to an exam session.

---

## 4. Candidate Experience: Interactive Testing Interface

Inspired by standardized international testing platforms (Reference Image 1):
- **Sticky Test Header:**
  - Dynamic Question Counter (`Question 2 of 28`).
  - Flag for Review toggle button (`⚑`).
  - Active Countdown Timer with color-coded alerts (cyan -> yellow < 5m -> red flashing < 1m). Auto-submit executes when timer expires.
- **Question Palette Grid:**
  - Interactive numbered tiles (1 to N) reflecting candidate state:
    - Current Active: Bright cyan outline
    - Answered: Emerald filled with checkmark
    - Flagged for Review: Amber flag badge
    - Unanswered: Muted slate
- **Review All Modal:**
  - Comprehensive pre-submission audit displaying total answered vs unanswered vs flagged questions before candidate confirms final submission.

---

## 5. Evaluator Experience: Standardized Rubric Grading

Inspired by institutional exam evaluation suites (Reference Image 2):
- **Grading Queue (`/exams/grading-queue/`):**
  - Displays all candidate attempts with `status=pending_review`.
  - Filterable by specific examination and student candidate.
- **Rubric Grading Screen (`/exams/grading/<uuid:attempt_id>/`):**
  - Side-by-side presentation of question prompt and candidate submitted essay/code.
  - Standardized Criteria Table with 4 evaluation levels:
    - **Level 3 (100%):** Exemplary
    - **Level 2 (70%):** Proficient
    - **Level 1 (40%):** Developing
    - **Level 0 (0%):** Unsatisfactory
  - Granular points override input and per-criterion evaluator comments.
  - Overall comprehensive evaluation feedback textarea.
  - One-click **Finalize Grade & Award Certificate** action that immediately recalculates the final percentage, updates database audit trail, and mints an Exam-Based Verified Certificate upon passing.

---

## 6. Financial & Voucher Integration

- **Free Practice Exams:** Instant entry without payment gate.
- **Paid Verified Exams:** Integrated directly with THUTA's Myanmar payment gateway infrastructure (`PaymentMethod`, MMQR, KBZ Pay, Wave Pay, Bank Transfer).
- Candidate submits transaction proof -> Admin approves payment -> Candidate is immediately entitled to take the examination.
- Revenue share is automatically apportioned between THUTA platform and the designated instructor/institution based on pedagogical level terms.

---

## 7. URL Routing Reference

| URL Path | View | Description |
|---|---|---|
| `/exams/` | `StandaloneExamListView` | Catalog of all standalone & verified exams |
| `/exams/<exam_id>/` | `StandaloneExamDetailView` | Exam overview, syllabus, rules, start/buy CTA |
| `/exams/<exam_id>/checkout/` | `ExamCheckoutView` | Purchase standalone exam voucher |
| `/exams/<exam_id>/take/` | `ExamSessionView` | Interactive timed exam environment |
| `/exams/<exam_id>/submit/` | `ExamSubmitView` | Secure submission processor |
| `/exams/<exam_id>/result/<attempt_id>/` | `ExamResultView` | Score breakdown & certificate release |
| `/exams/grading-queue/` | `ExamGradingQueueView` | Instructor manual evaluation queue |
| `/exams/grading/<attempt_id>/` | `ExamGradingDetailView` | Rubric scoring & certificate finalization |
| `/exams/new/` | `StandaloneExamCreateView` | Teacher exam creation form |
| `/exams/<exam_id>/edit/` | `StandaloneExamUpdateView` | Teacher exam edit form |

