# Myanmar E-Learning

An institutional e-learning platform for Myanmar: online courses with video/PDF lessons, quizzes with instant grading, assignments, progress tracking and verifiable certificates — plus an integrated, Docker-orchestrated **cyber security range** (isolated labs, CTF challenges and an in-browser terminal) engineered for the **10-Month Diploma in Cyber Security**.

Built for schools, colleges, technical institutes, universities and commercial training academies.

---

## Platform Structure

- **`apps/users`** — accounts and role-based access (`ADMIN` / `TEACHER` / `STUDENT`)
- **`apps/courses`** — subjects, modules, lessons, quizzes, assignments, progress
- **`apps/certificates`** — verifiable PDF credentials + public `/verify/` gateway
- **`apps/labs` + `apps/ctf` + `apps/terminal`** — cyber range (Docker sandboxes, CTF, WebSocket terminal)
- **`apps/scoring`** — badges, points and leaderboard
- **`apps/analytics`** — admin / instructor reporting

> Phase 0 (this snapshot): platform rebrand, Git version control, and the `Subject` category model.
> Cyber lab engine is intentionally left untouched.

---

## Key Capabilities

1. **Academic Curriculum & LMS**: 14 structured modules covering foundational theory, systems hardening, penetration testing, SOC/SIEM triage, digital forensics, and capstone defense.
2. **TryHackMe / HTB-Style Cyber Labs**: On-demand isolated Docker container sandboxes provisioned per student with single-click start, stop, and reset controls.
3. **Strict Egress & Host Isolation**: Every student sandbox runs inside a dedicated internal Docker bridge (`internal: true`) with **zero WAN routing**, dropped kernel capabilities (`cap_drop=['ALL']`), `no-new-privileges: true`, and strict cgroup CPU/memory/PID limits.
4. **Capture The Flag (CTF) Engine**: Jeopardy-style challenges across 10 categories featuring constant-time hash verification (`hmac.compare_digest`), anti-bruteforce rate limiting, and dynamic per-student flag injection.
5. **In-Browser Web Terminal**: Low-latency `xterm.js` terminal communicating via WebSockets and Django Channels directly to container pseudo-terminals (PTY).
6. **SOC & SIEM Telemetry**: Realistic log triage scenarios using Wazuh SIEM rules, MITRE ATT&CK correlation, and Indicators of Compromise (IOC) investigation.
7. **Digital Certificate Authority**: Verifiable credentials featuring unique serials and a public verification gateway (`/verify/<id>/`) preserving student privacy.
8. **Institutional Role-Based Access Control (RBAC)**: Distinct permissions and custom cockpits for Students, Instructors, Lab Administrators, and Super Administrators.

---

## Technology Stack

- **Backend**: Python 3.12, Django 5.x / 4.2+, Django REST Framework
- **Real-Time WebSockets**: Django Channels, Daphne ASGI Server, Redis Channel Layer
- **Async Tasks & Scheduling**: Celery Worker, Celery Beat (60-second lab expiration reaper)
- **Persistence & Cache**: PostgreSQL 16 Alpine, Redis 7 Alpine
- **Container Orchestration**: Docker Engine, Docker Compose, Docker SDK for Python
- **Frontend**: Semantic HTML5, Tailwind CSS, JetBrains Mono, xterm.js
- **Reverse Proxy**: Nginx with SSL termination and WebSocket pass-through

---

## 10-Month Curriculum (14 Modules)

