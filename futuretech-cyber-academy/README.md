# Future Tech Academy

> **Institutional Technology, Software Engineering & Cybersecurity Platform**  
> Engineered for IT colleges, universities, technical institutes, and vocational academies.

---

## 🛡️ Executive Summary

**Future Tech Academy** is an institutional-grade learning management platform purpose-built to deliver rigorous, structured technical and cybersecurity education. It combines an accessible, modern frontend with a modular Django backend architecture designed to support schools and IT colleges across multiple computer science and security tracks.

The system is architected in two phases:
- **Phase 1 (Complete)**: Full E-Learning platform foundation, email-based authentication, 6-tier RBAC, 14 academic diploma modules with 42+ comprehensive lessons, 6-step instructor authoring wizard, reactive HTMX progress tracking, and REST APIs.
- **Phase 2 (Roadmap Ready)**: Clean architectural service layers and UI placeholders for isolated Docker lab containers, browser web terminals (xterm.js), dynamic CTF scoring, and verifiable digital certificates.

> **IMPORTANT SECURITY POLICY**:
> All cybersecurity exercises, labs, and practical lessons are strictly designed to execute exclusively within authorized, isolated environments. The platform is never designed or permitted to attack arbitrary public Internet targets.

---

## 🚀 Key Features

- **Email-Based Authentication & Custom User**: Login via email address with UUIDv4 primary keys and role profile signals.
- **Strict Role-Based Access Control (RBAC)**:
  - `SUPER_ADMIN` (Dean / Executive)
  - `ACADEMY_ADMIN` (Academic Operations)
  - `INSTRUCTOR` (Faculty / Course Author)
  - `LAB_INSTRUCTOR` (Hands-on Range Facilitator)
  - `TEACHING_ASSISTANT` (Tutor / Grader)
  - `STUDENT` (Enrolled Learner)
- **14-Module Academic Diploma Curriculum**: 42+ original lessons covering networking, Linux hardening, defensive architecture, SOC operations, web pentesting, cryptography, digital forensics, cloud security, and DevSecOps.
- **6-Step Instructor Course Creation Wizard**:
  - Step 1: Course Metadata & Pricing
  - Step 2: Curriculum Modules Structuring
  - Step 3: Markdown Lesson Authoring
  - Step 4: Resource & Lab Sheet Uploads (25MB limit, strict executable blocking)
  - Step 5: Syllabus Audit & Review
  - Step 6: One-Click Publishing Toggle (`DRAFT` vs `PUBLISHED`)
- **Reactive Student Learning Experience**:
  - Instant lesson completion toggling via HTMX (no page reload)
  - Real-time progress percentage formula: `(completed_lessons / total_lessons) * 100`
  - Automatic transition of enrollment status from `ACTIVE` to `COMPLETED` at 100%
  - Collapsible curriculum sidebar with dark/light mode toggle (Alpine.js)
- **REST APIs**: Endpoints for course catalogs, curriculum details, student enrollments, and institutional metrics.
- **Automated Test Suite**: 21 unit and integration tests passing with 100% success.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | Python 3.12+, Django 4.2+ |
| **API Framework** | Django REST Framework (DRF) & Adaptive JSON Views |
| **Database** | PostgreSQL 15+ (Production/Docker) with SQLite fallback (Dev/Test) |
| **Cache & Queue** | Redis 7 & Celery |
| **WebSocket Architecture** | Django Channels 4 & ASGI protocol router |
| **Frontend UI** | Django Templates, Tailwind CSS (Dark/Light mode), Alpine.js, HTMX |
| **Containerization** | Docker & Docker Compose |

---

## 📁 Project Structure

```text
futuretech-cyber-academy/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── asgi.py
│   │   ├── celery.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── core/           # RBAC mixins, file validators, base models, REST APIs
│   │   ├── accounts/       # Custom User (email login), role profiles, auth views
│   │   ├── courses/        # Courses, Modules, Lessons, Resources, Seed command
│   │   ├── enrollments/    # Student admissions, unique enrollment constraints
│   │   ├── progress/       # Granular tracking, ProgressCalculationService
│   │   ├── dashboard/      # Student, Instructor Wizard, Academy Admin panels
│   │   └── notifications/  # Broadcast announcements and student notifications
│   └── manage.py
├── frontend/
│   ├── static/             # CSS & JS assets
│   └── templates/          # Accessible Tailwind + Alpine.js + HTMX templates
│       ├── accounts/       # Login, Register, Profile settings
│       ├── components/     # Reusable components (_completion_button.html)
│       ├── courses/        # Course catalog, Course detail, Lesson learn reader
│       ├── dashboard/      # Student, Admin, and Instructor 5-Step Wizard
│       ├── base.html       # WCAG accessible base layout with dark/light mode
│       ├── home.html       # Landing page with stats banner
│       └── placeholder.html# Phase 2 roadmap view for Labs, CTF, and Exams
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── docs/
│   ├── architecture.md     # High-level architecture & sequence flows
│   ├── database.md         # ERD, schemas, and indexing strategies
│   ├── development.md      # Setup guide and coding conventions
│   ├── deployment.md       # Docker and production Nginx configuration
│   ├── security.md         # Threat model, file validators, RBAC rules
│   └── api.md              # REST API endpoint specifications
├── tests/
│   └── test_academy.py     # 21 unit and integration test cases
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚡ Quickstart Guide

### Option A: Local Development (Fastest)

```bash
# 1. Navigate to project root
cd futuretech-cyber-academy

