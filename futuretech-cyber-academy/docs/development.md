# Future Tech Cyber Security Academy — Local Development Guide

## 1. Prerequisites
- **Python**: 3.12 or higher
- **Database**: PostgreSQL 15+ (Local or Docker) or SQLite (built-in local dev fallback)
- **Redis**: 7.x (optional for Phase 1 dev; memory layer fallback enabled)
- **Git**

---

## 2. Quickstart Setup

### Step 1: Clone or Navigate to Project
```bash
cd futuretech-cyber-academy
```

### Step 2: Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```
Ensure key environment variables are set:
```env
DEBUG=True
SECRET_KEY=futuretech-dev-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
# Leave POSTGRES_HOST empty to automatically use SQLite during local dev/tests:
POSTGRES_HOST=
```

### Step 3: Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Apply Database Migrations
```bash
python3 backend/manage.py migrate
```

### Step 5: Seed Demo Academy Curriculum
Populate the database with the complete **14-Module Diploma in Cyber Security**, 42 educational lessons, 1 Admin, 2 Instructors, and 5 Students:
```bash
python3 backend/manage.py seed_demo_data
```

### Step 6: Launch Development Server
```bash
python3 backend/manage.py runserver 0.0.0.0:8000
```
Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## 3. Pre-Seeded Accounts for Testing

| Role | Email Login | Default Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Dean / Super Admin** | `admin@futuretech.edu` | `CyberSec2026!` | Full System Dean Console & Django Admin |
| **Lead Instructor** | `instructor.morpheus@futuretech.edu` | `CyberSec2026!` | 6-Step Course Wizard & Curriculum Management |
| **Lab Instructor** | `instructor.trinity@futuretech.edu` | `CyberSec2026!` | Course Creation & Lab Guidance |
| **Student 1** | `student.neo@futuretech.edu` | `CyberSec2026!` | Student Dashboard & Diploma Enrollment |
| **Student 2** | `student.switch@futuretech.edu` | `CyberSec2026!` | Student Dashboard & Diploma Enrollment |

---

## 4. Running Automated Tests
The test suite validates RBAC rules, authentication, course workflows, progress percentage calculations, security file validations, and REST APIs:
```bash
python3 backend/manage.py test tests
```

