# MYANMAR E-LEARNING (MEL)
## Comprehensive System Requirements & Architectural Specification Report
**Document ID:** MEL-SRS-2026-V3  
**Status:** Approved Specification  
**Classification:** Academic & Technical Project Report Document  
**Platform Classification:** Modular Multi-Disciplinary Learning Management System (LMS) with Integrated Virtual Lab Sandbox  

---

## 1. Executive Summary

**Myanmar E-Learning (MEL)** is an inclusive, multi-disciplinary educational technology platform engineered to bridge the educational accessibility and quality gap across Myanmar. While traditional platforms frequently isolate theoretical academic education from practical technical training, Myanmar E-Learning provides a cohesive learning environment spanning elementary, secondary, vocational, higher academic, and advanced technical faculties.

The platform is explicitly designed **not as a cybersecurity-only platform**, but as a universal educational ecosystem encompassing computer programming, general sciences, secondary school credentials, language studies, engineering, and vocational trades, while housing an integrated, containerized virtual hands-on lab sandbox for technical and security curricula.

### 1.1 Core Foundational Principles
1. **Single Identity (One Account, One Sign-In)**: Eliminates identity fragmentation. A single user identity functions across student, educator, institutional, and administrative contexts.
2. **Extreme Socioeconomic Accessibility**: Features a permanent **Starter (Free)** tier and an ultra-affordable **Standard tier at 5,000 MMK/month**, ensuring barrier-free access for learners nationwide.
3. **Decoupled Examination & Certification Integrity**: Subscriptions confer continuous learning access; however, formal examinations and cryptographically verifiable certificates adhere to rigorous course-level academic policies.
4. **Merit-Driven Student Recognition**: High-level recognition ("Associate") is strictly an earned academic achievement benchmark, not a purchasable subscription tier.
5. **Empowering Educator & School Economy**: Provides an equitable dual revenue-sharing model (up to 80% for live instruction) and a sustainable 75/25 B2B partnership model for schools and universities.

---

## 2. Scope of Educational Disciplines

Myanmar E-Learning houses modular curricula divided into specialized academic faculties:

```
                            ┌─────────────────────────────────────────┐
                            │    Myanmar E-Learning Catalog Scope     │
                            └────────────────────┬────────────────────┘
                                                 │
     ┌───────────────────┬───────────────────────┼───────────────────────┬───────────────────┐
     ▼                   ▼                       ▼                       ▼                   ▼
┌──────────────┐   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐    ┌──────────────┐
│ Programming  │   │   Academic   │        │ Engineering  │        │ Cyber Range  │    │  Non-IT &    │
│ & Software   │   │  Foundations │        │  & Applied   │        │  & Systems   │    │  Vocational  │
├──────────────┤   ├──────────────┤        ├──────────────┤        ├──────────────┤    ├──────────────┤
│ • Python Pro │   │ • ICT        │        │ • Electrical │        │ • Linux Sys  │    │ • Business   │
│ • Full-Stack │   │ • IGCSE/O-Lvl│        │ • Electronics│        │ • Net Defense│    │ • Accounting │
│ • AI & ML    │   │ • GED Prep   │        │ • Mechanical │        │ • Hands-on   │    │ • Languages  │
│ • Databases  │   │ • General Sci│        │ • Robotics   │        │   Lab Sandbox│    │ • TVET Skills│
└──────────────┘   └──────────────┘        └──────────────┘        └──────────────┘    └──────────────┘
```

