# OWASP Juice Shop — Web Security Cyber Range Target

## Overview
OWASP Juice Shop is an intentionally insecure web application written in Node.js, Express, and Angular. It encompasses vulnerabilities across the entire **OWASP Top 10** alongside numerous other security flaws found in modern real-world enterprise web architectures.

In the **Future Tech Cyber Security Academy Range**, OWASP Juice Shop is orchestrated as a dedicated, containerized target with strict per-student isolation and dynamic flag generation.

## Upstream Project & Attribution
- **Project**: OWASP Juice Shop
- **Official Repository**: [https://github.com/juice-shop/juice-shop](https://github.com/juice-shop/juice-shop)
- **Author & Architect**: Bjoern Kimminich and the OWASP Juice Shop Team
- **License**: MIT / AGPL-3.0 Context for Educational Use
- **Attribution Statement**: This cyber range lab utilizes the open-source OWASP Juice Shop container distribution strictly for authorized hands-on cybersecurity education, vulnerability analysis, and defense training.

## Security Architecture & Range Isolation
1. **Zero Shared Instances**: Each enrolled student receives an ephemeral, isolated Docker container mapped to their specific session token (`/labs/i/<token>/`).
2. **Reverse Proxy Gateway**: Raw container ports are bound to an internal Docker bridge and proxied via the academy gateway, shielding internal daemon ports from the public internet.
3. **Dynamic Cryptographic Flags**: Objectives yield instance-specific dynamic flags in the format `FTACK{js_<id>_<token>}` to prevent flag-sharing or static replay across students.
4. **Hardened Resource Constraints**:
   - CPU Quota: `1.0 vCPU`
   - Memory Limit: `1024 MB RAM`
   - PIDs Ceiling: `150 processes`
   - Network Mode: Isolated Bridge Network
   - Security Options: `no-new-privileges: true`, `cap_drop: ALL`, `cap_add: NET_BIND_SERVICE`

## Challenge Curriculum
| ID | Challenge Name | OWASP Category | Difficulty | Points |
| :--- | :--- | :--- | :--- | :--- |
| `scoreboard` | Score Board Discovery | A01: Broken Access Control | Beginner | 50 |
| `admin_sqli` | Admin Login via SQL Injection | A03: Injection | Beginner | 100 |
| `dom_xss` | DOM-Based Cross-Site Scripting | A03: Injection | Intermediate | 100 |
| `path_traversal` | Confidential Document Traversal | A01: Broken Access Control | Intermediate | 100 |
| `basket_idor` | Basket IDOR Object Authorization | A01: Broken Access Control | Intermediate | 150 |

## AI Tutor Guidance Policy
Students can query the integrated **Socratic AI Tutor** for progressive conceptual and methodology hints without forfeiting the full learning experience. Direct solution flags are cryptographically filtered and never disclosed.