| Code | Module Title | Topics & Focus | Hands-on Labs & CTFs |
| :--- | :--- | :--- | :--- |
| **MOD-01** | Introduction to Cyber Security | CIA Triad, Threat Modeling, Attack Surfaces, Phishing, Legal Ethics | 3 Labs (Fundamentals, Phishing, Passwords) |
| **MOD-02** | Computer Systems & OS Security | Linux & Windows Internals, DAC/ACLs, Processes, Hardening Baselines | 3 Labs (Linux Perms, Windows Sec, Hardening) |
| **MOD-03** | Networking Fundamentals | OSI & TCP/IP, IPv4/v6 Subnetting, DNS, DHCP, ARP, Routing, NAT | 4 Labs (Net Basics, Subnetting, DNS, Packets) |
| **MOD-04** | Linux for Cyber Security | Headless CLI, SUID Escalation, SSH Hardening, Syslog/Auditd Triage | 4 Labs (Linux CLI, Perm CTF, SSH, Logs) |
| **MOD-05** | Windows & Active Directory | PowerShell Sec, Defender Firewall, AD DS, GPO, Kerberos, Event Logs | 4 Labs (Windows Sec, AD, GPO, Event Logs) |
| **MOD-06** | Ethical Hacking Fundamentals | Rules of Engagement, Recon, Nmap Scanning, Service Enumeration | 4 Labs (Recon, Nmap, Enumeration, Hacking CTF) |
| **MOD-07** | Web Application Security | HTTP/S, OWASP Top 10 (SQLi, XSS, BOLA, File Upload, Web Shells) | 7 Labs (HTTP, Auth, SQLi, XSS, Access, Upload, CTF) |
| **MOD-08** | Network Security | Firewalls (iptables/nftables), Suricata IDS/IPS, Wireshark, tcpdump | 4 Labs (Wireshark, Firewall, IDS, Net Mon) |
| **MOD-09** | Vulnerability Assessment & VAPT | Vulnerability Lifecycles, CVSS v3.1 Scoring, Nmap NSE, Audit Reports | 4 Labs (Net Vuln, Web Vuln, Vuln Mgmt, VAPT CTF) |
| **MOD-10** | SOC, SIEM & Incident Response | SOC Tiers, Wazuh SIEM Ingestion, Alert Triage, MITRE ATT&CK, IOCs | 5 Labs (SOC Mon, SIEM, Log Analysis, IOC, IR) |
| **MOD-11** | Digital Forensics & Malware | Chain of Custody, File Carving, Volatility Memory Triage, PE Analysis | 5 Labs (Windows, Browser, Linux, Disk, Memory) |
| **MOD-12** | Python for Cyber Security | Sockets, Scapy Packets, Requests, RegEx Log Triage, CLI Daemons | 5 Projects (Password, Log Analyzer, FIM, Scanner, IOC) |
| **MOD-13** | Cloud Security & DevSecOps | Cloud IAM Least Privilege, Container Benchmarking, CI/CD SAST/DAST | 4 Labs (IAM, Cloud, Docker Sec, API Sec) |
| **MOD-14** | Integrated Cyber Range Capstone | Enterprise Attack/Defend Simulation, Audit Report, Viva Defense | Capstone Proposal -> Viva Voce Examination |

---

## Quickstart & Docker Deployment

### 1. Clone & Configure Environment
```bash
cp .env.example .env
```

### 2. Build and Launch with Docker Compose
```bash
# Start Web, PostgreSQL, Redis, Celery Worker, Celery Beat, and Nginx
docker compose up --build -d
```