# 2. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Apply database migrations
python3 backend/manage.py migrate

# 4. Seed 14-Module Diploma Curriculum & Demo Users
python3 backend/manage.py seed_demo_data

# 5. Run automated test suite
python3 backend/manage.py test tests

# 6. Start development server
python3 backend/manage.py runserver 0.0.0.0:8000
```
Visit: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

### Option B: Docker Compose

```bash
# 1. Configure environment
cp .env.example .env

# 2. Build and launch services
docker compose up -d --build

# 3. Run database migrations inside container
docker compose exec web python manage.py migrate

# 4. Seed demo data
docker compose exec web python manage.py seed_demo_data
```

---

## 🔑 Pre-Configured Demo Accounts

All demo accounts are pre-seeded with the password: **`CyberSec2026!`**

| Role | Email Identifier | Dashboard Access |
| :--- | :--- | :--- |
| **Super Admin / Dean** | `admin@futuretech.edu` | Academy Console (`/admin-dashboard/`), Instructor Panel, Django Admin (`/admin/`) |
| **Lead Instructor** | `instructor.morpheus@futuretech.edu` | Instructor Console (`/instructor/`), Course Creation Wizard |
| **Lab Instructor** | `instructor.trinity@futuretech.edu` | Instructor Console (`/instructor/`) |
| **Student 1** | `student.neo@futuretech.edu` | Student Dashboard (`/dashboard/`), Course Learning |
| **Student 2** | `student.switch@futuretech.edu` | Student Dashboard (`/dashboard/`), Course Learning |

---

## 📚 Academic Programs & Seeded Courses

### 1. Flagship Program: Diploma in Cyber Security (6-Month Professional Program)
- **Status**: Published | **Level**: Beginner to Advanced | **Modules**: 14 | **Lessons**: 42
- Covers Foundations, Networking, Linux, Windows AD, Firewalls, SOC Analysis, SIEM, Pentesting, OWASP Web Security, Cryptography, Digital Forensics, Cloud Security, DevSecOps, and Capstone.

### 2. School of Software Engineering: Python Programming (Zero to Mastery & Automation)
- **Status**: Published | **Level**: Beginner | **Modules**: 4 | **Lessons**: 12
- Covers Python Core Syntax, Sequences & Dictionaries, OOP & Exception Handling, File I/O, REST APIs, and Socket Programming.

### 3. School of Systems: Linux System Administration & Shell Scripting
- **Status**: Published | **Level**: Beginner | **Modules**: 3 | **Lessons**: 9
- Covers Filesystem Hierarchy (FHS), Permissions, Storage (LVM), Processes, systemd, and Bash Shell Scripting.

### 4. School of Infrastructure: Computer Networking & TCP/IP Architecture
- **Status**: Published | **Level**: Beginner | **Modules**: 3 | **Lessons**: 9
- Covers OSI 7-Layer Model, IPv4/IPv6 Binary Subnetting (CIDR), Wireshark Packet Analysis, TCP/UDP, DNS, and TLS.

---

## 🧪 Automated Testing Verification

Run the test suite at any time:
```bash
python3 backend/manage.py test tests
```
Results:
```text
Found 21 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.....................
----------------------------------------------------------------------
Ran 21 tests in 5.968s

OK
Destroying test database for alias 'default'...
```

---

## 🗺️ Phase 2 Roadmap: Hands-On Cyber Range Integration

The architecture contains dedicated extension points for Phase 2:
- [ ] **Isolated Docker Labs**: Dynamic container spawning with xterm.js browser terminals over WebSockets (`channels`).
- [ ] **CTF Arena**: Jeopardy & Attack-Defense challenges with automated flag validation and real-time scoreboard.
- [ ] **Practical Exams**: Timed hands-on performance assessments in sandboxed networks.
- [ ] **Digital Certificates**: QR-verifiable cryptographic certificate generation upon 100% diploma completion.

---

## 📄 License & Academic Attribution
Future Tech Cyber Security Academy &copy; 2026. Engineered for institutional cybersecurity excellence.

