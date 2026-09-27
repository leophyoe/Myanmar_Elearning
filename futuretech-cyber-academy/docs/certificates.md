# Digital Certificates & Cryptographic Verification Architecture

## 1. Overview
Future Tech Academy provides cryptographically verifiable digital diplomas issued upon graduation. Each credential can be verified by employers, accreditors, and universities without requiring access to student accounts or exposing sensitive personal data.

---

## 2. Certificate Architecture (`apps.certificates`)

### 2.1 Identifiers & Verification Tokens
- **Certificate Number**: Institutional formatted serial number, e.g. `FTCSA-2026-A1B2C3D4`.
- **Verification Token**: Cryptographically secure UUIDv4 (`verification_token`), indexed for $O(1)$ lookups.
- **Issuance Date & Completion Date**: Tracked with timezone-aware timestamps.

### 2.2 Vector SVG QR Code Engine
- **Implementation**: Pure Python vector SVG generation (`apps/certificates/services.py:generate_svg_qr`).
- **Zero Binary Dependencies**: Completely eliminates requirements for native C libraries like `libpng`, `zlib`, or external Python imaging dependencies.
- **Rendering**: Directly outputs optimized, scalable vector `<svg>` markup that can be printed at 300+ DPI without pixelation.

### 2.3 Public Verification Gateway
- **URL**: `/verify/<certificate_number>/` (e.g. `/verify/FTCSA-2026-A1B2C3D4/`).
- **Zero-Trust Anonymous Access**: Does not require user authentication.
- **PII Shielding**: Displays only public academic data (Student Full Name, Course Title, Issue Date, Validity Status). The student's email, phone number, and account credentials are strictly withheld.
- **Audit Logging**: Every verification request logs the client IP address and User-Agent to `CertificateVerification` for forensic auditability.

---

## 3. Printable Diploma Layout
- The diploma view at `/certificates/<certificate_number>/` uses responsive print-ready CSS (`@media print`).
- Renders institutional seals, official signatory titles, graduation credentials, and the scannable SVG QR badge.

