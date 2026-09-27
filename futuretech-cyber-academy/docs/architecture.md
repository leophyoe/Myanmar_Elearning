# Future Tech Cyber Security Academy — Architecture Overview

## 1. Executive Summary
**Future Tech Cyber Security Academy** is an enterprise-grade, institutional cybersecurity e-learning platform engineered for colleges, universities, and IT institutes. It serves as the educational foundation for a **6-Month Diploma in Cyber Security**.

The platform is designed with a **two-phase architecture**:
- **Phase 1 (Current)**: Core E-Learning Platform foundation, RBAC authentication (email-based), course authoring workflow, enrollment tracking, progress calculation, downloadable lab guides, and REST APIs.
- **Phase 2 (Roadmap)**: Isolated Docker-based Cyber Range lab containers, browser web-terminal (xterm.js/WebSockets), CTF dynamic scoreboard, and cryptographic digital certificates.

---

## 2. High-Level Architecture

```mermaid
graph TD
    Client["Browser Client (HTMX + Alpine.js + Tailwind CSS)"]
    
    subgraph Application_Tier ["Application Tier (Django 4.2+ / Python 3.12)"]
        ASGI["ASGI Server (Uvicorn / Daphne)"]
        WSGI["WSGI Server (Gunicorn)"]
        Core["apps.core (RBAC, Security Validators, APIs)"]
        Accounts["apps.accounts (Custom User, Email Login, Profiles)"]
        Courses["apps.courses (14 Modules, 42+ Lessons, Syllabus)"]
        Enrollments["apps.enrollments (Student Admissions, Unique Constraints)"]
        Progress["apps.progress (Granular Lesson & Course % Calculation)"]
        Dashboard["apps.dashboard (Student, Instructor Wizard, Dean Console)"]
    end

    subgraph Data_Tier ["Data & Cache Tier"]
        DB[(PostgreSQL Database)]
        Cache[(Redis Cache & Message Broker)]
    end

    subgraph Phase_2_Readiness ["Phase 2 Engine Interfaces"]
        DockerWorker["Docker Daemon Worker (Sandboxed Labs)"]
        CTFEngine["CTF Dynamic Scoring Engine"]
    end

    Client -->|HTTP / HTMX| WSGI
    Client -->|WebSockets (Phase 2)| ASGI
    WSGI --> Application_Tier
    ASGI --> Application_Tier
    Application_Tier --> DB
    Application_Tier --> Cache
    Application_Tier -.->|Prepared Interfaces| Phase_2_Readiness
```

---

## 3. Modular App Structure

| App Name | Responsibilities | Key Models & Services |
| :--- | :--- | :--- |
| `apps.core` | Base abstractions, UUID primary keys, timestamping, file upload validation, RBAC permissions, adaptive API routing. | `BaseModel`, `validate_resource_file`, `RoleRequiredMixin`, `PlatformStatsAPIView` |
| `apps.accounts` | Custom authentication using **email as username**, UUID PKs, signals for auto-provisioning role profiles. | `User`, `RoleChoices`, `StudentProfile`, `InstructorProfile`, `AdminProfile` |
| `apps.courses` | 14 Diploma modules, lessons with rich Markdown content, resource attachments, draft/published workflow. | `CourseCategory`, `Course`, `CourseModule`, `Lesson`, `CourseResource` |
| `apps.enrollments` | Student course enrollments, duplicate prevention, admission lifecycle. | `Enrollment`, `EnrollmentStatus` |
| `apps.progress` | Granular per-lesson tracking, automated formula: `(completed / total) * 100`, auto-completion trigger. | `LessonProgress`, `ProgressCalculationService` |
| `apps.dashboard` | Multi-tenant portals: Student learning hub, 6-Step Instructor course creation wizard, Academy Admin console. | `StudentDashboardView`, `InstructorDashboardView`, `CourseCreateStep1-5` |
| `apps.notifications`| System announcements, student alerts, course completion notices. | `Notification` |

---

## 4. Frontend Philosophy (HTMX + Alpine.js + Tailwind CSS)
Instead of a heavyweight single-page application (SPA) requiring separate build tooling and high maintenance, Future Tech utilizes a **modern reactive server-rendered stack**:
1. **Tailwind CSS (Dark/Light Modes)**: High-contrast, WCAG 2.1 AA accessible UI with cybersecurity aesthetics (slate-950, cyan, emerald, amber).
2. **Alpine.js**: Client-side state handling (e.g., curriculum accordions, mobile sidebars, theme toggle in `localStorage`).
3. **HTMX**: In-place reactive partial updates (e.g., instant lesson completion toggle without reloading the reader view).

---

## 5. Async & Real-Time Preparedness
- **Celery & Redis**: Configured in `config/celery.py` and `docker-compose.yml` for background processing (certificate generation, bulk email dispatch, container timeouts).
- **Django Channels & ASGI**: `config/asgi.py` contains the protocol router for handling WebSockets in Phase 2 for interactive browser terminal streaming.

