# Learning Management System (LMS) & Academic Architecture

## 1. Overview
Future Tech Academy's Phase 2 Advanced E-Learning System provides a zero-trust academic environment tailored for cybersecurity and computer science diplomas. The LMS integrates modular learning paths, interactive quizzes, hands-on assignment submissions with instructor feedback, summative examinations, institutional gradebooks, and gamified achievement badges.

---

## 2. Core Subsystems

### 2.1 Learning Path System (`apps.learning_paths`)
- **Purpose**: Roadmaps students through progressive cohorts from Beginner to Advanced cybersecurity engineering.
- **Pre-configured Paths**:
  1. `Cyber Security Beginner`: Networking -> Linux -> Diploma in Cyber Security.
  2. `Ethical Hacking Path`: Linux -> Networking -> Offensive Pentesting.
  3. `SOC Analyst Path`: Networking -> Linux -> Defense & Wazuh SIEM.
  4. `Digital Forensics Path`: Linux Systems -> Filesystem & Memory Triage.
  5. `Cloud Security Path`: Networking -> Linux -> Cloud IAM & Container Isolation.
- **Progress Aggregation**: Cumulative weighted progress calculated automatically across all sequenced courses via `StudentLearningPath.recalculate_progress()`.

### 2.2 Formative Quiz System (`apps.assessments`)
- **Question Types Supported**:
  - `MULTIPLE_CHOICE`: Single option selection.
  - `MULTIPLE_SELECT`: Multiple option selection (all correct required).
  - `TRUE_FALSE`: Binary boolean verification.
  - `SHORT_ANSWER`: Text pattern matching.
- **Zero-Trust Security**:
  - The answer key (`is_correct`) is strictly confined to the backend server and database.
  - The HTML template and context never receive `is_correct` flags during quiz-taking.
  - Maximum attempt enforcement prevents brute-forcing answers.

### 2.3 Assignment System (`apps.assessments`)
- **Workflow**: Student Submission -> Instructor Grading Queue -> In-depth Feedback -> Gradebook.
- **File Validation**: Enforces strict extension whitelisting (`['pdf', 'zip']`) and rejects malicious extensions (`.exe`, `.sh`, `.elf`, `.bat`, `.cmd`, `.py`) via `validate_resource_file`.
- **Versioning**: Resubmissions increment the version counter, maintaining an audit trail.

### 2.4 Summative Examination System (`apps.assessments`)
- **Exam Types**:
  - `MODULE_EXAM`: Per-module summative test.
  - `MIDTERM`: Core midway milestone.
  - `PRACTICAL`: Live triage and forensic memory analysis.
  - `FINAL`: Comprehensive 14-module diploma examination.
- **Server-Authoritative Timer**:
  - Expiration timestamp `expires_at` is calculated and anchored on the database server at start.
  - Submissions received after `expires_at + 60s` grace period are rejected by `ExamTimerService`.
- **Phase 3 Ready**: Includes `PracticalLabTask` models specifying Docker template IDs (e.g., `cyber-range/web-triage-lab`) for seamless transition to live Docker containers in Phase 3.

### 2.5 Gamification & Achievements (`apps.achievements`)
- **Milestone Badges**:
  - `FIRST_STEP` (Bronze, 10 XP): Course enrollment.
  - `QUIZ_EXPLORER` (Bronze, 20 XP): Completing first quiz.
  - `PERFECT_SCORE` (Gold, 50 XP): 100% score on any assessment.
  - `MISSION_SUBMITTED` (Silver, 30 XP): Submitting practical assignment.
  - `COURSE_COMPLETER` (Platinum, 100 XP): Completing 100% of coursework.
  - `CERTIFIED_SPECIALIST` (Platinum, 100 XP): Earning a digital diploma.
  - `LINUX_MASTER` (Gold, 50 XP): Linux track mastery.
  - `NETWORK_DEFENDER` (Gold, 50 XP): Networking track mastery.
- **Notification Trigger**: Unlocking badges pushes persistent notifications to the student's Notification Center.