1. **Python & Modern Software Engineering**: Python for beginners, Object-Oriented Programming, Data Science, Web Application Engineering, and API development.
2. **Computer Science & Artificial Intelligence**: Data Structures & Algorithms, Machine Learning fundamentals, Deep Learning, and Applied Large Language Models.
3. **Information & Communication Technology (ICT)**: Digital literacy, workplace productivity, spreadsheet automation, and modern digital collaboration tools.
4. **Secondary & High School Equivalency (IGCSE / O-Level & GED)**: Cambridge/Edexcel IGCSE Mathematics, Physics, Chemistry, Biology, Business Studies, and complete 4-subject GED preparatory tracks.
5. **Applied Engineering**: Electrical circuit analysis, digital electronics, microcontrollers (Arduino/Raspberry Pi), and civil/mechanical engineering essentials.
6. **Cybersecurity & Systems Defense (Integrated Module)**: Network forensics, web security, Linux privilege escalation, defensive systems hardening, and Capture The Flag (CTF) challenges.
7. **Non-IT & Professional Studies**: Financial accounting, professional English, business administration, marketing, creative media, and TVET vocational trades.
8. **Future Modular Extensions**: Scalable architecture capable of hosting medical/healthcare modules, legal studies, and agricultural technology.

---

## 3. Unified Account & Identity Architecture

### 3.1 Single Account, Unified Sign-In
Myanmar E-Learning enforces a strict **Single User Account** policy. Users never register disparate accounts to access different areas of the platform.

```
                                  ┌───────────────────────────────┐
                                  │   Unified User Identity       │
                                  │   (Permanent MEL Account ID)  │
                                  └──────────────┬────────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
          ┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
          │  Student Mode   │           │ Instructor Mode │           │  Partner Agent  │
          │  (Active Track) │           │ (Studio/Payout) │           │  (Institutional)│
          └─────────────────┘           └─────────────────┘           └─────────────────┘
```

### 3.2 Permanent Account Identifier (MEL Account ID)
Upon account creation, the system assigns an immutable, lifetime identifier:
$$\mathbf{MEL\text{-}YYYY\text{-}NNNNNN} \quad (\text{e.g., } \mathbf{MEL\text{-}2026\text{-}004812})$$
* **Permanence**: The MEL Account ID serves as the student’s lifelong academic identity.
* **Institutional Independence**: When a student enrolls in a school, college, or university affiliated with the platform, the institution links to this ID. If the student graduates or leaves the institution, their MEL ID, course history, badges, and certificates remain intact in their personal possession.

### 3.3 Dynamic Role & Dual-Mode Switching
* **Seamless Context Toggle**: Users authorized as instructors or administrators toggle between **Student Mode** and **Instructor Mode** with a single click from the user navigation menu.
* **Shared Session State**: Mode switching updates the active workspace context in the session without requiring re-authentication.

### 3.4 Role-Based Access Control (RBAC) Hierarchy
1. **Student**: Course enrollment, lecture playback, quizzes, assignments, exam sitting, container sandbox access, portfolio generation.
2. **Instructor**: Curriculum authoring studio, lecture uploader, assignment grader, live class broadcaster, revenue analytics.
3. **Partner Administrator**: Institutional roster manager, cohort tracker, custom institutional curriculum publisher, institutional revenue collector.
4. **Platform Administrator**: User governance, teacher application approval, payment manual review, security auditing, and container infrastructure monitoring.

---

## 4. Universal Sign-In Portal Specification

The platform utilizes a **single, universal authentication entry point** across all roles, eliminating disjointed URLs.

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│                      [ 🛡️ Myanmar E-Learning ]                         │
│                                                                        │
│                    Sign in to Myanmar E-Learning                       │
│        Learn, teach, and manage your learning journey in one place.    │
│                                                                        │
│        ┌──────────────────────────────────────────────────────┐        │
│        │ Account ID / Email                                   │        │
│        │ [ MEL-2026-00421 or student@example.com            ] │        │
│        └──────────────────────────────────────────────────────┘        │
│        ┌──────────────────────────────────────────────────────┐        │
│        │ Password                                             │        │
│        │ [ •••••••••••••••••••••••••••••••••• ]               │        │
│        └──────────────────────────────────────────────────────┘        │
│                                                                        │
│        [✓] Remember me                        Forgot Password?         │
│                                                                        │
│        ┌──────────────────────────────────────────────────────┐        │
│        │                       Sign In                        │        │
│        └──────────────────────────────────────────────────────┘        │
│                                                                        │
│        New to Myanmar E-Learning? Create an account                    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Interface Specifications
* **Page Title**: `Sign in to Myanmar E-Learning`
* **Supporting Text**: `Learn, teach, and manage your learning journey in one place.`
* **Credential Input**: Dual-purpose field accepting either `Account ID` (e.g., `MEL-2026-00421`) or verified `Email Address`.
* **Action Button**: `Sign In`
* **Registration Prompt**: `New to Myanmar E-Learning? Create an account`
* **Intelligent Redirection Matrix**:
  * Users in Student Mode $\rightarrow$ `/dashboard/`
  * Instructors in Teacher Mode $\rightarrow$ `/teacher/dashboard/` (or `/cyber/` studio)
  * Institutional Partner Representatives $\rightarrow$ `/partner/portal/`
  * System Administrators $\rightarrow$ `/console/`

