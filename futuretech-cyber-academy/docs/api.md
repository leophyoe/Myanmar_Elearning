# Future Tech Cyber Security Academy — REST API Documentation

## 1. Overview
Future Tech Cyber Security Academy provides programmatic REST API endpoints for institutional portal integration, learning analytics, and external student dashboards.

- **Base URL**: `/api/`
- **Format**: `JSON`
- **Authentication**: Session Authentication (`Cookie`), HTTP Basic Auth, or Header Token (`Authorization`).

---

## 2. Endpoints Reference

### 2.1 Platform Statistics
Returns high-level institutional health metrics.

- **URL**: `GET /api/stats/`
- **Permissions**: Public
- **Sample Response**:
```json
{
  "platform": "Future Tech Cyber Security Academy",
  "phase": "Phase 1: E-Learning Foundation",
  "total_students": 5,
  "published_courses": 1,
  "total_lessons": 42
}
```

---

### 2.2 Course Catalog API
List all published academic courses and diploma tracks.

- **URL**: `GET /api/courses/`
- **Permissions**: Public (Shows published courses; instructors/admins see all courses)
- **Query Parameters**:
  - `page`: Page number (pagination)
- **Sample Response**:
```json
{
  "count": 1,
  "results": [
    {
      "id": "e4907eff-1db8-43ef-962d-3ebcf613d7b6",
      "title": "Diploma in Cyber Security (6-Month Professional Program)",
      "slug": "diploma-in-cyber-security",
      "short_description": "Comprehensive 14-module career diploma.",
      "level": "BEGINNER",
      "duration": "6 Months",
      "is_free": true,
      "price": "0.00",
      "total_lessons": 42
    }
  ]
}
```

---

### 2.3 Course Curriculum Detail
Fetch complete syllabus, modules, and lessons for a course.

- **URL**: `GET /api/courses/<slug>/`
- **Permissions**: Public
- **Sample Response**:
```json
{
  "id": "e4907eff-1db8-43ef-962d-3ebcf613d7b6",
  "title": "Diploma in Cyber Security (6-Month Professional Program)",
  "slug": "diploma-in-cyber-security",
  "level": "BEGINNER",
  "total_lessons": 42,
  "modules": [
    {
      "id": "c0183180-2a86-4f70-bbf6-b5fa53f2c589",
      "title": "Module 1: Cybersecurity Foundations & Ethics",
      "order": 1,
      "lessons_count": 3
    },
    {
      "id": "893c5fb9-8a9d-472e-8360-ffcf385b00c3",
      "title": "Module 2: Computer Networking & Architecture",
      "order": 2,
      "lessons_count": 3
    }
  ]
}
```

---

### 2.4 Student Enrollments API
Lists courses in which the authenticated student is currently registered.

- **URL**: `GET /api/enrollments/`
- **Permissions**: Authenticated Student or Admin
- **Sample Response**:
```json
{
  "count": 1,
  "results": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "course_title": "Diploma in Cyber Security (6-Month Professional Program)",
      "course_slug": "diploma-in-cyber-security",
      "status": "ACTIVE",
      "progress_percentage": 50.0,
      "enrolled_at": "2026-09-17T12:00:00Z"
    }
  ]
}
```

---

### 2.5 Auth Status
Check current session authentication state.

- **URL**: `GET /api/auth/`
- **Permissions**: Public
- **Sample Response (Authenticated)**:
```json
{
  "authenticated": true,
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "student.neo@futuretech.edu",
    "username": "student_neo",
    "role": "STUDENT"
  }
}
```

