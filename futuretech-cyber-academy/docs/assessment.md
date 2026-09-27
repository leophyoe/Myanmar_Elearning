# Assessment Engine & Gradebook Architecture

## 1. Grading Formula & Weights

Assessment grades are calculated dynamically per course based on `AssessmentWeight` records:

| Assessment Category | Default Weight | Model Representation |
| :--- | :--- | :--- |
| **Assignments** | 10% | `AssignmentSubmission` (Latest Feedback Score) |
| **Quizzes** | 10% | `QuizAttempt` (Passed Attempt Scores) |
| **Practical Labs** | 25% | `LessonProgress` (`PRACTICAL` lesson completion) |
| **Module Exams** | 20% | `ExamAttempt` (`MODULE_EXAM`, `MIDTERM`) |
| **Practical Exam** | 15% | `ExamAttempt` (`PRACTICAL`) |
| **Final Project** | 20% | `ExamAttempt` (`FINAL`) |
| **Total** | **100%** | `GradeCalculationService.calculate_student_grade()` |

$$\text{Final Grade} = \sum (\text{Category Score} \times \text{Category Weight})$$

### Letter Grade Rubric
- **A+**: $\ge 90.0\%$
- **A**: $85.0\% - 89.9\%$
- **B+**: $80.0\% - 84.9\%$
- **B**: $75.0\% - 79.9\%$
- **C+**: $70.0\% - 74.9\%$
- **C**: $60.0\% - 69.9\%$
- **F**: $< 60.0\%$ (Fail)

---

## 2. Server-Authoritative Anti-Cheat Safeguards

1. **Zero-Trust Answer Key Secrecy**:
   - Answer options rendered in HTML templates do NOT contain answer key attributes (`data-correct`, `is_correct`, etc.).
   - Grading is performed purely server-side in `QuizGradingService.grade_attempt()`.

2. **Server-Enforced Countdown Timer**:
   - `expires_at` is generated upon test initiation on the backend.
   - Client clocks and JavaScript timers are decorative only; any submission received past `expires_at + 60s` grace period triggers a hard HTTP rejection.

3. **Rate Limiting & Max Attempt Guards**:
   - Number of attempts per quiz/exam is tracked atomically.
   - Starting an attempt beyond `max_attempts` raises an exception and is logged in `AuditLog`.

4. **Malicious File Upload Filtering**:
   - All submissions are analyzed by `validate_resource_file`. Executable headers (`MZ`, `ELF`) and dangerous extensions are stripped or rejected.