---

## 5. Student Membership & Pricing Structure

Myanmar E-Learning implements a three-tier student subscription model designed to maximize adoption while sustainably financing computing overhead.

```text
Student Account Tiers
│
├── 1. Starter   ──► 0 MMK (Free Lifetime Access)
├── 2. Standard  ──► 5,000 MMK / Month  (50,000 MMK / Year — Saves 10,000 MMK)
└── 3. Premium   ──► 15,000 MMK / Month (150,000 MMK / Year — Saves 30,000 MMK)
```

### 5.1 Plan Specifications

#### 1. Starter Plan — Free (0 MMK)
* **Target Audience**: Exploratory learners, high school students, and prospective members evaluating the platform.
* **Pricing**: `0 MMK` (Lifetime Free).
* **Included Features**:
  * Access to all platform-wide Free Courses.
  * Preview lessons (Module 1 and 2) across Standard and Premium courses.
  * Curated learning video streams.
  * Foundational learning resources and reading documentation.
  * Formative diagnostic quizzes.
  * Personal Student Dashboard and basic progress tracking.
* **Explicit Restrictions**:
  * No access to paid course catalogs.
  * No official course examinations.
  * No official verified certificates.
  * No access to containerized cyber range / cloud sandboxes.
  * No premium downloadable toolkits.

#### 2. Standard Plan — 5,000 MMK / Month (50,000 MMK / Year)
* **Target Audience**: Primary mass-market student body, collegiate students, and self-taught developers.
* **Pricing**:
  * **Monthly**: `5,000 MMK / month`
  * **Yearly**: `50,000 MMK / year` *(Saves 10,000 MMK compared to 12 months standard rate)*.
* **Included Features**:
  * Complete, unrestricted access to the **Myanmar E-Learning Standard Course Catalog**.
  * Full video lectures with adaptive bitrates.
  * Comprehensive lesson notes, code repositories, and study guides.
  * Module quizzes and automated assignment grading.
  * Detailed learning progress and historical completion records.
  * Selected foundational practical sandbox activities (Shared container pool).
  * Eligibility to sit for course examinations and earn verified certificates (subject to individual course requirements).
  * Access to the student learning community and peer discussion forums.
  * Standard 10% discount on live masterclasses and workshops.

#### 3. Premium Plan — 15,000 MMK / Month (150,000 MMK / Year)
* **Target Audience**: Advanced technology students, aspiring cybersecurity engineers, AI practitioners, and professional career switchers.
* **Pricing**:
  * **Monthly**: `15,000 MMK / month`
  * **Yearly**: `150,000 MMK / year` *(Saves 30,000 MMK compared to 12 months standard rate)*.
