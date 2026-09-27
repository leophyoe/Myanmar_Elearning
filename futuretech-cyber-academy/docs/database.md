# Future Tech Cyber Security Academy — Database Schema & Data Models

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USER ||--o| STUDENT_PROFILE : "has profile"
    USER ||--o| INSTRUCTOR_PROFILE : "has profile"
    USER ||--o| ADMIN_PROFILE : "has profile"
    USER ||--o{ COURSE : "authors (as Instructor)"
    USER ||--o{ ENROLLMENT : "registers (as Student)"
    USER ||--o{ LESSON_PROGRESS : "completes"
    USER ||--o{ NOTIFICATION : "receives"

    COURSE ||--o{ COURSE_MODULE : "contains"
    COURSE ||--o{ ENROLLMENT : "has students"
    COURSE }o--o{ COURSE_CATEGORY : "tagged with"

    COURSE_MODULE ||--o{ LESSON : "structures"
    LESSON ||--o{ COURSE_RESOURCE : "attaches"
    LESSON ||--o{ LESSON_PROGRESS : "tracked by"

    USER {
        uuid id PK
        string email UK
        string username UK
        string role
        boolean is_staff
        boolean is_active
        datetime date_joined
    }

    COURSE {
        uuid id PK
        string title
        string slug UK
        string short_description
        text description
        string level
        string duration
        decimal price
        boolean is_free
        string status
        uuid created_by FK
    }

    COURSE_MODULE {
        uuid id PK
        uuid course_id FK
        string title
        string slug
        int order
        int estimated_hours
        boolean is_published
    }

    LESSON {
        uuid id PK
        uuid module_id FK
        string title
        string slug
        string lesson_type
        text content
        string video_url
        int order
        int estimated_minutes
        boolean is_published
    }

    COURSE_RESOURCE {
        uuid id PK
        uuid lesson_id FK
        string title
        string file
        string resource_type
        string external_link
    }

    ENROLLMENT {
        uuid id PK
        uuid student_id FK
        uuid course_id FK
        string status
        decimal progress_percentage
        datetime enrolled_at
        datetime completed_at
    }

    LESSON_PROGRESS {
        uuid id PK
        uuid student_id FK
        uuid lesson_id FK
        boolean completed
        datetime started_at
        datetime completed_at
        int time_spent_seconds
    }
```

---

## 2. Table Specifications

### 2.1 User (`accounts_user`)
- **Primary Key**: `id` (UUID4, non-sequential to prevent enumeration).
- **Authentication Field**: `email` (Unique, Case-Insensitive Normalized, Indexed).
- **Identifier**: `username` (Unique, auto-generated from email prefix if omitted).
- **Roles**:
  - `SUPER_ADMIN`: Full system dean access.
  - `ACADEMY_ADMIN`: Academy operations and student management.
  - `INSTRUCTOR`: Course authoring and curriculum publishing.
  - `LAB_INSTRUCTOR`: Hands-on lab facilitator.
  - `TEACHING_ASSISTANT`: Grading and tutoring support.
  - `STUDENT`: Enrolled learner.

### 2.2 Course Hierarchy
- **`Course`**: Root diploma or course track. Contains status (`DRAFT`, `PUBLISHED`, `ARCHIVED`).
- **`CourseModule`**: Sequential curriculum phase.
  - Composite Unique Constraints: `('course', 'order')`, `('course', 'slug')`.
- **`Lesson`**: Granular learning unit.
  - Composite Unique Constraints: `('module', 'order')`, `('module', 'slug')`.
  - Content supports rich Markdown and optional embedded video URLs.
- **`CourseResource`**: Downloadable attachments validated against malicious executables (`.exe`, `.sh`, `.bat`, etc.) with a 25MB threshold.

### 2.3 Enrollment & Progress Tracking
- **`Enrollment`**:
  - Composite Unique Constraint: `('student', 'course')` strictly prevents duplicate enrollments.
  - `progress_percentage`: Decimal(5,2) automatically calculated by `ProgressCalculationService`.
  - `status`: Automatically switches between `ACTIVE` and `COMPLETED` based on percentage.
- **`LessonProgress`**:
  - Composite Unique Constraint: `('student', 'lesson')`.
  - Captures `started_at`, `completed_at`, and boolean `completed`.