### 3. Run Migrations & Seed Curriculum
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_curriculum
```

### 4. Create Super Administrator Account
```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Access the Platform
- **Public Portal**: [http://localhost](http://localhost) (or port 8000 if accessing Daphne directly)
- **Student Dashboard**: `/auth/dashboard/`
- **Teacher Dashboard**: `/analytics/instructor/`
- **Administrator Dashboard**: `/analytics/system/`
- **Health Check API**: `/api/health/`

---

## Accounts & Roles

Three institutional roles are supported. Every account automatically receives a matching
profile (`StudentProfile` / `TeacherProfile` / `AdminProfile`) via a `post_save` signal.

| Role | Value | Can do | Dashboard |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | Everything: user management, publishing, payments, system telemetry | `/analytics/system/` |
| **Teacher** | `teacher` | Author courses/lessons, set quizzes & assignments, grade, view class progress | `/analytics/instructor/` |
| **Student** | `student` | Self-register, enrol, learn, submit, track progress, earn certificates | `/auth/dashboard/` |

**Provisioning**

```bash
# Administrator (also creates a Django superuser)
python manage.py createsuperuser
# then set role = admin in the Django admin (/admin/)

# Teacher
python manage.py shell -c "
from apps.users.models import User, UserRole
User.objects.create_user('u_kyaw', 'kyaw@mel.edu.mm', 'ChangeMe2026!', role=UserRole.TEACHER)
"

# Students self-register at /auth/register/ (always role = student)
```

Legacy role values (`super_admin`, `lab_admin`, `instructor`) are remapped automatically
by migration `users.0003`.

---

## Course Authoring & Enrolment (Phase 2)

Teachers (and administrators) get a **Content Studio** at `/courses/manage/` for the full
`Subject → Course → Module → Lesson` hierarchy. Students must **enrol** before a course's
lessons unlock.

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/courses/manage/` | teacher, admin | Authoring cockpit — subjects, courses, modules, lessons |
| `/courses/manage/subjects/new/` | teacher, admin | Create a subject (`general` or `cyber`) |
| `/courses/manage/courses/new/` | teacher, admin | Create / publish a course |
| `/courses/manage/modules/new/` | teacher, admin | Add a module (code, objectives) |
| `/courses/manage/lessons/new/` | teacher, admin | Author a lesson incl. **video & PDF upload** |
| `/courses/my/` | student | Enrolled courses with live progress % |
| `/courses/<slug>/enroll/` | student (POST) | Enrolment — required before lessons open |

**Lesson types** — `text`, `video`, `pdf`, `quiz`, `assignment`, `lab`, `ctf`.
The lesson page renders the matching block: HTML5 `<video>` for uploads, an external link
for `video_url`, a download card for `document_file`, and the existing quiz/CTF widgets.

**Upload limits** — video 200 MB (`mp4/webm/ogg/mov`), documents 25 MB
(`pdf/doc/docx/ppt/pptx/txt/md/zip`). Files land under `media/lessons/{video,docs}/`.

---

## Quizzes, Assignments & Grading (Phase 3)

Assessment is authored by teachers, taken by enrolled students and marked in a
single grading queue.

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/courses/manage/lessons/<id>/quiz/` | teacher, admin | Quiz builder: settings + multiple choice questions |
| `/courses/manage/assignments/new/` | teacher, admin | Publish an assignment for a module |
| `/courses/manage/assignments/<id>/edit/` | teacher, admin | Edit or delete an assignment |
| `/courses/manage/submissions/` | teacher, admin | Grading queue (ungraded / graded filters) |
| `/courses/manage/submissions/<id>/grade/` | teacher, admin | Award a score out of `max_score` + feedback |
| `/courses/assignments/<id>/` | enrolled student | Assignment brief, hand-in form and feedback |

* **Quiz builder** — each question carries four answer slots and a "correct answer"
  radio; saving writes the `Choice` rows in one pass. Empty prompts are ignored,
  a quiz must keep at least one question, and every kept question needs a correct
  answer. Students still submit through `quiz-submit`, which auto-grades, awards
  points and completes the lesson.
* **Hand-ins** — text and/or a file (25 MB). Re-submitting replaces the previous
  attempt (`AssignmentSubmission` is unique per assignment + student).
* **Grading** — the score is capped by `max_score`. At 60 % or better the module's
  `assignment` lesson is marked complete and the student's enrolment progress is
  recomputed.
* Access rules are enforced end to end: students need an active enrolment, staff
  never submit work, and the whole Content Studio / queue is `403` for students.

---

## Progress, Certificates & Reports (Phase 4)

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `POST /courses/lessons/<id>/complete/` | enrolled student | Toggle "lesson complete" and resync enrolment progress |
| `/certificates/` | student | Credentials earned so far |
| `/certificates/verify/<uuid>/` | public | Standalone verification page (no PII) |
| `/analytics/reports/courses/` | teacher, admin | Enrolment / progress / grading / credentials per course |
| `/analytics/reports/students/` | teacher, admin | Progress, grades, pending work and credentials per student |

**Completion rules**

* Reading lessons complete via the **Mark complete** button (undo is allowed).
* Lessons with a real checkpoint quiz are only completed by **passing** it.
* Lessons of type `assignment` are only completed once a submission scores
  **≥ 60 %** and the teacher grades it.
* Every completion calls `sync_enrollment_progress`, which stores
  `Enrollment.progress_pct` and flips the enrolment to `completed` at 100 %.

**Certificates** — issued automatically the first time an enrolment reaches
100 % (`apps/certificates/services.py`). Issuance is idempotent per
(student, course), retries on serial collisions inside a savepoint, and derives
the classification from the student's graded assignments in that course:
**Distinction ≥ 85 %**, **Merit ≥ 70 %**, otherwise **Pass**.

**Student dashboard** — metrics are now scoped to enrolled courses (lessons
completed / total lessons, live per-course progress bars) and revoked
certificates are hidden everywhere.

---

## Payments, Pricing & Revenue Share (Phase 5a)

Teachers price their own courses. The platform keeps a fixed commission of
every approved payment and pays the rest to the course owner.

| Setting (`config/settings/base.py`) | Default | Meaning |
| :--- | :--- | :--- |
| `PLATFORM_CURRENCY` | `MMK` | Currency shown everywhere |
| `PAYMENT_PLATFORM_COMMISSION_RATE` | `0.25` | Platform share of every approved payment |
| `PAYMENT_RECEIPT_MAX_MB` | `10` | Receipt upload limit |

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/courses/<slug>/checkout/` | student | Submit KBZ Pay / Wave Pay / bank transfer proof |
| `/billing/my-payments/` | student | Own payment history (pending / approved / rejected) |
| `/billing/review/?status=…` | admin | Review queue with per-status tabs |
| `/billing/review/<uuid>/` | admin | Approve (auto-enrols) or reject with a reason |
| `/analytics/reports/earnings/` | teacher, admin | Gross / 25 % platform / 75 % teacher split per course |

**Pricing model**

* `Course.price = 0` → free, enrolment works exactly as in Phase 2.
* `Course.billing_period` → `one_time` (permanent access) or `monthly`
  (approvals get a `period_end` one month later and stop unlocking lessons).
* `Course.owner` → the teacher who receives the 75 % share; set automatically
  on creation. Teachers can only edit courses they own, admins can edit all.

**Checkout flow**

1. Paid courses replace the *Enrol* button with **Buy for 5,000 MMK**.
   `EnrollView` redirects to checkout until a current payment exists.
2. `PaymentSubmitForm` requires a transaction reference, a receipt, or both.
   The platform/teacher split (`Payment.split`) is frozen at submission time.
3. Approving in the review queue sets `status=approved`, stamps
   `period_start` / `period_end` and creates the `Enrollment`.
   Rejecting requires a reason and never enrols anybody.
4. `can_access_course()` now demands **both** an active `Enrollment` **and**
   an approved, unexpired payment for paid courses, so lessons, quizzes and
   assignments stay locked until an admin approves the payment.

---

## Live Sessions (Phase 5b)

Teachers schedule real-time classes on Zoom, Google Meet, Microsoft Teams or any
custom link. The joining URL is treated as private course content.

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/courses/manage/live/` | teacher, admin | Schedule with an optional `?course=` filter |
| `/courses/manage/live/new/` | teacher, admin | Create a session (future start times only) |
| `/courses/manage/live/<uuid>/edit/` | owner, admin | Reschedule or republish |
| `/courses/manage/live/<uuid>/delete/` | owner, admin | Remove a session |

**Visibility rules**

* `CourseDetailView` only publishes `upcoming_live_sessions()` when the viewer
  may see the course content — staff, or a student with an active enrolment
  *and* an approved payment on paid courses. Anonymous visitors and
  non-enrolled students never receive the link.
* Unpublished (`is_published=False`) and already-started sessions are filtered
  out.
* The student dashboard lists the next five sessions across enrolled courses.
* Teachers only schedule on courses they own (`Course.owner`); admins on any.

---

## Administration Console (Phase 7)

One admin-only workspace for accounts, courses and money. Every route lives under
`/console/` and is guarded by `AdminRequiredMixin` (`allowed_roles = ['admin']`).

| Route | Purpose |
| :--- | :--- |
| `/console/` | Platform totals: users, courses, enrolments, revenue |
| `/console/users/` | User management — search, role filter, status filter, pagination |
| `/console/users/new/` | Provision a student, teacher or administrator |
| `/console/users/<uuid>/` | Account detail: enrolments, payments, certificates |
| `/console/users/<uuid>/edit/` | Identity, role and active status |
| `/console/users/<uuid>/password/` | Administrator password reset |
| `/console/users/<uuid>/toggle/` | POST-only deactivate / reactivate |
| `/console/courses/` | Course & fee list: price, owner, enrolments, gross, platform share |
| `/console/fees/` | Revenue split, status totals, pending queue, refund action |
| `/console/payments/<uuid>/refund/` | POST-only refund of an approved payment |

**Rules enforced in the console**

* A user always keeps the profile of their current role — changing
  `student` → `teacher` creates the missing `TeacherProfile` immediately.
* Administrators cannot demote themselves, deactivate themselves or rename
  their own account (`AdminUserUpdateForm.clean`).
* Deactivation blocks sign-in but never deletes the account, its enrolments,
  payments or certificates.
* Emails are unique case-insensitively on create and update.
* A role's profile (`StudentProfile` / `TeacherProfile` / `AdminProfile`) is
  created by the console as well as by the `post_save` signal on self-registration.

## Public Portfolios, QR/NFC & Credential Verification (Phase 8)

Every account owns a shareable portfolio at `/portfolio/<username>/`, plus a
public lookup for certificate IDs.

**Routes**

| Route | Access | Purpose |
| :--- | :--- | :--- |
| `/portfolio/<username>/` | public | Skills, profile links, platform & external certificates |
| `/portfolio/edit/` | owner | Add / edit / delete skills, links and external credentials |
| `/portfolio/<username>/qr.png` | public | PNG QR encoding the portfolio URL |
| `/portfolio/<username>/nfc.txt` | public | Plain-text URL payload for writing an NFC tag |
| `/portfolio/qr/`, `/portfolio/nfc/` | owner | The same for your own profile |
| `/certificates/verify/` | public | Look up a certificate by serial or UUID |
| `/certificates/verify/<uuid>/qr.png` | public | QR encoding the verification page |
| `/console/credentials/` | admin | Review queue for student-submitted credentials |

**Models (`apps.portfolio`)**

* `Skill` — name, category, level 1–5, display order, unique per owner.
* `PortfolioLink` — kind (GitHub / LinkedIn / Website / CV / …), label, URL.
  The `StudentProfile.github_url` / `linkedin_url` fields are merged in
  automatically so nothing has to be entered twice.
* `ExternalCertificate` — credential earned elsewhere: title, issuer, credential
  ID/URL, dates, uploaded document, note, and an admin `is_verified` stamp.

**Rules**

* An external credential is *pending* the moment it is saved or edited; an
  administrator must approve it in `/console/credentials/` before it appears
  publicly. Pending and rejected entries stay visible to their owner only.
* Rejection requires a written reason, which the owner sees on their edit page.
* Skills and links can only be edited by their owner — the editor resolves
  every `pk` through `owner=request.user`, so another account yields a 404.
* The skill level must be between 1 and 5; uploaded documents must be
  PDF/PNG/JPG and ≤ 10 MB.

**QR & NFC**

QR codes are generated server-side with `qrcode` (+ Pillow) and returned as
`image/png`. The NFC endpoint returns the absolute portfolio URL as
`text/plain`, which any tag writer can paste into a URI/URL NDEF record —
scanning the tag then opens the portfolio.

**Certificate lookup**

`/certificates/verify/?code=…` accepts either the printed serial
(`MEL-CERT-2026-…`, case-insensitive) or the certificate UUID and redirects to
the public verification page. The verification page itself now shows a QR code
for the record, a VALID/REVOKED status badge with the revocation reason, and a
link back to the lookup form.

## Local Development (Without Docker)

You can also run Myanmar E-Learning locally with SQLite:

```bash
# Run database migrations
python manage.py migrate

# Seed 14 curriculum modules, 16 sample labs, CTF challenges, and badges
python manage.py seed_curriculum

# Run automated test suite
python manage.py test apps.common

# Launch development server
python manage.py runserver 0.0.0.0:8000
```

---

## Defense-in-Depth Lab Isolation Architecture

```
[Host System]
  │
  ├── Platform Network (Bridge: ftcr_internal_net)
  │     ├── web (Daphne / Django)
  │     ├── db (PostgreSQL 16)
  │     ├── redis (Redis 7)
  │     └── celery (Worker with /var/run/docker.sock)
  │
  └── Isolated Student Sandbox (Bridge: ftcr_net_inst_<uuid>)
        ├── Network Option: "internal": true (WAN routing disabled)
        ├── Subnet: Unique ephemeral /24 block per student instance
        ├── cgroup limits: cpu_quota=50000 (0.5 vCPU), mem_limit=512m
        ├── Fork-bomb protection: pids_limit=100
        ├── Capability dropping: cap_drop=['ALL']
        ├── Security options: no-new-privileges:true
        ├── Filesystem: readonly_rootfs=true, tmpfs on /tmp (noexec, nosuid)
        └── Automated Reaper: Celery Beat auto-destroys containers >90 minutes
```

---

## License & Commercial Deployment
Designed for institutional licensing (Schools, Vocational Colleges, and Universities). Supports white-label branding, multi-tenancy, and on-premises air-gapped deployment.