* **Included Features**:
  * **All Standard Tier features included**.
  * Access to **Premium Courses** and advanced professional tracks.
  * **Dedicated Hands-on Cyber Range & Cloud Lab Sandboxes**:
    * Individual OpenVPN tunnel (`.ovpn`) connecting directly to the isolated lab subnet (`10.10.0.0/16`).
    * Full penetration testing targets, root flags (`root.txt`), and user flags (`user.txt`).
    * High-performance browser-based terminal fallback.
  * Capstone industry-grade projects with mentor feedback.
  * Advanced practice exams and certification simulations.
  * Premium downloadable toolkits and career development playbooks.
  * High-tier 25% discount on live cohorts and proctored examinations.
  * Priority 24/7 fast-track customer support.
  * Exclusive access to premium learning events, hackathons, and guest masterclasses.

---

## 6. Comprehensive Pricing & Feature Comparison Table

| Feature / Capability | Starter (Free) | Standard (5,000 MMK/mo) | Premium (15,000 MMK/mo) |
| :--- | :---: | :---: | :---: |
| **Monthly Pricing** | **Free (0 MMK)** | **5,000 MMK** | **15,000 MMK** |
| **Yearly Pricing** | **Free** | **50,000 MMK** *(Save 10k)* | **150,000 MMK** *(Save 30k)* |
| **Free Foundation Courses** | ✓ (Full) | ✓ (Full) | ✓ (Full) |
| **Standard Course Catalog** | Preview Only | ✓ (Full Access) | ✓ (Full Access) |
| **Premium & Advanced Courses** | ✕ | Limited / Selected | ✓ (Full Access) |
| **Quizzes & Diagnostic Tests** | Selected Only | ✓ (Full Access) | ✓ (Full Access) |
| **Assignments & Homework Grading**| Limited | ✓ (Full Access) | ✓ (Full Access) |
| **Foundational Sandbox Labs** | ✕ | Limited Quota (2 hrs/day) | High-Priority Quota |
| **Advanced Cyber Range / VPN** | ✕ | ✕ | **✓ (Isolated 10.10.0.0/16)** |
| **Course Examinations** | ✕ | Eligible Courses Included | Eligible & Advanced Included |
| **Verified Digital Certificates** | ✕ | Eligible Courses Included | Eligible & Advanced Included |
| **Capstone Projects & Reviews** | ✕ | Selected | ✓ (Full Portfolio & Review) |
| **Instructor-Led Courses** | ✕ | Selected | Full Selection / Premium |
| **Live Class / Bootcamp Discounts**| ✕ | 10% Standard Discount | **25% High Discount** |
| **Career & Resume Toolkits** | ✕ | ✕ | ✓ (Full Access) |
| **Support SLA** | Community | Standard (48 hrs) | **Priority Fast-track (12 hrs)** |

---

## 7. Course Access, Examination & Certification Policy

To prevent systemic abuse and protect institutional academic integrity, **a Membership Plan does not automatically guarantee every certificate or proctored examination**.

```
Course Operational Structure
├── 1. Learning Access  ──► Standard / Premium Membership
├── 2. Quizzes & Tasks  ──► Continuous Formative Evaluation
├── 3. Course Exam      ──► Course Policy (Included vs Proctored Voucher)
└── 4. Certification   ──► Cryptographically Signed Certificate (Score ≥ 70%)
```

### Policy Categories:
1. **Included Assessment (Standard/Premium)**:
   * *Example*: *Python Programming Fundamentals* — Lectures, quizzes, final examination, and verified digital certificate are completely covered by the Standard subscription once the student passes the threshold ($\ge 70\%$).
2. **Specialized Proctored Assessment (Additional Voucher Model)**:
   * *Example*: *Offensive Cyber Security Specialist* or *Advanced Cloud Architect* — Instructional lectures and sandbox environments are accessible under Premium; however, sitting for an intensive 24-hour practical proctored examination requiring dedicated compute clusters and human evaluation may require an individual assessment voucher.

---

## 8. Student Merit: "Associate" Achievement Framework

**"Associate" is an earned academic achievement title, NOT a purchasable subscription tier.**

