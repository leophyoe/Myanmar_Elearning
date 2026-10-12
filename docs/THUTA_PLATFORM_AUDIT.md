# THUTA Platform Audit Report

**Date of Audit**: October 11, 2026  
**Repository**: `https://github.com/leophyoe/Myanmar_Elearning.git`  
**Django Version**: 5.1.x | **Python**: 3.12.x  
**Platform Focus**: Myanmar E-Learning Management System, Cyber Range, Exam Center, Live Teaching & Video Hosting  

---

## 1. Executive Summary

This document presents a rigorous, evidence-based audit of the **THUTA (Myanmar E-Learning)** platform codebase. The audit evaluates architecture, authentication, role-based access control, billing and URL routing, assessment and examination pipelines, partner capabilities, video hosting, live teaching integration, Docker orchestration, and production security readiness.

All findings are based on direct source code inspection, configuration file verification, and active runtime test execution.

---

## 2. Platform Audit Findings by Subsystem

### 2.1 Routing & URL Resolution (Duplicate Billing Inclusion)
- **Feature & Role**: Billing, Payments, Subscriptions, Promotions (Student, Teacher, Admin, Partner).
- **Exact Location**: `config/urls.py` lines 40–41.
  ```python
  path('billing/', include(('apps.billing.urls', 'billing'), namespace='billing')),
  path('billing/', include('apps.billing.urls')),
  ```
- **Evidence**: `apps.billing.urls` is included twice at the same URL prefix. The first include establishes the `billing` namespace, while the second registers patterns in the global namespace.
- **Problem**: Duplicate route declarations increase URL resolver lookup overhead and create pattern ambiguity. Legacy templates and tests reference both namespaced (`billing:payment-list`) and unnamespaced (`payment-list`) route names.
- **Severity**: **Medium** (Confirmed).
- **Proposed Fix**: Unify billing routing under `apps.billing.urls` with namespace `billing`, while providing explicit non-namespaced backward-compatibility aliases for legacy routes (`pricing`, `payment-list`, `payment-review`, `payment-history`, `my-subscription`) without duplicating the whole URL include block.

---

### 2.2 Docker Compose & Deployment Security (Port Exposure & Insecure Defaults)
- **Feature & Role**: System Deployment, Database, Caching, Broker, and Edge Proxy.
- **Exact Location**: `docker-compose.yml` (lines 19–37, 41–55, 59–70).
  ```yaml
  web:
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.development
      - DEBUG=True
    ports:
      - "8000:8000"
  db:
    ports:
      - "5432:5432"
  redis:
    ports:
      - "6379:6379"
  ```
- **Evidence**:
  1. PostgreSQL port 5432 and Redis port 6379 are bound directly to the host interface (`5432:5432`, `6379:6379`). When deployed to a public VPS, the database and in-memory broker are directly exposed to the internet.
  2. The `web` container defaults to `DEBUG=True` with development settings.
  3. Default passwords (`cyberrange_secure_password_2026!`, `cyberrange_redis_secret`) are hardcoded in the compose file as fallbacks.
- **Severity**: **High / Critical for Production** (Confirmed).
- **Proposed Fix**:
  1. Remove host port publication for internal database and Redis services (`db` and `redis`). They communicate exclusively over the internal bridge network (`ftcr_internal_net`).
  2. Unpublish `8000:8000` from the host; route traffic through `nginx` (ports 80/443 only).
  3. Default `DJANGO_SETTINGS_MODULE` to `config.settings.production` and `DEBUG` to `False` via environment variable expansion.
  4. Require production credentials to be supplied via `.env` without insecure fallbacks.

---

### 2.3 Environment Variable Configuration (`.env.example`)
- **Feature & Role**: Environment Security & Setup Configuration.
- **Exact Location**: `.env.example`.
- **Evidence**: Contains insecure development secret keys (`ftcr-insecure-dev-secret-key-...`), `DEBUG=True`, `localhost:8000` hardcoded certificate URL, and missing production variables such as `CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT`, Cloudflare R2 / S3 storage keys, and Video Streaming API tokens.
- **Severity**: **Medium** (Confirmed).
- **Proposed Fix**: Replace all hardcoded development keys with documented placeholders, provide clear production guidance, and include all necessary production variables with fail-safe instructions.

---

### 2.4 Exam Center & Assessment Architecture
- **Feature & Role**: Examination, Assessment, Certification (Student, Instructor, Partner, Admin).
- **Exact Location**:
  - `apps/courses/models.py` (`Quiz`, `Question`, `QuizAttempt`, `Assessment`)
  - `apps/courses/views.py` (`AssessmentDetailView`, `AssessmentSubmitView`)
  - `apps/certificates/models.py` (`Certificate`)
- **Evidence**:
  1. **Course Tight-Coupling**: `AssessmentDetailView` explicitly requires `slug` (course slug) and mandates course enrollment via `can_access_course`. A student cannot take an independent or standalone exam without enrolling in the complete course.
  2. **Standalone Exam Monetization**: No support for standalone paid or free exams. Students wishing to be certified in a specific skill without watching course lectures have no distinct purchase or exam access path.
  3. **Certificate Type Ambiguity**: `Certificate` model defaults to course completion and does not distinguish between **Course Completion Certificate** and **Exam-based Verified Certificate**.
  4. **Manual Grading Rubrics**: Open-ended questions, short answers, coding problems, and project essays lack an instructor rubric grading interface where scores and feedback can be recorded per criteria (as shown in reference screenshot `ExamSoft` rubric table).
