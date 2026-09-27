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

