# OWASP Juice Shop Web Security Lab Architecture

## 1. Executive Summary
**OWASP Juice Shop** is an intentionally vulnerable web application created by **Bjoern Kimminich** and maintained under the **OWASP Foundation**. It serves as an industry-standard training ground for web application security, modern API defense, and the OWASP Top 10 vulnerabilities.

The **Future Tech Cyber Security Academy** integrates OWASP Juice Shop as an isolated, containerized Cyber Range target for hands-on auditing, penetration testing, and secure development education.

---

## 2. Upstream Attribution & Open-Source Licensing
- **Upstream Repository**: [https://github.com/juice-shop/juice-shop](https://github.com/juice-shop/juice-shop)
- **Primary Author & Lead**: Bjoern Kimminich
- **Organization**: OWASP (Open Web Application Security Project)
- **License**: AGPL-3.0 / Open Source Educational Usage
- **Academy Attribution**: Future Tech Cyber Security Academy acknowledges the immense educational contribution of the OWASP Juice Shop project. All container deployments utilize unmodified, pinned upstream container releases (`bkimminich/juice-shop:v17.1.1`) encapsulated inside our proprietary cyber range sandboxing orchestration layer.

---

## 3. Strict Range Security Isolation Policy

### Why Shared Public Targets Are Prohibited
Traditional shared instances (such as a single public test server) suffer from severe educational and security shortcomings:
1. **Cross-Student Interference**: Student A exploiting an injection or modifying user accounts breaks the environment for Student B.
2. **Flag Sniffing & Cheating**: One student's solution or exploit artifacts remain visible in shared databases or logs.
3. **Denial-of-Service / Instability**: A crashed instance denies access to all concurrent learners.

### The Future Tech Dedicated Container Model
To ensure complete learning autonomy and uncompromised security, the platform enforces:

```
[ Enrolled Student ]
         │
         ▼
[ Future Tech Cyber Range Gateway ]
   (/labs/i/<secure-instance-token>/)
         │  (Token Ownership & TTL Verification)
         ▼
[ Docker Sandbox Orchestrator ]
         │  (Resource Limits & Capability Drops)
         ▼
[ Dedicated Isolated Container ]
   (10.10.X.15:3000 — Private Bridge Network)
```

1. **Per-Student Sandbox**: Each student receives a distinct Docker container allocated on an isolated subnet.
2. **Controlled Reverse-Proxy Gateway**:
   - Access is mediated exclusively via `/labs/i/<secure-instance-token>/`.
   - Raw container ports (e.g. `3000`) are bound to internal Docker bridge interfaces, never exposed directly to the public internet.
3. **Cross-Student Isolation Enforcement**:
   - The gateway validates `instance.student == request.user`.
   - If Student A attempts to access Student B's instance token, the platform instantly terminates the request with `403 Forbidden`.
4. **Hardened Docker Security Flags**:
   - `no-new-privileges: true`
   - `cap_drop: ["ALL"]`
   - `cap_add: ["NET_BIND_SERVICE"]`
   - Strict resource boundaries (1.0 vCPU, 1024MB RAM, 150 PIDs limit).

---

## 4. Multi-Challenge Dynamic Flag System

To prevent flag sharing and encourage original exploitation, all challenge flags are dynamically bound to the student's unique instance token prefix (`instance.uuid.hex[:8]`):

$$\text{Flag} = \text{"FTACK\{js\_"} + \text{challenge\_id} + \text{"\_"} + \text{instance\_token[:8]} + \text{"\}"}$$

### Core Objectives Matrix
| Objective ID | Challenge Title | OWASP Category | Points | Dynamic Pattern |
| :--- | :--- | :--- | :--- | :--- |
| `scoreboard` | Score Board Discovery | A01: Broken Access Control | 50 | `FTACK{js_scoreboard_<token>}` |
| `admin_sqli` | Admin Login via SQL Injection | A03: Injection | 100 | `FTACK{js_admin_sqli_<token>}` |
| `dom_xss` | DOM-Based Cross-Site Scripting | A03: Injection | 100 | `FTACK{js_dom_xss_<token>}` |
| `path_traversal` | Confidential Document Traversal | A01: Broken Access Control | 100 | `FTACK{js_path_traversal_<token>}` |
| `basket_idor` | Basket IDOR Broken Object Auth | A01: Broken Access Control | 150 | `FTACK{js_basket_idor_<token>}` |

Flags submitted by Student A cannot be reused by Student B because the dynamic generator validates the flag against the specific instance database record.

---

## 5. Socratic AI Security Tutor

The Cyber Range features an integrated Socratic AI Tutor endpoint (`/labs/i/<token>/hint/`):
- **Level 1 (Conceptual Hint)**: Explains the underlying vulnerability theory (e.g., how client-side routing works in single-page apps) with 0% penalty.
- **Level 2 (Methodology Hint)**: Suggests testing tools (e.g., Burp Suite Repeater, DevTools source inspection) with a 10% penalty.
- **Level 3 (Actionable Guidance)**: Outlines specific payloads or routes without ever leaking the raw solution flag (25% penalty).

---

## 6. Lifecycle Management & Automatic Teardown
1. **Provisioning**: Launched on-demand when a student clicks "Launch Lab Workspace".
2. **TTL Timeout**: Default runtime is 120 minutes. Students can extend by +30 minutes.
3. **Reset**: Instantly wipes the database/container and restores pristine state while maintaining student progress records.
4. **Celery Celery Beat Cleanup**: Expired instances are decommissioned automatically by `sweep_expired_labs`.