```
                      ┌─────────────────────────────────────────┐
                      │   Active Student (Any Membership Tier)  │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │      Verification & Audit Engine        │
                      │  • ≥ 3 Verified Core Track Courses (80%)│
                      │  • ≥ 5 Assessed Practical Labs / CTFs   │
                      │  • ≥ 1 Reviewed Industry Capstone       │
                      │  • ≥ 100 Verified Academic Hours        │
                      │  • Clear Academic Integrity Record      │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │    "Associate of Myanmar E-Learning"    │
                      │   (Public Verifiable Credential & URL)  │
                      └─────────────────────────────────────────┘
```

### Associate Qualification Criteria
The platform analytics engine automatically evaluates students against rigorous metrics:
1. **Curriculum Mastery**: Successfully completed at least 3 Track Core Courses with a cumulative grade point average of $\ge 80\%$.
2. **Practical Competence**: Successfully conquered at least 5 hands-on lab targets or CTF challenges.
3. **Capstone Demonstration**: Built and submitted 1 reviewed, production-grade Capstone Project.
4. **Academic Commitment**: Accumulated $\ge 100$ verified active learning hours.
5. **Honor Code Compliance**: Zero recorded academic integrity violations or cheating flags.

*Recipients earn the title "Associate of Myanmar E-Learning", complete with an immutable public verification URL (`/verify/credential/<UUID>/`) and a cryptographically verifiable digital badge.*

---

## 9. Instructor System & Dual-Stream Revenue Model

Educators can transition from students to instructors by submitting credentials, sample lectures, and identity documents through the **Become an Instructor** portal.