- **Severity**: **High** (Confirmed).
- **Proposed Fix**:
  1. Add standalone exam capabilities to `Quiz` (`is_standalone=True`, `price`, `owner`, `partner`, `requires_manual_grading`).
  2. Implement dedicated standalone exam URLs and views (`/courses/exams/<uuid:exam_id>/`) decoupled from course enrollment, supporting standalone entitlement checking (free exam or purchased exam via Billing).
  3. Extend `Certificate` with `certificate_type` (`COURSE_COMPLETION`, `EXAM_VERIFIED`, `PARTICIPATION`), `exam`, `exam_score`, `verified_by`.
  4. Build an interactive Exam Center UI matching the reference design (exam timer, section navigation tiles, quiz controls) and an Instructor Grading Rubric interface.

---

### 2.5 Live Teaching & Virtual Classroom Integration
- **Feature & Role**: Live Classroom, Lecture Broadcasting, Attendance Tracking (Teacher, Student).
- **Exact Location**:
  - `apps/courses/live/bigbluebutton.py`
  - `apps/courses/live/zoom.py`, `google_meet.py`, `teams.py`
  - `apps/courses/views.py` (`LiveSessionJoinView`, `LiveSessionSyncAttendanceView`)
- **Evidence**:
  1. The platform integrates **BigBlueButton (BBB)** as its primary open-source virtual classroom platform, alongside Zoom, Google Meet, and Teams.
  2. In offline or local test environments without internet DNS access, `BigBlueButtonClient.test_connection()` throws socket name resolution errors (`<urlopen error [Errno -3] Temporary failure in name resolution>`).
  3. Live session join URLs require resilient fallback: if BigBlueButton server is unreachable or offline, sessions must offer seamless fallback to instructor-provided meeting links (Zoom / Google Meet) with user-friendly notices instead of crashing.
- **Severity**: **High** (Confirmed).
- **Proposed Fix**:
  1. Implement simulation/mock mode for BigBlueButton client during offline test execution.
  2. Provide teacher UI controls for managing live session status, attendance synchronization, lecture recording attachment, and Google Meet/Zoom fallbacks.
  3. Produce comprehensive comparative evaluation of open-source meeting platforms in `docs/THUTA_LIVE_TEACHING_AND_VIDEO_HOSTING.md`.

---

### 2.6 Video Hosting & Course Media Management
- **Feature & Role**: Course Lessons, Lecture Video Playback, Downloadable Handouts.
- **Exact Location**:
  - `apps/courses/models.py` (`Lesson.video_file`, `Lesson.video_url`, `Lesson.document_file`)
  - `templates/courses/lesson_detail.html`
- **Evidence**:
  1. Course videos are currently stored in the Django container's local file storage (`/app/media/lessons/video/`), which is unsuitable for production streaming, bandwidth scalability, or multi-server deployments.
  2. External video links currently render a simple link button ("Launch Video Stream") rather than an embedded responsive video player with theater controls (as shown in reference screenshots `EDEARN` and laptop player).
- **Severity**: **High for Production Scale** (Confirmed).
- **Proposed Fix**:
  1. Architectural separation:
     - **Recorded Course Videos**: Managed video hosting (Bunny Stream / Cloudflare Stream) with HLS adaptive bitrate streaming and token authentication.
     - **PDF Handouts, Slides, Source Code**: S3-compatible object storage (Cloudflare R2 / AWS S3).
     - **Live Teaching**: Dedicated conferencing platform (BigBlueButton / Google Meet fallback).
  2. Update `lesson_detail.html` to embed modern video player supporting embedded streams, HLS, YouTube/Vimeo embeds, and custom hosted streams with speed controls and responsive lesson navigation.

---

### 2.7 Partner Course and Exam Center
- **Feature & Role**: Institutional Partners, Corporate Universities, Training Centers.
- **Exact Location**: `apps/partner/models.py`, `apps/partner/views.py`.
- **Evidence**:
  - The partner portal handles institutional applications and revenue dashboards, but lacks dedicated tools for partners to create institution-scoped exams, assign certified instructors, and view institutional cohort exam performance.
- **Severity**: **Medium** (Confirmed).
- **Proposed Fix**:
  - Extend the Partner portal with an Institution Exam Center tab allowing partner administrators to create and manage standalone and course-based exams, assign approved instructors, and view student cohort score reports.

---

## 3. Prioritized Action Matrix

| Priority | Issue / Task | Affected Components | Status |
|---|---|---|---|
| **P0 (Critical)** | Unpublish PostgreSQL (5432) & Redis (6379) from host in `docker-compose.yml`; fix production environment defaults | `docker-compose.yml`, `.env.example` | In Progress |
| **P0 (Critical)** | Fix duplicate `billing` URL inclusion in `config/urls.py` with backward-compatible aliases | `config/urls.py`, `apps/billing/urls.py` | In Progress |
| **P1 (High)** | Build Standalone Exam Center with independent eligibility, pricing, and purchase flows | `apps/courses/`, `apps/billing/`, `templates/courses/` | In Progress |
| **P1 (High)** | Separate Certificate types (Course Completion vs Exam-based Verified Certificate) | `apps/certificates/`, `apps/courses/` | In Progress |
| **P1 (High)** | Interactive Exam Taking UI (Timer, Question Palette, Section Controls) & Rubric Grading | `templates/courses/`, `apps/courses/views.py` | In Progress |
| **P1 (High)** | Resilient Live Teaching (BigBlueButton simulation/offline fallback, Meet/Zoom fallbacks) | `apps/courses/live/`, `apps/courses/views.py` | In Progress |
| **P2 (Medium)** | Video Hosting & Media Architecture Specification (Bunny Stream, Cloudflare R2) & Embedded Player | `apps/courses/`, `templates/courses/lesson_detail.html` | In Progress |
| **P2 (Medium)** | Partner Exam & Course Center (Institution-scoped exams, cohort analytics) | `apps/partner/`, `templates/partner/` | In Progress |