### 9.1 Instructor Tier Classification
1. **Associate Instructor**: Entry-level educator holding a recognized Bachelor’s degree, diploma, or verified industry certification. Mentored by senior faculty.
2. **Professional Instructor**: Experienced practitioner with $\ge 2$ years of documented teaching experience, strong student feedback scores ($\ge 4.5/5.0$), and validated instructional design.
3. **Master Instructor**: Distinguished authority holding advanced degrees (Master's/PhD) or executive-level industry mastery with landmark curricula.

### 9.2 Revenue Allocation Matrix
Revenue generated from instructor-created courses and live interactive cohorts is split according to rank:

```text
┌─────────────────────────┬───────────────────────────┬───────────────────────────┐
│ Instructor Level        │ Recorded On-Demand Courses│ Live Interactive Classes  │
│                         │ (Instructor / MEL Platform│ (Instructor / MEL Platform│
├─────────────────────────┼───────────────────────────┼───────────────────────────┤
│ Associate Instructor    │ 40% / 60%                 │ 70% / 30%                 │
│ Professional Instructor │ 50% / 50%                 │ 75% / 25%                 │
│ Master Instructor       │ 60% / 40%                 │ 80% / 20%                 │
└─────────────────────────┴───────────────────────────┴───────────────────────────┘
```

* **Rationale**: Recorded courses leverage platform video transcode clusters, automated server grading, storage, and customer acquisition marketing (justifying a 40%–60% platform share). Live teaching demands real-time instructor hours and continuous direct interaction (justifying a 70%–80% educator share).

---

## 10. Institutional Partnership System (B2B School Engine)

Myanmar E-Learning provides an institutional multi-tenant portal for external educational organizations:
* Preschools & Primary Schools
* Secondary & High Schools (State & Private)
* International Schools (Cambridge IGCSE, Edexcel, IB)
* Technical & Vocational Training Centers (TVET)
* Colleges & Universities (Domestic & International)

### 10.1 Key Partner Capabilities
1. **Student Onboarding via MEL Account ID**: Partners add existing Myanmar E-Learning students directly by entering their permanent Account ID, dispatching an automated affiliation invitation.
2. **Cohort Management & Analytics**: Teachers and administrators monitor student attendance, video completion percentages, quiz scores, and lab completions in real time.
3. **Private Institutional Courses**: Schools author custom curricula accessible exclusively by their affiliated students.
4. **Partner Revenue Share**: For public courses authored by an accredited partner and approved on the MEL catalog, the revenue split is established at **75% to the Partner Institution** and **25% to Myanmar E-Learning**.

---

## 11. Cyber Range & Practical Lab Sandbox Subsystem

The Cybersecurity and Cloud Lab Engine is an **internal module** (`apps.labs` and `apps.vpn`) integrated directly inside Myanmar E-Learning, rather than an isolated external product.

```
                              ┌─────────────────────────────────────────┐
                              │ Student Machine (Kali Linux / Terminal) │
                              └────────────────────┬────────────────────┘
                                                   │
                                                   ▼ [UDP Port 1194]
                              ┌─────────────────────────────────────────┐
                              │ OpenVPN Gateway Subsystem (apps.vpn)    │
                              │ • Dedicated Tun IP (10.8.0.0/24)        │
                              └────────────────────┬────────────────────┘
                                                   │
                                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ Isolated Lab Network Subnet (10.10.0.0/16)                                            │
│                                                                                       │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐ │
│  │ Target 1: Linux PrivEsc │  │ Target 2: Web Security  │  │ Target 3: Network Lab  │ │
│  │ IP: 10.10.10.5          │  │ IP: 10.10.10.6          │  │ IP: 10.10.10.7         │ │
│  │ SSH Port 22 (sshd)      │  │ HTTP Port 80            │  │ Services               │ │
│  │ Flags: user.txt/root.txt│  │ Flag Injected           │  │ Flags Injected         │ │
│  └─────────────────────────┘  └─────────────────────────┘  └────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

* **Automated PKI Generator (`apps.vpn`)**: Pure-Python X.509 Certificate Engine using `cryptography` generates 2048-bit Root CA and client keys, producing standalone `.ovpn` configuration bundles on demand.
* **Isolated Subnet Sandboxing (`10.10.0.0/16`)**: Docker Engine provisions isolated bridge networks with strict security configurations:
  * Zero outbound WAN egress routing (prevents abuse or internet attacks).
  * Memory caps (`512MB`), tmpfs size limits, and `no-new-privileges:true`.
  * Dynamic flag injection into `/root/root.txt`, `/home/student/user.txt`, and database tables.
* **Browser Web Terminal Fallback (`apps.terminal`)**: Daphne WebSocket PTY bridge connecting directly to container terminals for learners without local VPN capabilities.

---

## 12. Domestic Payment Gateway & Financial Audit Workflow

Because international credit cards are not universally accessible in Myanmar, the platform integrates domestic mobile financial systems:
* **Supported Methods**: KBZPay, WavePay, AYA Pay, and direct domestic bank transfers.
* **Workflow**:
  1. Student selects a subscription tier or course exam voucher.
  2. Platform displays the official merchant account details and transaction QR code.
  3. Student transfers funds and inputs their transaction reference code and uploads a digital payment slip screenshot.
  4. System registers the payment as `Pending Review`.
  5. Administrative audit queue verifies the transaction against merchant banking logs and approves the payment with one click.
  6. Account subscription or course voucher activates immediately, generating an automated PDF tax receipt.

---

## 13. System Architecture & Technical Implementation Specifications

```
                     [ Web Clients / Kali Linux / Mobile Browsers ]
                                          │
                                          ▼
                               [ Nginx Reverse Proxy ]
                                          │
                        ┌─────────────────┴─────────────────┐
                        │                                   │
                  [ HTTP / HTTPS ]                   [ UDP Port 1194 ]
                        │                                   │
                        ▼                                   ▼
             [ Django ASGI (Daphne) ]              [ OpenVPN Gateway ]
             ├── apps.users (Auth & MEL ID)                 │
             ├── apps.courses (Multi-disciplinary LMS)      │
             ├── apps.billing (KBZPay / WavePay)            ▼
             ├── apps.labs (Docker Sandboxes) ──► [ Isolated Lab Subnet ]
             └── apps.vpn (PKI Certificate Engine)  (10.10.0.0/16)
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
 [ PostgreSQL 16 ]              [ Redis 7 Cache ]
```

### 13.1 Production Technology Stack
* **Operating System**: Ubuntu Server 24.04 LTS
* **Web Server & Edge Proxy**: Nginx 1.25 (SSL termination, rate limiting, static caching)
* **Application Framework**: Python 3.12, Django 5.1, Django REST Framework (DRF)
* **ASGI & WebSockets**: Daphne ASGI Server (handling Xterm.js real-time container PTY bridges)
* **Relational Database**: PostgreSQL 16 (strict relational constraints, JSONB indexing)
* **Caching & Message Broker**: Redis 7
* **Task Queues**: Celery 5.4 + Celery Beat (handling lab timeouts, video processing, email dispatch)
* **Virtualization & Sandboxes**: Docker Engine 26 with Docker Python SDK
* **VPN Subsystem**: OpenVPN Gateway (`kylemanna/openvpn`) + pure-Python `cryptography` PKI

### 13.2 Modular Django Applications Breakdown
* `apps.common`: Base UUID models, timestamps, landing page, health check endpoints.
* `apps.users`: Custom user model, permanent MEL Account ID generation, role switching.
* `apps.courses`: Multi-category course catalog, curriculum builder, lesson playback, video streaming.
* `apps.billing`: Subscription plans, user subscriptions, manual payment verification queue, revenue splits.
* `apps.instructor`: Teacher applications, tier promotion auditor, studio management, payout calculations.
* `apps.partner`: Institutional accounts, school cohort rosters, custom partner course builder.
* `apps.exams`: Question banks, automated quizzes, timed proctored examinations.
* `apps.certificates`: Verification engine, cryptographic PDF certificate generator with SHA-256 signatures.
* `apps.achievements`: Automated "Associate" status evaluation engine and badge wallet.
* `apps.labs`: Docker container lifecycle manager, isolated subnet bridges, dynamic flag injection.
* `apps.vpn`: Pure-Python X.509 PKI certificate authority, client `.ovpn` configuration bundle generator.
* `apps.terminal`: Daphne WebSocket to container PTY bridge.
* `apps.analytics`: Active study hour tracking, audit logging, completion rates.
* `apps.console`: Unified platform administrative console.

---

## 14. RESTful API Architecture & Mobile Readiness

All business logic is accessible via REST endpoints adhering to the OpenAPI 3.0 specification, enabling future native iOS and Android applications.

```
┌────────────────────────────────────────────────────────────────────────┐
│                              API Gateway                               │
│                                                                        │
│   POST /api/v1/auth/login/                (Universal JWT Authentication│
│   GET  /api/v1/user/profile/              (User & Active Mode Status)  │
│   POST /api/v1/user/switch-mode/          (Toggle Student/Instructor)  │
│   GET  /api/v1/courses/                   (Course Catalog & Filtering) │
│   GET  /api/v1/courses/{id}/curriculum/   (Lessons, Quizzes & Videos)  │
│   POST /api/v1/billing/subscribe/         (Initiate Plan & Submit Slip)│
│   GET  /api/v1/vpn/profile/               (Download .ovpn Profile)     │
│   POST /api/v1/labs/{id}/start/           (Spin up Container Sandbox)  │
│   POST /api/v1/labs/{id}/submit-flag/     (Verify User/Root Flags)     │
│   GET  /api/v1/certificates/{uuid}/verify/ (Public Cryptographic Audit) │
│   POST /api/v1/partner/cohort/invite/     (Invite Student by MEL ID)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Conclusion & Project Validation

This specification establishes **Myanmar E-Learning** as a modern, scalable, and socially transformative platform. By unifying broad academic disciplines under a single account identity, establishing an ultra-affordable **5,000 MMK Standard plan**, upholding course-level certification rigor, and providing deep institutional partnerships with integrated virtual lab sandboxes, the architecture delivers a robust, real-world ready digital education platform for Myanmar.
