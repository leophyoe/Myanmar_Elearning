from django.core.management.base import BaseCommand
from django.utils.text import slugify
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User
from apps.core.permissions import RoleChoices
from apps.courses.models import (
    CourseCategory, Course, CourseModule, Lesson, LessonType, CourseStatus, CourseLevel, CourseReview
)
from apps.assessments.models import (
    QuestionBank, Quiz, Question, QuestionOption, QuestionType, QuestionDifficulty,
    QuizAttempt, QuizAnswer, Assignment, AssignmentSubmission, AssignmentFeedback,
    SubmissionStatus, Exam, ExamType, ExamQuestion, ExamOption, ExamAttempt, ExamAnswer,
    PracticalLabTask, AssessmentWeight
)
from apps.learning_paths.models import LearningPath, LearningPathCourse, StudentLearningPath, LearningPathLevel
from apps.certificates.models import CertificateTemplate, Certificate, CertificateStatus
from apps.certificates.services import CertificateGenerationService
from apps.achievements.models import Achievement, StudentAchievement, BadgeType
from apps.enrollments.models import Enrollment
from apps.progress.models import LessonProgress
from apps.notifications.models import Announcement, Notification, NotificationType
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabAccessType, LabObjective,
    LabHint, LabFlag, FlagType,
    ChallengeCategory, Challenge,
    CTFEvent, CTFEventStatus, CTFScore
)

class Command(BaseCommand):
    help = "Seeds initial demo data: 1 Admin, 2 Instructors, 5 Students, and the 14-Module Certificate in Cyber Security."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Seeding Future Tech Cyber Security Academy Demo Data ==="))

        # 1. Create Categories
        categories_data = [
            ("Cyber Security", "cyber-security", "Comprehensive cyber defense and resilience"),
            ("Networking", "networking", "Network architecture, routing, protocols, and packet analysis"),
            ("Linux", "linux", "Linux systems administration, permissions, and command line security"),
            ("Ethical Hacking", "ethical-hacking", "Offensive testing methodologies, reconnaissance, and enumeration"),
            ("Web Security", "web-security", "OWASP Top 10 vulnerabilities, secure web architectures, and API defense"),
            ("SOC & SIEM", "soc-siem", "Security Operations Center protocols, alert correlation, and Wazuh SIEM"),
            ("Digital Forensics", "digital-forensics", "Evidence preservation, memory analysis, and filesystem triage"),
            ("Python", "python", "Automating cybersecurity workflows, socket scripting, and telemetry parsers"),
            ("Cloud Security", "cloud-security", "Cloud IAM, container isolation, and infrastructure as code security"),
            ("DevSecOps", "devsecops", "CI/CD security scanning, pipeline automation, and shift-left defense"),
        ]

        cat_objs = {}
        for name, slug, desc in categories_data:
            cat, _ = CourseCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc}
            )
            cat_objs[slug] = cat

        # 2. Create 1 Super Administrator
        admin_user, _ = User.objects.get_or_create(
            email="admin@futuretech.edu",
            defaults={
                'username': 'academy_admin',
                'first_name': 'Chief',
                'last_name': 'Administrator',
                'role': RoleChoices.SUPER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password("CyberSec2026!")
        admin_user.save()
        self.stdout.write(self.style.SUCCESS(f"Created Admin: {admin_user.email}"))

        # 3. Create 2 Instructors
        ins1, _ = User.objects.get_or_create(
            email="instructor.morpheus@futuretech.edu",
            defaults={
                'username': 'morpheus',
                'first_name': 'Morpheus',
                'last_name': 'Vance',
                'role': RoleChoices.INSTRUCTOR,
                'is_staff': True,
            }
        )
        ins1.set_password("CyberSec2026!")
        ins1.save()
        if hasattr(ins1, 'instructor_profile'):
            ins1.instructor_profile.specialization = "Offensive Security & Penetration Testing"
            ins1.instructor_profile.save()

        ins2, _ = User.objects.get_or_create(
            email="instructor.trinity@futuretech.edu",
            defaults={
                'username': 'trinity',
                'first_name': 'Trinity',
                'last_name': 'Chen',
                'role': RoleChoices.INSTRUCTOR,
                'is_staff': True,
            }
        )
        ins2.set_password("CyberSec2026!")
        ins2.save()
        if hasattr(ins2, 'instructor_profile'):
            ins2.instructor_profile.specialization = "Blue Team Defense, SOC & Incident Response"
            ins2.instructor_profile.save()

        self.stdout.write(self.style.SUCCESS(f"Created Instructors: {ins1.email}, {ins2.email}"))

        # 4. Create 5 Students
        students_data = [
            ("student.neo@futuretech.edu", "neo", "Thomas", "Anderson"),
            ("student.alice@futuretech.edu", "alice", "Alice", "Smith"),
            ("student.bob@futuretech.edu", "bob", "Robert", "Johnson"),
            ("student.cipher@futuretech.edu", "cipher", "David", "Miller"),
            ("student.switch@futuretech.edu", "switch", "Elena", "Reyes"),
        ]

        for email, uname, fname, lname in students_data:
            stu, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': uname,
                    'first_name': fname,
                    'last_name': lname,
                    'role': RoleChoices.STUDENT,
                }
            )
            stu.set_password("CyberSec2026!")
            stu.save()
        self.stdout.write(self.style.SUCCESS("Created 5 Students."))

        # 5. Create Sample Course: CERTIFICATE IN CYBER SECURITY
        course, _ = Course.objects.get_or_create(
            slug="diploma-in-cyber-security",
            defaults={
                'title': 'CERTIFICATE IN CYBER SECURITY',
                'title_en': 'Certificate in Cyber Security',
                'title_my': 'ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း',
                'course_type': CourseType.CERTIFICATE,
                'short_description': 'A comprehensive 10-month professional cybersecurity certificate program combining theory and practical learning.',
                'description': (
                    "Welcome to the Future Tech Cyber Security Academy flagship certificate program. "
                    "This comprehensive curriculum covers 14 rigorous professional modules spanning foundational computer security, "
                    "operating systems, networking, ethical penetration testing, web defense, Wazuh SIEM telemetry, "
                    "incident response, digital forensics, and capstone engineering."
                ),
                'level': CourseLevel.BEGINNER,
                'duration': '10 Months',
                'language': 'English',
                'price': 0.00,
                'is_free': True,
                'status': CourseStatus.PUBLISHED,
                'created_by': ins1,
            }
        )
        course.categories.set(cat_objs.values())

        # 6. Define 14 Modules with at least 3 original lessons each
        modules_curriculum = [
            (
                "Introduction to Cyber Security",
                "Foundational security concepts, CIA Triad, threat classifications, risk management, and professional ethics.",
                [
                    ("The CIA Triad & Core Principles of Information Assurance", LessonType.ARTICLE, 45,
                     "# The CIA Triad & Core Principles of Information Assurance\n\n"
                     "Information security is anchored upon three fundamental pillars: Confidentiality, Integrity, and Availability.\n\n"
                     "### 1. Confidentiality\n"
                     "Ensures that information is concealed from unauthorized individuals, entities, or processes.\n"
                     "- Mechanisms: Cryptographic ciphers (AES-256), access control lists (ACLs), multi-factor authentication (MFA).\n\n"
                     "### 2. Integrity\n"
                     "Guarantees that information remains accurate, authentic, and uncorrupted throughout its lifecycle.\n"
                     "- Mechanisms: SHA-256 cryptographic hashes, digital signatures, version controls.\n\n"
                     "### 3. Availability\n"
                     "Ensures systems, communication channels, and data are promptly accessible to authorized users when needed.\n"
                     "- Mechanisms: Redundant server clusters, automated failovers, DDoS mitigation scrubbing."),

                    ("Threat Modeling, Vulnerability Taxonomies & Risk Assessment", LessonType.READING, 50,
                     "# Threat Modeling & Risk Calculations\n\n"
                     "Cybersecurity professionals quantify risk using formalized equations:\n\n"
                     "$$\\text{Risk} = \\text{Threat} \\times \\text{Vulnerability} \\times \\text{Impact}$$\n\n"
                     "### Core Terminology:\n"
                     "- **Asset**: Any data, system, hardware, or human resource of organizational value.\n"
                     "- **Vulnerability**: A flaw, misconfiguration, or weakness in an asset.\n"
                     "- **Threat**: An event, actor, or condition capable of exploiting a vulnerability.\n"
                     "- **Attack Surface**: The total sum of reachable entry points where an attacker can interact with the system."),

                    ("Social Engineering Tactics & Password Defense Architecture", LessonType.PRACTICAL, 60,
                     "# Social Engineering Tactics & Password Defense\n\n"
                     "Human error remains a principal attack vector in organizational intrusions.\n\n"
                     "### Common Vectors:\n"
                     "1. **Phishing & Spear Phishing**: Fabricated emails targeting individuals with deceptive links or attachments.\n"
                     "2. **Pretexting**: Inventing an authoritative scenario to extract sensitive records.\n"
                     "3. **Credential Stuffing**: Replaying breached username/password databases across services.\n\n"
                     "### Defensive Counter-Measures:\n"
                     "- Deploy FIDO2/WebAuthn hardware tokens.\n"
                     "- Implement Argon2id or bcrypt adaptive key-derivation password hashing functions.\n"
                     "- Enforce outbound email authentication: SPF, DKIM, and DMARC policies."),
                ]
            ),
            (
                "Computer Systems & OS Security",
                "Architectural security paradigms across Linux and Windows, user privilege separation, DAC/MAC, and system hardening.",
                [
                    ("Operating System Architecture & Kernel Rings", LessonType.ARTICLE, 45,
                     "# Operating System Architecture & Kernel Boundaries\n\n"
                     "Modern computer architectures enforce hierarchical privilege levels known as protection rings:\n"
                     "- **Ring 0 (Kernel Space)**: Direct hardware interaction, memory management, device drivers.\n"
                     "- **Ring 3 (User Space)**: Unprivileged applications, web browsers, user shells.\n\n"
                     "System calls (syscalls) serve as the controlled gateway between User Space and Kernel Space."),

                    ("Discretionary vs Mandatory Access Control Models", LessonType.READING, 50,
                     "# Discretionary vs Mandatory Access Control\n\n"
                     "### Discretionary Access Control (DAC)\n"
                     "File owners possess the discretion to dictate read, write, and execute permissions (e.g. POSIX chmod, Windows ACLs).\n\n"
                     "### Mandatory Access Control (MAC)\n"
                     "Access decisions are enforced centrally by the operating system kernel regardless of owner intent (e.g. SELinux, AppArmor)."),

                    ("System Hardening Baselines & Attack Surface Reduction", LessonType.PRACTICAL, 60,
                     "# System Hardening Baselines\n\n"
                     "Hardening involves disabling unnecessary system services, enforcing least privilege, and implementing automated audits.\n\n"
                     "1. Decommission unused daemons (telnet, ftp, legacy r-services).\n"
                     "2. Apply Center for Internet Security (CIS) Benchmark baselines.\n"
                     "3. Implement centralized system log auditing via auditd."),
                ]
            ),
            (
                "Networking Fundamentals",
                "Dissection of the OSI and TCP/IP protocol stacks, IPv4/IPv6 subnetting calculations, DNS, DHCP, and packet analysis.",
                [
                    ("OSI 7-Layer vs TCP/IP Protocol Stack Dissection", LessonType.ARTICLE, 50,
                     "# OSI 7-Layer vs TCP/IP Protocol Model\n\n"
                     "Understanding the movement of data down and up the protocol stack via encapsulation and decapsulation:\n"
                     "- Layer 7: Application (HTTP, DNS, SSH)\n"
                     "- Layer 4: Transport (TCP, UDP - segments/datagrams)\n"
                     "- Layer 3: Network (IP, ICMP - packets)\n"
                     "- Layer 2: Data Link (Ethernet, MAC - frames)\n"
                     "- Layer 1: Physical (Bits across copper/fiber)"),

                    ("IPv4 Subnetting Mechanics & CIDR Notation", LessonType.PRACTICAL, 60,
                     "# IPv4 Subnetting & CIDR Mechanics\n\n"
                     "A 32-bit IPv4 address is divided into Network and Host portions using a Subnet Mask.\n\n"
                     "### Example: `/26` Subnetting\n"
                     "- Subnet Mask: `255.255.255.192`\n"
                     "- Total IPs per subnet: $2^{(32-26)} = 64$\n"
                     "- Usable Host IPs: $64 - 2 = 62$ (Network ID and Broadcast ID reserved)."),

                    ("Packet Dissection: Three-Way Handshake & ICMP", LessonType.VIDEO, 45,
                     "# Packet Dissection: TCP Three-Way Handshake\n\n"
                     "Establishing a reliable stateful connection requires three sequential flags:\n"
                     "1. Client -> Server: `[SYN]` (Sequence Number = X)\n"
                     "2. Server -> Client: `[SYN, ACK]` (Acknowledgment = X+1, Sequence = Y)\n"
                     "3. Client -> Server: `[ACK]` (Acknowledgment = Y+1)\n\n"
                     "Tear-down is concluded with `[FIN]` and `[ACK]` packets."),
                ]
            ),
            (
                "Linux for Cyber Security",
                "Command-line mastery, POSIX permissions, SUID privilege escalation, SSH hardening, and log parsing.",
                [
                    ("Headless Linux CLI Mastery & File Hierarchy Standard", LessonType.ARTICLE, 45,
                     "# Linux File Hierarchy Standard (FHS)\n\n"
                     "Critical directories in Linux system defense:\n"
                     "- `/etc/`: Global system configuration files (passwd, shadow, sshd_config).\n"
                     "- `/var/log/`: System and application logs (auth.log, syslog).\n"
                     "- `/proc/`: Virtual filesystem exposing real-time kernel and process states."),

                    ("POSIX File Permissions & SUID Privilege Escalation", LessonType.PRACTICAL, 60,
                     "# SUID / SGID Security\n\n"
                     "When the SetUID (4000) bit is placed on an executable binary, it executes with the privileges of the file owner (often root):\n\n"
                     "```bash\n"
                     "# Find all SUID executables owned by root:\n"
                     "find / -perm -4000 -user root -type f 2>/dev/null\n"
                     "```\n\n"
                     "Unsanitized PATH environment variables or built-in GTFOBins commands can lead to immediate local privilege escalation."),

                    ("SSH Cryptographic Hardening & Key Authentication", LessonType.PRACTICAL, 50,
                     "# SSH Daemon Hardening\n\n"
                     "Recommended settings for `/etc/ssh/sshd_config`:\n"
                     "- `PermitRootLogin no`\n"
                     "- `PasswordAuthentication no`\n"
                     "- `PubkeyAuthentication yes`\n"
                     "- `KexAlgorithms curve25519-sha256`"),
                ]
            ),
            (
                "Windows & Active Directory Security",
                "PowerShell auditing, Windows Defender Firewall, Event IDs, Active Directory Domain Services, Kerberos, and GPOs.",
                [
                    ("Windows Security Architecture & PowerShell Security", LessonType.ARTICLE, 50,
                     "# Windows Security Subsystems\n\n"
                     "Key components of Windows enterprise security:\n"
                     "- **LSASS (Local Security Authority Subsystem Service)**: Enforces security policies, manages user authentications.\n"
                     "- **SAM (Security Account Manager)**: Database storing local account password hashes.\n"
                     "- **Constrained Language Mode (CLM)**: Restricts PowerShell capabilities against unauthorized script execution."),

                    ("Active Directory Domain Services, OUs & Group Policy", LessonType.READING, 60,
                     "# Active Directory & Group Policy Architecture\n\n"
                     "Active Directory Domain Services (AD DS) manages centralized identity across enterprise networks:\n"
                     "- **Domain Controller (DC)**: The server validating and authenticating network principals.\n"
                     "- **Organizational Units (OUs)**: Logical subdivisions holding users and computers.\n"
                     "- **Group Policy Objects (GPOs)**: Automated configuration sets pushed across all domain nodes."),

                    ("Kerberos Authentication & Windows Event ID Triage", LessonType.PRACTICAL, 60,
                     "# Windows Security Event Log Triage\n\n"
                     "Vital Windows Event IDs every security analyst must know:\n"
                     "- `4624`: Successful account logon.\n"
                     "- `4625`: Failed account logon (potential brute-force or password spraying).\n"
                     "- `4688`: A new process has been created (investigating suspicious process trees).\n"
                     "- `4720`: A user account was created."),
                ]
            ),
            (
                "Ethical Hacking Fundamentals",
                "Penetration testing methodology, Rules of Engagement, passive OSINT reconnaissance, Nmap scanning, and enumeration.",
                [
                    ("Rules of Engagement & Ethical Hacking Standards", LessonType.ARTICLE, 45,
                     "# Rules of Engagement (RoE)\n\n"
                     "Ethical penetration tests require explicit, legally binding permission documents:\n"
                     "- Defined IP address and domain scope.\n"
                     "- Authorized testing windows and contact protocols.\n"
                     "- Out-of-bounds systems (e.g. medical devices, third-party payment gateways).\n"
                     "- Strict compliance with legal statutes."),

                    ("Passive Reconnaissance & OSINT Information Gathering", LessonType.READING, 50,
                     "# OSINT Techniques\n\n"
                     "Gathering technical intelligence without actively transmitting packets to the target network:\n"
                     "- Certificate Transparency Logs (crt.sh).\n"
                     "- DNS enumeration via passive records (SecurityTrails).\n"
                     "- Search engine dorking to locate exposed credentials and endpoints."),

                    ("Network Scanning & Port Enumeration with Nmap", LessonType.PRACTICAL, 65,
                     "# Port Scanning Mechanics with Nmap\n\n"
                     "Analyzing target open ports and service versions:\n"
                     "```bash\n"
                     "nmap -sV -sC -T4 -p- 10.10.10.10\n"
                     "```\n"
                     "- `-sV`: Determine service/version information.\n"
                     "- `-sC`: Execute default NSE discovery scripts.\n"
                     "- `-p-`: Scan all 65,535 TCP ports."),
                ]
            ),
            (
                "Web Application Security",
                "HTTP/S mechanics, OWASP Top 10 vulnerabilities (SQLi, XSS, CSRF, IDOR, SSRF, File Uploads), and remediation.",
                [
                    ("HTTP Headers, Cookies & Session Management", LessonType.ARTICLE, 45,
                     "# HTTP Mechanics & Session Security\n\n"
                     "Securing modern stateless HTTP transactions:\n"
                     "- `Set-Cookie: sessionid=...; Secure; HttpOnly; SameSite=Strict`\n"
                     "- `HttpOnly`: Mitigates JavaScript access to session cookies (XSS protection).\n"
                     "- `SameSite=Strict`: Shields against Cross-Site Request Forgery (CSRF)."),

                    ("SQL Injection: Exploitation Mechanics & Parameterized Queries", LessonType.PRACTICAL, 65,
                     "# SQL Injection & Remediation\n\n"
                     "Occurs when untrusted user input is directly concatenated into a dynamic SQL query.\n\n"
                     "### Defense:\n"
                     "Always employ Prepared Statements (Parameterized Queries) or Object-Relational Mappers (ORMs):\n"
                     "```python\n"
                     "cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (user, pass_hash))\n"
                     "```"),

                    ("Cross-Site Scripting (XSS) & Content Security Policy", LessonType.PRACTICAL, 60,
                     "# Cross-Site Scripting (XSS)\n\n"
                     "Occurs when unescaped HTML or JavaScript is rendered in a victim's browser session.\n\n"
                     "### Types:\n"
                     "1. **Stored XSS**: Malicious script permanently saved in a database.\n"
                     "2. **Reflected XSS**: Script payload delivered via URL parameter.\n"
                     "3. **DOM-based XSS**: Insecure client-side DOM manipulation.\n\n"
                     "Deploying a strict `Content-Security-Policy` header restricts unauthorized script origins."),

                    ("Lab: OWASP Juice Shop Hands-on Security Testing", LessonType.PRACTICAL, 90,
                     "# Hands-on Cyber Range Lab: OWASP Juice Shop\n\n"
                     "In this interactive cyber range session, students deploy a private, dedicated instance of "
                     "the industry-standard **OWASP Juice Shop** web application target via the academy's secure gateway (`/labs/i/<token>/`).\n\n"
                     "### Lab Objectives:\n"
                     "1. **Score Board Discovery**: Locate hidden client-side single-page application administration routes.\n"
                     "2. **SQL Injection Authentication Bypass**: Bypass administrator authentication using SQLite injection payloads.\n"
                     "3. **DOM-Based XSS**: Perform cross-site scripting via unsanitized search reflection.\n"
                     "4. **Path Traversal & Data Exfiltration**: Exploit insecure file server directories to extract confidential documentation.\n"
                     "5. **Broken Object Authorization (IDOR)**: Manipulate user basket identifiers to access unauthorized account data.\n\n"
                     "### Launching the Lab:\n"
                     "Access the **Cyber Range Labs** catalog to provision your isolated container target."),
                ]
            ),
            (
                "Network Security",
                "Firewalls, deep packet inspection with Wireshark/tcpdump, Suricata IDS/IPS, and network micro-segmentation.",
                [
                    ("Deep Packet Inspection with Wireshark & tcpdump", LessonType.PRACTICAL, 60,
                     "# Packet Dissection with Wireshark\n\n"
                     "Filtering captured PCAP files using Berkeley Packet Filters (BPF):\n"
                     "```bash\n"
                     "tcpdump -i eth0 -nn 'tcp port 80 and (((ip[2:2] - ((ip[0]&0xf)<<2)) - ((tcp[12:1] & 0xf0)>>2)) != 0)'\n"
                     "```\n"
                     "Analyzing HTTP streams, DNS exfiltration anomalies, and plain-text credentials."),

                    ("Stateful Packet Filtering with iptables & nftables", LessonType.ARTICLE, 55,
                     "# Linux Firewall Architecture\n\n"
                     "Enforcing stateful inbound and outbound firewall rules:\n"
                     "```bash\n"
                     "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT\n"
                     "iptables -A INPUT -p tcp --dport 22 -j ACCEPT\n"
                     "iptables -P INPUT DROP\n"
                     "```\n"
                     "Default DROP policies ensure zero unauthorized services are reachable."),

                    ("Intrusion Detection & Prevention Systems (Suricata IDS)", LessonType.PRACTICAL, 65,
                     "# Writing Suricata IDS Signatures\n\n"
                     "Structure of a network intrusion detection rule:\n"
                     "```text\n"
                     "alert tcp $EXTERNAL_NET any -> $HOME_NET 80 (msg:\"EXPLOIT Web Shell Execution\"; content:\"cmd.exe\"; nocase; sid:1000001; rev:1;)\n"
                     "```"),
                ]
            ),
            (
                "Vulnerability Assessment & Penetration Testing",
                "Vulnerability management lifecycles, automated scanners, CVSS v3.1 scoring formulas, and executive reporting.",
                [
                    ("Vulnerability Lifecycle & CVSS v3.1 Scoring", LessonType.ARTICLE, 50,
                     "# CVSS v3.1 Scoring Framework\n\n"
                     "Common Vulnerability Scoring System metrics:\n"
                     "- **Base Score**: Inherent qualities of a vulnerability (Attack Vector, Complexity, Privileges Required, User Interaction, Scope, Confidentiality, Integrity, Availability).\n"
                     "- **Severity Bands**: None (0.0), Low (0.1-3.9), Medium (4.0-6.9), High (7.0-8.9), Critical (9.0-10.0)."),

                    ("Network Vulnerability Scanning & False Positive Verification", LessonType.PRACTICAL, 60,
                     "# Scanning & Manual Verification\n\n"
                     "Automated vulnerability scanners flag potential weaknesses, but false positives are rampant.\n"
                     "Ethical hackers must perform manual proof-of-concept verification without causing operational denial of service."),

                    ("Technical Findings Documentation & Remediation Reporting", LessonType.READING, 55,
                     "# Professional Pen Testing Reporting\n\n"
                     "An actionable pentest report must contain:\n"
                     "1. Executive Summary (High-level business risk overview).\n"
                     "2. Technical Findings with CVSS scores and reproduction steps.\n"
                     "3. Root Cause Analysis.\n"
                     "4. Short-term and Long-term Strategic Remediation Guidance."),
                ]
            ),
            (
                "SOC, SIEM & Incident Response",
                "SOC operations, log aggregation with Wazuh SIEM, alert correlation, MITRE ATT&CK mapping, and containment.",
                [
                    ("SOC Operations, Tiered Escalation & MITRE ATT&CK", LessonType.ARTICLE, 50,
                     "# SOC Architecture & Escalation\n\n"
                     "- **Tier 1 (Triage Analyst)**: Monitors SIEM dashboards, filters false positives, escalates valid incidents.\n"
                     "- **Tier 2 (Incident Responder)**: Conducts deep host and network forensic investigation, executes containment.\n"
                     "- **Tier 3 (Threat Hunter)**: Proactively searches for stealthy adversaries using MITRE ATT&CK tactics."),

                    ("SIEM Log Ingestion, Normalization & Wazuh Deployment", LessonType.PRACTICAL, 65,
                     "# Wazuh SIEM Telemetry Ingestion\n\n"
                     "Wazuh agents aggregate endpoint events across Windows Event Logs, Linux Syslog, and auditd.\n"
                     "Events are parsed via decoders and matched against XML correlation rules to trigger high-priority alerts."),

                    ("Incident Response: Containment, Eradication & Post-Mortem", LessonType.ARTICLE, 55,
                     "# The NIST Incident Response Lifecycle\n\n"
                     "1. **Preparation**: Hardening and telemetry readiness.\n"
                     "2. **Detection & Analysis**: Identifying active indicators of compromise (IOCs).\n"
                     "3. **Containment, Eradication & Recovery**: Isolating compromised endpoints, purging malware, restoring from clean backups.\n"
                     "4. **Post-Incident Activity**: Lessons learned and policy refinement."),
                ]
            ),
            (
                "Digital Forensics & Malware Fundamentals",
                "Chain of custody, forensic file carving, memory triage with Volatility, and static malware analysis.",
                [
                    ("Digital Evidence Handling & Cryptographic Chain of Custody", LessonType.ARTICLE, 45,
                     "# Forensic Evidence Preservation\n\n"
                     "Legal admissibility of digital evidence mandates:\n"
                     "- Write-blocker hardware when imaging drives.\n"
                     "- Cryptographic hashes (SHA-256) calculated immediately before and after imaging.\n"
                     "- Meticulous chain-of-custody documentation tracking every handler."),

                    ("Volatile Memory Analysis with Volatility Framework", LessonType.PRACTICAL, 65,
                     "# Volatility Memory Forensics\n\n"
                     "RAM contains unencrypted credentials, injected code, and terminated network sockets:\n"
                     "- `windows.pslist`: Display running processes.\n"
                     "- `windows.malfind`: Detect injected shellcode and hidden DLLs.\n"
                     "- `windows.netscan`: Extract established network sockets."),

                    ("Static Malware Triage: Hashes, Strings & PE Headers", LessonType.PRACTICAL, 60,
                     "# Static Malware Analysis\n\n"
                     "Safely analyzing portable executable (PE) binaries without execution:\n"
                     "- Querying hash signatures on VirusTotal.\n"
                     "- Extracting ASCII/Unicode strings for C2 domains or embedded commands.\n"
                     "- Inspecting PE Import Address Tables (IAT) for suspicious APIs (`VirtualAllocEx`, `WriteProcessMemory`)."),
                ]
            ),
            (
                "Python for Cyber Security",
                "Python automation, socket programming, regex log triage, and threat intelligence API scripting.",
                [
                    ("Python Fundamentals for Security Practitioners", LessonType.ARTICLE, 45,
                     "# Python for Security Automation\n\n"
                     "Python excels at rapid automation, socket manipulation, and log parsing.\n"
                     "Security engineers utilize Python's standard library (`sys`, `os`, `socket`, `re`, `json`) to construct custom tools."),

                    ("Network Socket Programming: Port Scanners & Banner Grabbers", LessonType.PRACTICAL, 65,
                     "# Custom TCP Port Scanner with Python\n\n"
                     "```python\n"
                     "import socket\n\n"
                     "def scan_port(host, port):\n"
                     "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                     "    s.settimeout(1.0)\n"
                     "    try:\n"
                     "        s.connect((host, port))\n"
                     "        banner = s.recv(1024).decode().strip()\n"
                     "        print(f'[+] Port {port} OPEN | Banner: {banner}')\n"
                     "    except:\n"
                     "        pass\n"
                     "    finally:\n"
                     "        s.close()\n"
                     "```"),

                    ("Log Parsing Automation with Regular Expressions", LessonType.PRACTICAL, 60,
                     "# Automated Web Log Triage\n\n"
                     "Parsing Apache access logs for SQL injection and directory traversal attacks:\n"
                     "```python\n"
                     "import re\n\n"
                     "pattern = re.compile(r'(\\d+\\.\\d+\\.\\d+\\.\\d+).*\"(GET|POST)\\s+([^\\s]+)')\n"
                     "# Match and flag suspicious characters like ../, <script>, or UNION SELECT\n"
                     "```"),
                ]
            ),
            (
                "Cloud Security, DevSecOps & Modern Cyber Security",
                "Cloud shared responsibility, AWS/GCP IAM least privilege, container security, Docker benchmarking, and CI/CD SAST/DAST.",
                [
                    ("Cloud Shared Responsibility & IAM Least Privilege", LessonType.ARTICLE, 50,
                     "# Cloud Security & IAM Architecture\n\n"
                     "- **IaaS**: Customer manages OS, runtime, and data; Cloud provider manages physical hardware.\n"
                     "- **PaaS**: Provider manages runtime; Customer manages code and configurations.\n"
                     "- **Principle of Least Privilege (PoLP)**: Granting only the exact permissions needed to execute a role."),

                    ("Container Hardening: Docker Benchmarking & Isolation", LessonType.PRACTICAL, 65,
                     "# Docker Container Security\n\n"
                     "Preventing container breakout:\n"
                     "- Never run container processes as root (`USER nonroot`).\n"
                     "- Mount root filesystem as read-only (`--read-only`).\n"
                     "- Drop all Linux capabilities (`--cap-drop=ALL`).\n"
                     "- Never mount the Docker socket (`/var/run/docker.sock`) into unprivileged containers."),

                    ("DevSecOps: Integrating SAST & DAST into CI/CD Pipelines", LessonType.PRACTICAL, 60,
                     "# DevSecOps & Shift-Left Security\n\n"
                     "Automating security testing during the code integration and build phases:\n"
                     "- **SAST (Static Application Security Testing)**: Scans source code for vulnerabilities.\n"
                     "- **SCA (Software Composition Analysis)**: Detects outdated third-party libraries with known CVEs.\n"
                     "- **DAST (Dynamic Application Security Testing)**: Tests running applications from an outside perspective."),
                ]
            ),
            (
                "Integrated Cyber Security Laboratory & Capstone",
                "Holistic enterprise attack and defense simulation, risk analysis, remediation report, and live Viva Voce defense.",
                [
                    ("Capstone Scope Definition & Enterprise Attack Path Planning", LessonType.ARTICLE, 60,
                     "# Capstone Proposal & Scope Definition\n\n"
                     "In the final capstone, students design an end-to-end corporate network simulation combining:\n"
                     "- External web perimeter attack surface.\n"
                     "- Internal Windows Active Directory domain controller.\n"
                     "- Centralized Wazuh SIEM detection pipeline.\n\n"
                     "Deliverable: Formal Capstone Proposal with architecture diagrams."),

                    ("Enterprise Security Assessment & Remediation Engineering", LessonType.PRACTICAL, 120,
                     "# Enterprise Assessment & Defense Implementation\n\n"
                     "Students execute full technical vulnerability assessments against authorized lab environments, "
                     "documenting proof-of-concept evidence and engineering production-ready hardening remediation steps."),

                    ("Executive Audit Report & Live Viva Voce Examination", LessonType.QUIZ, 90,
                     "# Capstone Defense & Viva Voce\n\n"
                     "Students present their findings before an examination faculty board:\n"
                     "1. Demonstration of technical remediation.\n"
                     "2. Explanation of architectural defense strategies.\n"
                     "3. Response to oral examination probing questions."),
                ]
            )
        ]

        total_modules_created = 0
        total_lessons_created = 0

        for order, (mod_title, mod_desc, lessons_data) in enumerate(modules_curriculum, start=1):
            mod_slug = slugify(f"module-{order}-{mod_title}")[:50]
            module, _ = CourseModule.objects.get_or_create(
                course=course,
                order=order,
                defaults={
                    'title': f"Module {order}: {mod_title}",
                    'slug': mod_slug,
                    'description': mod_desc,
                    'estimated_hours': 25,
                    'is_published': True,
                    'learning_objectives': [
                        f"Master theoretical concepts of {mod_title}",
                        f"Apply defensive architectures and hardening for {mod_title}",
                        f"Conduct hands-on validation and troubleshooting"
                    ]
                }
            )
            total_modules_created += 1

            for l_order, (l_title, l_type, l_minutes, l_content) in enumerate(lessons_data, start=1):
                l_slug = slugify(f"m{order}-l{l_order}-{l_title}")[:50]
                Lesson.objects.get_or_create(
                    module=module,
                    order=l_order,
                    defaults={
                        'title': l_title,
                        'slug': l_slug,
                        'lesson_type': l_type,
                        'content': l_content,
                        'estimated_minutes': l_minutes,
                        'is_published': True,
                    }
                )
                total_lessons_created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {total_modules_created} Modules and {total_lessons_created} Lessons in {course.title}."))

        # ==============================================================================
        # 6. Additional Course: Python Programming: Zero to Mastery & Secure Automation
        # ==============================================================================
        py_course, _ = Course.objects.get_or_create(
            slug="python-zero-to-mastery",
            defaults={
                'title': 'Python Programming: Zero to Mastery & Automation',
                'short_description': 'Master Python from fundamentals to OOP, socket programming, and automated security tooling.',
                'description': (
                    "### Course Overview\n\n"
                    "This comprehensive program trains students in Python programming with real-world practical applications. "
                    "You will build strong computer science fundamentals, master object-oriented design, manipulate structured data, "
                    "and build network tools and automation scripts.\n\n"
                    "### Who is this course for?\n"
                    "- Beginners with zero prior programming experience.\n"
                    "- IT and cybersecurity students requiring automation and scripting skills.\n"
                    "- Software engineers moving into systems engineering and DevOps."
                ),
                'level': CourseLevel.BEGINNER,
                'duration': '3 Months',
                'language': 'English',
                'price': 0.00,
                'is_free': True,
                'status': CourseStatus.ARCHIVED,
                'created_by': ins1,
            }
        )
        py_course.status = CourseStatus.ARCHIVED
        py_course.save()
        py_course.categories.add(cat_objs.get('python'), cat_objs.get('devsecops'))

        py_modules = [
            (
                "Python Syntax & Core Fundamentals",
                "Variables, memory model, standard data types, operators, and conditional logic.",
                [
                    ("Introduction to Python & Development Environment", LessonType.ARTICLE, 30,
                     "# Introduction to Python 3\n\n"
                     "Python is a high-level, interpreted, general-purpose programming language emphasizing code readability.\n\n"
                     "```python\nprint('Hello, Future Tech Academy!')\n```\n\n"
                     "### Key Characteristics:\n"
                     "- Dynamically typed\n"
                     "- Automatic memory management (Garbage collection)\n"
                     "- Rich standard library ('Batteries included')"),
                    ("Control Flow & Conditionals", LessonType.ARTICLE, 40,
                     "# Conditional Statements\n\n"
                     "Controlling program execution flow using `if`, `elif`, and `else` blocks with boolean logic."),
                    ("Loops and Iteration", LessonType.PRACTICAL, 45,
                     "# For & While Loops\n\n"
                     "Iterating over sequences with `range()`, `enumerate()`, and list comprehensions."),
                ]
            ),
            (
                "Data Structures & Functions",
                "Lists, dictionaries, sets, tuples, and functional programming concepts.",
                [
                    ("Working with Lists and Tuples", LessonType.ARTICLE, 40,
                     "# Python Sequences\n\n"
                     "Understanding indexing, slicing, mutable lists vs immutable tuples."),
                    ("Dictionaries and Hash Maps", LessonType.ARTICLE, 40,
                     "# Key-Value Mappings\n\n"
                     "Fast lookup structures using Python dictionaries and set operations."),
                    ("Functions, Scope & Lambdas", LessonType.PRACTICAL, 50,
                     "# Writing Modular Functions\n\n"
                     "Defining reusable functions with `*args`, `**kwargs`, and type hints."),
                ]
            ),
            (
                "Object-Oriented Programming (OOP) & Error Handling",
                "Classes, inheritance, encapsulation, polymorphism, and robust exception handling.",
                [
                    ("Classes, Instances & Attributes", LessonType.ARTICLE, 45,
                     "# OOP in Python\n\n"
                     "Designing real-world models using class definitions and the `__init__` constructor."),
                    ("Inheritance & Polymorphism", LessonType.ARTICLE, 45,
                     "# Class Hierarchies\n\n"
                     "Extending base classes, method overriding, and `super()` calls."),
                    ("Exception Handling & Clean Code", LessonType.PRACTICAL, 45,
                     "# Try, Except, Finally\n\n"
                     "Handling runtime exceptions gracefully to ensure application resilience."),
                ]
            ),
            (
                "Network Scripting & Systems Automation",
                "Socket programming, HTTP requests, file parsing, and building CLI tools.",
                [
                    ("File I/O and JSON Data Processing", LessonType.ARTICLE, 45,
                     "# File Operations\n\n"
                     "Reading and writing CSV, JSON, and text files using context managers (`with open`)."),
                    ("Working with REST APIs and HTTP Requests", LessonType.PRACTICAL, 60,
                     "# The `requests` Library\n\n"
                     "Making GET and POST requests, handling headers, and parsing JSON payloads."),
                    ("Building a Port Scanner with Sockets", LessonType.PRACTICAL, 60,
                     "# Raw Socket Programming\n\n"
                     "Creating network connections using Python's built-in `socket` module."),
                ]
            ),
        ]

        for mod_idx, (m_title, m_desc, m_lessons) in enumerate(py_modules, start=1):
            m_slug = slugify(f"py-mod-{mod_idx}-{m_title}")[:50]
            pmod, _ = CourseModule.objects.get_or_create(
                course=py_course,
                order=mod_idx,
                defaults={
                    'title': f"Module {mod_idx}: {m_title}",
                    'slug': m_slug,
                    'description': m_desc,
                    'estimated_hours': 20,
                    'is_published': True,
                }
            )
            for l_idx, (ltitle, ltype, lmin, lcont) in enumerate(m_lessons, start=1):
                lslug = slugify(f"py-m{mod_idx}-l{l_idx}-{ltitle}")[:50]
                Lesson.objects.get_or_create(
                    module=pmod,
                    order=l_idx,
                    defaults={
                        'title': ltitle,
                        'slug': lslug,
                        'lesson_type': ltype,
                        'content': lcont,
                        'estimated_minutes': lmin,
                        'is_published': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Created {py_course.title}."))

        # ==============================================================================
        # 7. Additional Course: Linux System Administration & Shell Scripting
        # ==============================================================================
        linux_course, _ = Course.objects.get_or_create(
            slug="linux-system-administration",
            defaults={
                'title': 'Linux System Administration & Shell Scripting',
                'short_description': 'Enterprise Linux administration, systemd service management, LVM, and Bash automation.',
                'description': (
                    "### Course Overview\n\n"
                    "Linux powers over 90% of global cloud infrastructure and enterprise servers. This course covers everything from "
                    "terminal command-line proficiency and user/group administration to systemd services, LVM storage, and automated Bash scripts."
                ),
                'level': CourseLevel.BEGINNER,
                'duration': '2 Months',
                'language': 'English',
                'price': 0.00,
                'is_free': True,
                'status': CourseStatus.ARCHIVED,
                'created_by': ins2,
            }
        )
        linux_course.status = CourseStatus.ARCHIVED
        linux_course.save()
        linux_course.categories.add(cat_objs.get('linux'), cat_objs.get('networking'))

        linux_modules = [
            (
                "Linux Command Line & Filesystem Hierarchy",
                "Navigating POSIX environments, standard streams, and file manipulation.",
                [
                    ("Filesystem Hierarchy Standard (FHS)", LessonType.ARTICLE, 30,
                     "# Understanding the Linux FHS\n\n"
                     "Exploring `/bin`, `/etc`, `/var`, `/proc`, `/sys`, and `/home`."),
                    ("Core Command Utilities", LessonType.PRACTICAL, 40,
                     "# Navigation & Inspection\n\n"
                     "Mastering `grep`, `sed`, `awk`, `find`, `cut`, and `sort`."),
                    ("Pipes, Redirection and Text Streams", LessonType.ARTICLE, 35,
                     "# Standard Streams\n\n"
                     "Redirecting stdin (0), stdout (1), and stderr (2) with `|`, `>`, and `2>&1`."),
                ]
            ),
            (
                "Users, Permissions & Process Control",
                "Linux security model, POSIX permissions, ACLs, and process lifecycle.",
                [
                    ("Linux Permissions Model & Ownership", LessonType.ARTICLE, 40,
                     "# chmod and chown\n\n"
                     "Octal and symbolic permissions, umask defaults, and special bits (SUID, SGID, Sticky)."),
                    ("Process Inspection and Management", LessonType.PRACTICAL, 45,
                     "# Managing Processes\n\n"
                     "Using `ps`, `top`, `htop`, `kill`, `nice`, and signals."),
                    ("Storage Management & LVM", LessonType.ARTICLE, 45,
                     "# Logical Volume Management\n\n"
                     "Physical Volumes (PV), Volume Groups (VG), and Logical Volumes (LV)."),
                ]
            ),
            (
                "Bash Scripting & Infrastructure Automation",
                "Writing professional shell scripts with error handling and automation cron jobs.",
                [
                    ("Bash Script Fundamentals", LessonType.ARTICLE, 45,
                     "# Writing Shell Scripts\n\n"
                     "Shebang `#!/usr/bin/env bash`, variables, exit codes (`$?`), and arguments."),
                    ("Conditional Statements and Loops in Bash", LessonType.PRACTICAL, 50,
                     "# Logic in Bash\n\n"
                     "Using `[[ ... ]]`, `for in`, `while`, and `case` statements."),
                    ("Cron Scheduling & Maintenance Automation", LessonType.PRACTICAL, 45,
                     "# Automating Tasks\n\n"
                     "Configuring `/etc/crontab` and `crontab -e` for automated backups and healthchecks."),
                ]
            ),
        ]

        for mod_idx, (m_title, m_desc, m_lessons) in enumerate(linux_modules, start=1):
            m_slug = slugify(f"linux-mod-{mod_idx}-{m_title}")[:50]
            lmod, _ = CourseModule.objects.get_or_create(
                course=linux_course,
                order=mod_idx,
                defaults={
                    'title': f"Module {mod_idx}: {m_title}",
                    'slug': m_slug,
                    'description': m_desc,
                    'estimated_hours': 15,
                    'is_published': True,
                }
            )
            for l_idx, (ltitle, ltype, lmin, lcont) in enumerate(m_lessons, start=1):
                lslug = slugify(f"linux-m{mod_idx}-l{l_idx}-{ltitle}")[:50]
                Lesson.objects.get_or_create(
                    module=lmod,
                    order=l_idx,
                    defaults={
                        'title': ltitle,
                        'slug': lslug,
                        'lesson_type': ltype,
                        'content': lcont,
                        'estimated_minutes': lmin,
                        'is_published': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Created {linux_course.title}."))

        # ==============================================================================
        # 8. Additional Course: Computer Networking & TCP/IP Architecture
        # ==============================================================================
        net_course, _ = Course.objects.get_or_create(
            slug="computer-networking-tcpip",
            defaults={
                'title': 'Computer Networking & TCP/IP Architecture',
                'short_description': 'In-depth study of computer networks, OSI reference model, IP subnetting, and packet capture analysis.',
                'description': (
                    "### Course Overview\n\n"
                    "Networking is the backbone of all modern computing and cybersecurity. This course guides students through "
                    "physical cabling, Ethernet switching, IPv4/IPv6 subnetting, transport layer reliability, and core application protocols."
                ),
                'level': CourseLevel.BEGINNER,
                'duration': '2 Months',
                'language': 'English',
                'price': 0.00,
                'is_free': True,
                'status': CourseStatus.ARCHIVED,
                'created_by': ins1,
            }
        )
        net_course.status = CourseStatus.ARCHIVED
        net_course.save()
        net_course.categories.add(cat_objs.get('networking'), cat_objs.get('cyber-security'))

        net_modules = [
            (
                "Network Models & Protocols",
                "OSI 7-layer reference model vs TCP/IP 4-layer architecture.",
                [
                    ("The OSI 7-Layer Model Explained", LessonType.ARTICLE, 35,
                     "# The OSI Reference Model\n\n"
                     "Layer 1 Physical to Layer 7 Application with encapsulation headers."),
                    ("Ethernet, MAC Addresses & ARP", LessonType.ARTICLE, 40,
                     "# Data Link Layer\n\n"
                     "Frame structure, hardware addresses, and Address Resolution Protocol."),
                    ("Wireshark Packet Capture Basics", LessonType.PRACTICAL, 50,
                     "# Hands-on Packet Capture\n\n"
                     "Capturing real network traffic and applying display filters."),
                ]
            ),
            (
                "IP Addressing & Subnetting",
                "Mastering binary arithmetic, IPv4 classless addressing (CIDR), and VLSM.",
                [
                    ("IPv4 Structure & Binary Conversion", LessonType.ARTICLE, 40,
                     "# IPv4 Addressing\n\n"
                     "32-bit addresses, network vs host bits, and subnet masks."),
                    ("CIDR Subnetting Calculations", LessonType.PRACTICAL, 60,
                     "# Calculating Subnets\n\n"
                     "Step-by-step methodology for /24, /26, /28, and /30 networks."),
                    ("IPv6 Architecture & Transition", LessonType.ARTICLE, 35,
                     "# Next-Gen IP\n\n"
                     "128-bit hex notation, link-local addresses, and dual-stack operations."),
                ]
            ),
            (
                "Transport & Application Protocols",
                "TCP reliability, UDP speed, DNS resolution, and TLS encryption.",
                [
                    ("TCP vs UDP Transmission", LessonType.ARTICLE, 40,
                     "# Transport Layer\n\n"
                     "Three-way handshakes (SYN, SYN-ACK, ACK), sequence numbers, and port multiplexing."),
                    ("DNS Architecture & Resolution", LessonType.ARTICLE, 45,
                     "# Domain Name System\n\n"
                     "Root nameservers, TLDs, authoritative zones, and DNS record types (A, AAAA, MX, CNAME)."),
                    ("HTTP, HTTPS and TLS Handshakes", LessonType.PRACTICAL, 50,
                     "# Secure Web Protocols\n\n"
                     "Certificates, asymmetric key exchange, and symmetric data encryption."),
                ]
            ),
        ]

        for mod_idx, (m_title, m_desc, m_lessons) in enumerate(net_modules, start=1):
            m_slug = slugify(f"net-mod-{mod_idx}-{m_title}")[:50]
            nmod, _ = CourseModule.objects.get_or_create(
                course=net_course,
                order=mod_idx,
                defaults={
                    'title': f"Module {mod_idx}: {m_title}",
                    'slug': m_slug,
                    'description': m_desc,
                    'estimated_hours': 15,
                    'is_published': True,
                }
            )
            for l_idx, (ltitle, ltype, lmin, lcont) in enumerate(m_lessons, start=1):
                lslug = slugify(f"net-m{mod_idx}-l{l_idx}-{ltitle}")[:50]
                Lesson.objects.get_or_create(
                    module=nmod,
                    order=l_idx,
                    defaults={
                        'title': ltitle,
                        'slug': lslug,
                        'lesson_type': ltype,
                        'content': lcont,
                        'estimated_minutes': lmin,
                        'is_published': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Created {net_course.title}."))

        # ==============================================================================
        # 9. Assessment Weights (Grading formulas per course)
        # ==============================================================================
        for c in [course, linux_course, net_course]:
            AssessmentWeight.objects.get_or_create(
                course=c,
                defaults={
                    'assignments_weight': Decimal('10.00'),
                    'quizzes_weight': Decimal('10.00'),
                    'labs_weight': Decimal('25.00'),
                    'module_exams_weight': Decimal('20.00'),
                    'practical_exam_weight': Decimal('15.00'),
                    'final_project_weight': Decimal('20.00'),
                }
            )
        self.stdout.write(self.style.SUCCESS("Seeded Assessment Weights."))

        # ==============================================================================
        # 10. Question Bank
        # ==============================================================================
        qb_data = [
            ("Explain the primary objective of Confidentiality in the CIA triad", "Cybersecurity", QuestionDifficulty.EASY),
            ("Identify all mechanisms used to guarantee data Integrity", "Cybersecurity", QuestionDifficulty.MEDIUM),
            ("What is the primary role of Linux PAM (Pluggable Authentication Modules)?", "Linux", QuestionDifficulty.MEDIUM),
            ("Which TCP control flag initiates the three-way handshake?", "Networking", QuestionDifficulty.EASY),
            ("Analyze the SQL Injection attack vector and remediation strategies", "Web Security", QuestionDifficulty.HARD),
            ("Distinguish between False Positive and True Positive alerts in a SIEM", "SOC & SIEM", QuestionDifficulty.EASY),
        ]
        q_banks = {}
        for qb_title, qb_cat, qb_diff in qb_data:
            qb, _ = QuestionBank.objects.get_or_create(
                title=qb_title,
                category=qb_cat,
                defaults={
                    'difficulty': qb_diff,
                    'created_by': ins1,
                }
            )
            q_banks[qb_title] = qb
        self.stdout.write(self.style.SUCCESS("Seeded Question Bank."))

        # ==============================================================================
        # 11. Quizzes & Questions
        # ==============================================================================
        mod1 = course.modules.order_by('order').first()
        quiz1, _ = Quiz.objects.get_or_create(
            course=course,
            title="Cyber Security Fundamentals Quiz",
            defaults={
                'lesson': mod1.lessons.first() if mod1 else None,
                'description': "Evaluates understanding of CIA triad, threat modeling, attack surfaces, and defensive primitives.",
                'time_limit_minutes': 15,
                'passing_score': 70,
                'max_attempts': 3,
                'randomize_questions': True,
                'is_published': True,
            }
        )
        if quiz1.questions.count() == 0:
            q1 = Question.objects.create(
                quiz=quiz1,
                order=1,
                question_text="Which pillar of the CIA Triad is primarily protected by SHA-256 cryptographic hashing?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                points=Decimal('2.50'),
                explanation="Cryptographic hash functions generate deterministic digests to detect unauthorized data modification, directly assuring data Integrity."
            )
            QuestionOption.objects.create(question=q1, option_text="Integrity", is_correct=True, order=1)
            QuestionOption.objects.create(question=q1, option_text="Confidentiality", is_correct=False, order=2)
            QuestionOption.objects.create(question=q1, option_text="Availability", is_correct=False, order=3)
            QuestionOption.objects.create(question=q1, option_text="Non-repudiation", is_correct=False, order=4)

            q2 = Question.objects.create(
                quiz=quiz1,
                order=2,
                question_text="Select all defensive controls that directly mitigate credential stuffing attacks:",
                question_type=QuestionType.MULTIPLE_SELECT,
                points=Decimal('2.50'),
                explanation="MFA, strict IP rate limiting, and breached-credential detection directly stop automated credential replay attacks."
            )
            QuestionOption.objects.create(question=q2, option_text="Multi-Factor Authentication (MFA)", is_correct=True, order=1)
            QuestionOption.objects.create(question=q2, option_text="Rate limiting on authentication endpoints", is_correct=True, order=2)
            QuestionOption.objects.create(question=q2, option_text="Upgrading database RAM", is_correct=False, order=3)
            QuestionOption.objects.create(question=q2, option_text="Enforcing breached-password database checks", is_correct=True, order=4)

            q3 = Question.objects.create(
                quiz=quiz1,
                order=3,
                question_text="A threat actor can exploit an organizational asset even if no technical vulnerability exists.",
                question_type=QuestionType.TRUE_FALSE,
                points=Decimal('2.50'),
                explanation="Without a vulnerability (flaw or misconfiguration), an exploitation cannot occur according to standard risk calculation (Risk = Threat x Vulnerability x Impact)."
            )
            QuestionOption.objects.create(question=q3, option_text="True", is_correct=False, order=1)
            QuestionOption.objects.create(question=q3, option_text="False", is_correct=True, order=2)

            q4 = Question.objects.create(
                quiz=quiz1,
                order=4,
                question_text="What standard three-variable formula is used in threat modeling to calculate organizational risk?",
                question_type=QuestionType.SHORT_ANSWER,
                points=Decimal('2.50'),
                explanation="Standard threat modeling dictates Risk = Threat x Vulnerability x Impact."
            )
            QuestionOption.objects.create(question=q4, option_text="Threat x Vulnerability x Impact", is_correct=True, order=1)

        lmod1 = linux_course.modules.order_by('order').first()
        quiz_linux, _ = Quiz.objects.get_or_create(
            course=linux_course,
            title="Linux Core Security & Permissions Quiz",
            defaults={
                'lesson': lmod1.lessons.first() if lmod1 else None,
                'description': "Assess knowledge of Linux permissions, SUID binaries, and system account security.",
                'time_limit_minutes': 15,
                'passing_score': 70,
                'max_attempts': 3,
                'is_published': True,
            }
        )
        if quiz_linux.questions.count() == 0:
            lq1 = Question.objects.create(
                quiz=quiz_linux, order=1,
                question_text="Which numeric chmod permission gives Read/Write/Execute to Owner, Read/Execute to Group, and Read-only to Others?",
                question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('3.00'),
                explanation="7 (rwx) for owner, 5 (r-x) for group, 4 (r--) for others = 754."
            )
            QuestionOption.objects.create(question=lq1, option_text="754", is_correct=True, order=1)
            QuestionOption.objects.create(question=lq1, option_text="755", is_correct=False, order=2)
            QuestionOption.objects.create(question=lq1, option_text="644", is_correct=False, order=3)
            QuestionOption.objects.create(question=lq1, option_text="700", is_correct=False, order=4)

            lq2 = Question.objects.create(
                quiz=quiz_linux, order=2,
                question_text="A SUID executable runs with the permissions of the file owner rather than the user executing it.",
                question_type=QuestionType.TRUE_FALSE, points=Decimal('3.00'),
                explanation="SUID (Set Owner User ID) grants the executing process the privileges of the file owner."
            )
            QuestionOption.objects.create(question=lq2, option_text="True", is_correct=True, order=1)
            QuestionOption.objects.create(question=lq2, option_text="False", is_correct=False, order=2)

            lq3 = Question.objects.create(
                quiz=quiz_linux, order=3,
                question_text="Which files store user account definitions and salted password hashes respectively on modern Linux?",
                question_type=QuestionType.MULTIPLE_SELECT, points=Decimal('4.00'),
                explanation="/etc/passwd contains account configurations while /etc/shadow holds protected shadow password hashes."
            )
            QuestionOption.objects.create(question=lq3, option_text="/etc/passwd", is_correct=True, order=1)
            QuestionOption.objects.create(question=lq3, option_text="/etc/shadow", is_correct=True, order=2)
            QuestionOption.objects.create(question=lq3, option_text="/etc/hosts", is_correct=False, order=3)
            QuestionOption.objects.create(question=lq3, option_text="/etc/sudoers", is_correct=False, order=4)

        nmod1 = net_course.modules.order_by('order').first()
        quiz_net, _ = Quiz.objects.get_or_create(
            course=net_course,
            title="TCP/IP Protocol Architecture Quiz",
            defaults={
                'lesson': nmod1.lessons.first() if nmod1 else None,
                'description': "Validates understanding of TCP/IP handshakes, CIDR subnetting, and transport protocols.",
                'time_limit_minutes': 15,
                'passing_score': 70,
                'max_attempts': 3,
                'is_published': True,
            }
        )
        if quiz_net.questions.count() == 0:
            nq1 = Question.objects.create(
                quiz=quiz_net, order=1,
                question_text="In the TCP 3-way handshake, what packet flag sequence is sent by the server in response to the initial SYN?",
                question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('3.00'),
                explanation="Client sends SYN -> Server responds SYN-ACK -> Client completes with ACK."
            )
            QuestionOption.objects.create(question=nq1, option_text="SYN-ACK", is_correct=True, order=1)
            QuestionOption.objects.create(question=nq1, option_text="ACK", is_correct=False, order=2)
            QuestionOption.objects.create(question=nq1, option_text="SYN", is_correct=False, order=3)
            QuestionOption.objects.create(question=nq1, option_text="RST", is_correct=False, order=4)

            nq2 = Question.objects.create(
                quiz=quiz_net, order=2,
                question_text="How many usable host addresses exist in an IPv4 /28 subnet?",
                question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('3.00'),
                explanation="A /28 subnet has 32 - 28 = 4 host bits (2^4 = 16 total). Subtracting network and broadcast yields 14 usable hosts."
            )
            QuestionOption.objects.create(question=nq2, option_text="14", is_correct=True, order=1)
            QuestionOption.objects.create(question=nq2, option_text="16", is_correct=False, order=2)
            QuestionOption.objects.create(question=nq2, option_text="30", is_correct=False, order=3)
            QuestionOption.objects.create(question=nq2, option_text="12", is_correct=False, order=4)

            nq3 = Question.objects.create(
                quiz=quiz_net, order=3,
                question_text="UDP provides built-in congestion control, flow control, and guaranteed ordered packet delivery.",
                question_type=QuestionType.TRUE_FALSE, points=Decimal('4.00'),
                explanation="UDP is a connectionless, best-effort datagram service without flow control or delivery guarantees."
            )
            QuestionOption.objects.create(question=nq3, option_text="True", is_correct=False, order=1)
            QuestionOption.objects.create(question=nq3, option_text="False", is_correct=True, order=2)

        self.stdout.write(self.style.SUCCESS("Seeded Quizzes and Questions."))

        # ==============================================================================
        # 12. Assignments
        # ==============================================================================
        assign1, _ = Assignment.objects.get_or_create(
            course=course,
            title="Threat Modeling & Attack Surface Report",
            defaults={
                'module': mod1,
                'description': "Perform a complete STRIDE threat model on a multi-tier banking web application.",
                'instructions': (
                    "### Assignment Objectives\n\n"
                    "1. Deconstruct the architecture into Data Flow Diagrams (DFD Level 1).\n"
                    "2. Enumerate STRIDE threat vectors against all communication channels.\n"
                    "3. Calculate DREAD risk scores for top 5 vulnerabilities.\n"
                    "4. Propose actionable cryptographic and architectural mitigations.\n\n"
                    "### Deliverable:\n"
                    "Submit a formal PDF document (max 25MB). Ensure all diagrams and risk matrices are legible."
                ),
                'due_date': timezone.now() + timezone.timedelta(days=14),
                'max_score': Decimal('100.00'),
                'allowed_file_types': ['pdf', 'zip'],
                'max_file_size_mb': 25,
                'status': 'PUBLISHED',
            }
        )

        assign_linux, _ = Assignment.objects.get_or_create(
            course=linux_course,
            title="Linux Server Hardening Audit & Script Submission",
            defaults={
                'module': lmod1,
                'description': "Develop an automated Bash hardening script conforming to CIS Benchmark baselines.",
                'instructions': (
                    "### Assignment Objectives\n\n"
                    "1. Write a shell script that disables unused services, tightens SSH configs, and enforces password complexity.\n"
                    "2. Implement automated auditd logging for sensitive configuration files.\n"
                    "3. Package script and verification log in a zip archive or upload your report."
                ),
                'due_date': timezone.now() + timezone.timedelta(days=21),
                'max_score': Decimal('100.00'),
                'allowed_file_types': ['pdf', 'zip'],
                'max_file_size_mb': 20,
                'status': 'PUBLISHED',
            }
        )

        assign_net, _ = Assignment.objects.get_or_create(
            course=net_course,
            title="Wireshark Packet Trace & Traffic Analysis",
            defaults={
                'module': nmod1,
                'description': "Analyze a pcap capture file of a simulated corporate network security breach.",
                'instructions': (
                    "### Assignment Objectives\n\n"
                    "1. Isolate DNS exfiltration queries using Wireshark display filters.\n"
                    "2. Identify cleartext credentials transmitted over legacy protocols.\n"
                    "3. Document attack timeline and compromised host IP addresses in a PDF report."
                ),
                'due_date': timezone.now() + timezone.timedelta(days=10),
                'max_score': Decimal('100.00'),
                'allowed_file_types': ['pdf', 'zip'],
                'max_file_size_mb': 25,
                'status': 'PUBLISHED',
            }
        )
        self.stdout.write(self.style.SUCCESS("Seeded Assignments."))

        # ==============================================================================
        # 13. Exams & Practical Lab Tasks (Phase 3 readiness)
        # ==============================================================================
        exam_midterm, _ = Exam.objects.get_or_create(
            course=course,
            title="Cyber Defense Midterm Examination",
            defaults={
                'exam_type': ExamType.MIDTERM,
                'description': "Midterm examination evaluating foundational knowledge across Modules 1 through 7.",
                'duration_minutes': 60,
                'passing_score': 70,
                'max_attempts': 1,
                'randomize_questions': True,
                'is_published': True,
            }
        )
        if exam_midterm.questions.count() == 0:
            eq1 = ExamQuestion.objects.create(
                exam=exam_midterm, order=1,
                question_text="Which defense-in-depth security layer is most effective against zero-day endpoint exploits?",
                question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('10.00'),
                explanation="Behavioral EDR and application whitelisting detect anomalous execution patterns independent of signatures."
            )
            ExamOption.objects.create(question=eq1, option_text="Behavioral Endpoint Detection and Response (EDR)", is_correct=True, order=1)
            ExamOption.objects.create(question=eq1, option_text="Legacy Signature-based Antivirus", is_correct=False, order=2)
            ExamOption.objects.create(question=eq1, option_text="Static Packet Filtering Firewall", is_correct=False, order=3)
            ExamOption.objects.create(question=eq1, option_text="DNS Sinkholing alone", is_correct=False, order=4)

            eq2 = ExamQuestion.objects.create(
                exam=exam_midterm, order=2,
                question_text="Select all protocols that transmit credentials in unencrypted plaintext by default:",
                question_type=QuestionType.MULTIPLE_SELECT, points=Decimal('10.00'),
                explanation="Telnet, HTTP, and FTP transmit credentials in plaintext across the network."
            )
            ExamOption.objects.create(question=eq2, option_text="Telnet", is_correct=True, order=1)
            ExamOption.objects.create(question=eq2, option_text="HTTP", is_correct=True, order=2)
            ExamOption.objects.create(question=eq2, option_text="FTP", is_correct=True, order=3)
            ExamOption.objects.create(question=eq2, option_text="SSHv2", is_correct=False, order=4)

        exam_practical, _ = Exam.objects.get_or_create(
            course=course,
            title="Simulated Incident Response & Forensic Triage Practical Exam",
            defaults={
                'exam_type': ExamType.PRACTICAL,
                'description': "Hands-on practical assessment covering live triage, memory dump examination, and attack containment.",
                'duration_minutes': 90,
                'passing_score': 70,
                'max_attempts': 1,
                'is_published': True,
            }
        )
        if exam_practical.lab_tasks.count() == 0:
            PracticalLabTask.objects.create(
                exam=exam_practical,
                title="Triage Compromised Linux Web Server",
                instructions="Log into the isolated container instance, locate the hidden web shell in /var/www, extract the attacker IP, and terminate the reverse shell process.",
                docker_template_id="cyber-range/web-triage-lab",
                points=Decimal('25.00'),
                verification_method="AUTOMATED_FLAG"
            )
            PracticalLabTask.objects.create(
                exam=exam_practical,
                title="Analyze Volatility Memory Dump",
                instructions="Analyze memory image 'compromised.raw' using Volatility3 plugins (windows.pslist, windows.netscan) to identify the injected DLL and recover the flag.",
                docker_template_id="cyber-range/volatility-memory-lab",
                points=Decimal('25.00'),
                verification_method="AUTOMATED_FLAG"
            )

        exam_final, _ = Exam.objects.get_or_create(
            course=course,
            title="Certificate in Cyber Security Comprehensive Final Examination",
            defaults={
                'exam_type': ExamType.FINAL,
                'description': "Comprehensive summative examination verifying mastery of all 14 certificate curriculum modules.",
                'duration_minutes': 120,
                'passing_score': 75,
                'max_attempts': 1,
                'randomize_questions': True,
                'is_published': True,
            }
        )
        if exam_final.questions.count() == 0:
            fq1 = ExamQuestion.objects.create(
                exam=exam_final, order=1,
                question_text="In asymmetric cryptography, which key is used to sign a digital certificate, and which is used to verify it?",
                question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('15.00'),
                explanation="Digital signatures are generated using the sender's Private Key and verified by anyone using their Public Key."
            )
            ExamOption.objects.create(question=fq1, option_text="Sign with Private Key, verify with Public Key", is_correct=True, order=1)
            ExamOption.objects.create(question=fq1, option_text="Sign with Public Key, verify with Private Key", is_correct=False, order=2)
            ExamOption.objects.create(question=fq1, option_text="Sign with Symmetric Key, verify with Session Key", is_correct=False, order=3)

        self.stdout.write(self.style.SUCCESS("Seeded Exams and Practical Lab Tasks."))

        # ==============================================================================
        # 14. Learning Paths (5 Tracks)
        # ==============================================================================
        paths_data = [
            ("Cyber Security Beginner", "cyber-security-beginner",
             "Start your cybersecurity career from scratch with foundational networking, Linux administration, and security fundamentals in the flagship 10-Month Certificate.",
             "shield", 10, LearningPathLevel.BEGINNER,
             [(course, 1)]),

            ("Ethical Hacking Path", "ethical-hacking-path",
             "Step-by-step roadmap to offensive penetration testing, network reconnaissance, and vulnerability exploitation in the Certificate Program.",
             "terminal", 10, LearningPathLevel.INTERMEDIATE,
             [(course, 1)]),

            ("SOC Analyst Path", "soc-analyst-path",
             "Become a frontline cyber defender. Master log aggregation, Wazuh SIEM threat detection, and incident triage in the Certificate Program.",
             "activity", 10, LearningPathLevel.INTERMEDIATE,
             [(course, 1)]),

            ("Digital Forensics Path", "digital-forensics-path",
             "Specialized forensics path covering chain of custody, filesystem artifacts, Volatility memory triage, and evidence recovery.",
             "search", 10, LearningPathLevel.ADVANCED,
             [(course, 1)]),

            ("Cloud Security Path", "cloud-security-path",
             "Secure modern multi-cloud architectures, containerized environments, Kubernetes clusters, and zero-trust IAM frameworks.",
             "cloud", 10, LearningPathLevel.ADVANCED,
             [(course, 1)]),
        ]

        created_paths = {}
        for p_title, p_slug, p_desc, p_icon, p_months, p_level, p_courses in paths_data:
            lp, _ = LearningPath.objects.get_or_create(
                slug=p_slug,
                defaults={
                    'title': p_title,
                    'description': p_desc,
                    'icon': p_icon,
                    'estimated_months': p_months,
                    'level': p_level,
                    'is_published': True,
                }
            )
            LearningPathCourse.objects.filter(learning_path=lp).delete()
            for c_obj, c_order in p_courses:
                LearningPathCourse.objects.create(
                    learning_path=lp,
                    course=c_obj,
                    order=c_order
                )
            created_paths[p_slug] = lp
        self.stdout.write(self.style.SUCCESS("Seeded 5 Learning Paths."))

        # ==============================================================================
        # 15. Achievement Badges (8 Badges)
        # ==============================================================================
        achievements_data = [
            ("FIRST_STEP", "First Step into the Cyber Realm", "Enrolled in your first cybersecurity course at Future Tech Academy.", "shield-check", BadgeType.BRONZE, 10, "ENROLLMENT"),
            ("QUIZ_EXPLORER", "Knowledge Seeker", "Completed your first knowledge verification quiz with passing marks.", "help-circle", BadgeType.BRONZE, 20, "QUIZ"),
            ("PERFECT_SCORE", "Flawless Execution", "Scored a perfect 100% on a course assessment.", "zap", BadgeType.GOLD, 50, "SCORE"),
            ("MISSION_SUBMITTED", "Field Agent", "Submitted your first hands-on cybersecurity assignment.", "send", BadgeType.SILVER, 30, "ASSIGNMENT"),
            ("COURSE_COMPLETER", "Course Graduate", "Completed 100% of all required coursework in a training track.", "award", BadgeType.PLATINUM, 100, "COMPLETION"),
            ("CERTIFIED_SPECIALIST", "Verified Operator", "Earned an official cryptographically verified certificate.", "file-check", BadgeType.PLATINUM, 100, "CERTIFICATE"),
            ("LINUX_MASTER", "Kernel Commando", "Mastered Linux systems administration, security baselines, and permissions.", "terminal", BadgeType.GOLD, 50, "COURSE"),
            ("NETWORK_DEFENDER", "Packet Whisperer", "Successfully mastered TCP/IP architecture and network protocol defense.", "activity", BadgeType.GOLD, 50, "COURSE"),
        ]

        ach_objs = {}
        for code, title, desc, icon, btype, points, ctype in achievements_data:
            ach, _ = Achievement.objects.get_or_create(
                code=code,
                defaults={
                    'title': title,
                    'description': desc,
                    'icon': icon,
                    'badge_type': btype,
                    'points': points,
                    'criteria_type': ctype,
                }
            )
            ach_objs[code] = ach
        self.stdout.write(self.style.SUCCESS("Seeded 8 Achievement Badges."))

        # ==============================================================================
        # 16. Certificate Template
        # ==============================================================================
        CertificateTemplate.objects.get_or_create(
            title="Certificate in Cyber Security",
            defaults={
                'signatory_name': "Dr. Morpheus Vance",
                'signatory_title': "Director of Training & Lead Instructor",
                'academy_title': "Future Tech Academy",
                'is_default': True,
            }
        )

        # ==============================================================================
        # 17. Seed Realistic Student Activity (Neo & Alice)
        # ==============================================================================
        neo = User.objects.get(email="student.neo@futuretech.edu")
        alice = User.objects.get(email="student.alice@futuretech.edu")

        # Enroll Neo in all 3 courses & beginner learning path
        for c in [course, linux_course, net_course]:
            Enrollment.objects.get_or_create(student=neo, course=c)
        StudentLearningPath.objects.get_or_create(
            student=neo,
            learning_path=created_paths["cyber-security-beginner"],
            defaults={'progress_percentage': Decimal('33.33')}
        )

        # Mark first 3 lessons completed for Neo in Certificate
        for les in mod1.lessons.all()[:3]:
            LessonProgress.objects.get_or_create(
                student=neo, lesson=les,
                defaults={'completed': True, 'completed_at': timezone.now(), 'started_at': timezone.now()}
            )

        # Neo Quiz Attempt (100% score)
        QuizAttempt.objects.get_or_create(
            student=neo,
            quiz=quiz1,
            attempt_number=1,
            defaults={
                'score': Decimal('10.00'),
                'percentage': Decimal('100.00'),
                'passed': True,
                'is_completed': True,
                'time_spent_seconds': 420,
                'submitted_at': timezone.now(),
            }
        )

        # Neo Assignment Submission (Graded: 95/100)
        sub_neo, _ = AssignmentSubmission.objects.get_or_create(
            assignment=assign1,
            student=neo,
            defaults={
                'submission_text': "Comprehensive STRIDE Threat Model Report submitted for financial core banking gateway.\nAll DFD Level 1 and 2 diagrams attached. Calculated DREAD score: 8.2.",
                'status': SubmissionStatus.GRADED,
            }
        )
        if sub_neo and not sub_neo.feedbacks.exists():
            AssignmentFeedback.objects.create(
                submission=sub_neo,
                instructor=ins1,
                score=Decimal('95.00'),
                feedback="Outstanding threat decomposition! Excellent DREAD calculation and realistic architectural mitigations."
            )

        # Alice Assignment Submission (Pending Grading in Queue!)
        Enrollment.objects.get_or_create(student=alice, course=course)
        AssignmentSubmission.objects.get_or_create(
            assignment=assign1,
            student=alice,
            defaults={
                'submission_text': "Draft threat model report for banking gateway. Detailed analysis of CSRF and spoofing threat vectors.",
                'status': SubmissionStatus.SUBMITTED,
            }
        )

        # Award Badges to Neo
        for b_code in ["FIRST_STEP", "QUIZ_EXPLORER", "PERFECT_SCORE"]:
            if b_code in ach_objs:
                StudentAchievement.objects.get_or_create(student=neo, achievement=ach_objs[b_code])

        # Issue 1 verified certificate to Neo for Certificate in Cyber Security
        CertificateGenerationService.issue_certificate(neo, course)

        # 18. Campus Announcements
        Announcement.objects.get_or_create(
            title="Welcome to Future Tech Cyber Security Academy",
            defaults={
                'content': (
                    "Welcome students and instructors to our premier cohort! "
                    "All certificate tracks are now open. Ensure your lab access credentials are set, "
                    "and review the assessment grading policy in your student handbook."
                ),
                'created_by': admin_user,
                'is_pinned': True,
            }
        )
        Announcement.objects.get_or_create(
            title="Module 1 Threat Modeling Reports Due This Friday",
            course=course,
            defaults={
                'content': "Reminder for all enrolled Certificate candidates: Your STRIDE threat model submissions must be submitted by 23:59 GMT.",
                'created_by': ins1,
                'is_pinned': True,
            }
        )

        # 19. Course Review
        CourseReview.objects.get_or_create(
            course=course,
            student=neo,
            defaults={
                'rating': 5,
                'comment': "The best cybersecurity curriculum I've experienced. Thorough theory backed by rigorous assessments."
            }
        )

        # 20. Phase 3: Cyber Range Labs, CTF Challenges & Scoreboard
        self.stdout.write(self.style.NOTICE("Seeding Cyber Range Labs, CTF Challenges & Scoreboard..."))

        # Lab Categories
        lab_cat_web, _ = LabCategory.objects.get_or_create(
            name="Web Application Security",
            slug="web-application-security",
            defaults={'description': "Hands-on targets covering OWASP Top 10 vulnerabilities, injection, and auth bypass."}
        )
        lab_cat_sys, _ = LabCategory.objects.get_or_create(
            name="Linux System Exploitation",
            slug="linux-system-exploitation",
            defaults={'description': "Privilege escalation, GTFOBins, misconfigured cron jobs, and SUID binaries."}
        )
        lab_cat_net, _ = LabCategory.objects.get_or_create(
            name="Network Analysis & Defense",
            slug="network-analysis-defense",
            defaults={'description': "Network packet inspection, C2 beacon hunting, and firewall configuration."}
        )
        lab_cat_bof, _ = LabCategory.objects.get_or_create(
            name="Binary Exploitation",
            slug="binary-exploitation",
            defaults={'description': "Stack buffer overflows, shellcoding, and memory corruption concepts."}
        )

        # Lab 1: DVWA Target
        lab1, _ = Lab.objects.get_or_create(
            slug="dvwa-web-pentesting",
            defaults={
                'name': "DVWA: SQL Injection & Auth Bypass",
                'category': lab_cat_web,
                'difficulty': LabDifficulty.BEGINNER,
                'type': LabType.GUIDED,
                'short_description': "Exploit SQL injection vulnerabilities and bypass broken authentication on a live target.",
                'description': (
                    "In this guided laboratory exercise, candidates deploy an isolated Damn Vulnerable Web Application "
                    "sandbox container. Analyze authentication forms, perform SQL injection to extract user tables, "
                    "and capture the administrative root flag."
                ),
                'docker_image': "futuretech/dvwa-target:1.0",
                'cpu_limit': Decimal('1.0'),
                'memory_limit_mb': 1024,
                'storage_limit_mb': 2048,
                'max_runtime_minutes': 60,
                'points': 100,
                'created_by': ins1,
                'is_published': True,
            }
        )
        LabObjective.objects.get_or_create(
            lab=lab1, order=1,
            defaults={'title': "Discover SQL Injection parameter on user lookup form", 'points': 30, 'required': True}
        )
        LabObjective.objects.get_or_create(
            lab=lab1, order=2,
            defaults={'title': "Dump admin password hash and capture system flag", 'points': 70, 'required': True}
        )
        LabHint.objects.get_or_create(
            lab=lab1, order=1,
            defaults={'hint_text': "Use single quotes (') to test input reflection and check for SQLite or MySQL syntax errors.", 'penalty_percent': 10}
        )
        LabFlag.objects.get_or_create(
            lab=lab1,
            defaults={'flag_type': FlagType.STATIC_FLAG, 'static_flag': "FTACK{sqli_pwn3d_4uth_byp4ss}", 'points': 100}
        )

        # Lab 2: Linux PrivEsc
        lab2, _ = Lab.objects.get_or_create(
            slug="linux-privilege-escalation",
            defaults={
                'name': "Linux SUID & Sudo Privilege Escalation",
                'category': lab_cat_sys,
                'difficulty': LabDifficulty.MEDIUM,
                'type': LabType.CHALLENGE,
                'short_description': "Identify misconfigured sudo rights and SUID binaries to elevate from www-data to root.",
                'description': (
                    "Gain initial low-privilege shell access, enumerate the system environment, "
                    "identify an exploitable SUID binary, and escalate privileges to root."
                ),
                'docker_image': "futuretech/linux-privesc-target:1.0",
                'cpu_limit': Decimal('1.5'),
                'memory_limit_mb': 1024,
                'storage_limit_mb': 2048,
                'max_runtime_minutes': 90,
                'points': 150,
                'created_by': ins1,
                'is_published': True,
            }
        )
        LabFlag.objects.get_or_create(
            lab=lab2,
            defaults={'flag_type': FlagType.STATIC_FLAG, 'static_flag': "FTACK{suid_pr1v_3sc4l4t10n_r00t}", 'points': 150}
        )

        # Lab 3: Packet Triage
        lab3, _ = Lab.objects.get_or_create(
            slug="network-c2-beacon-hunting",
            defaults={
                'name': "Network Packet Triage: C2 Beacon Hunting",
                'category': lab_cat_net,
                'difficulty': LabDifficulty.EASY,
                'type': LabType.GUIDED,
                'short_description': "Analyze captured PCAP traffic to identify Cobalt Strike beacon intervals and extract exfiltrated data.",
                'description': (
                    "Inspect live packet streams using Wireshark and TShark. Filter DNS tunneling requests, "
                    "isolate command and control intervals, and extract hidden payload flags."
                ),
                'docker_image': "futuretech/pcap-analysis-target:1.0",
                'cpu_limit': Decimal('1.0'),
                'memory_limit_mb': 512,
                'storage_limit_mb': 1024,
                'max_runtime_minutes': 45,
                'points': 100,
                'created_by': ins1,
                'is_published': True,
            }
        )
        LabFlag.objects.get_or_create(
            lab=lab3,
            defaults={'flag_type': FlagType.STATIC_FLAG, 'static_flag': "FTACK{pcap_c2_b34c0n_d3t3ct3d}", 'points': 100}
        )

        # Lab 4: OWASP Juice Shop (Web Application Security Target)
        module_web = CourseModule.objects.filter(course=course, order=7).first()
        lab_juice, _ = Lab.objects.get_or_create(
            slug="owasp-juice-shop",
            defaults={
                'name': "OWASP Juice Shop: Web Security Range",
                'category': lab_cat_web,
                'difficulty': LabDifficulty.BEGINNER,
                'type': LabType.WEB_APPLICATION,
                'short_description': "Audit an intentionally vulnerable modern e-commerce web application covering the OWASP Top 10.",
                'description': (
                    "OWASP Juice Shop is an intentionally insecure web application written in Node.js, Express, and Angular. "
                    "Each candidate receives an isolated, dedicated container instance accessed through the academy gateway. "
                    "Find hidden score boards, exploit SQL injection to bypass admin login, perform DOM XSS, and exploit IDOR flaws."
                ),
                'docker_image': "bkimminich/juice-shop:v17.1.1",
                'cpu_limit': Decimal('1.0'),
                'memory_limit_mb': 1024,
                'storage_limit_mb': 2048,
                'process_limit': 150,
                'max_runtime_minutes': 120,
                'points': 500,
                'course': course,
                'module': module_web,
                'access_type': LabAccessType.WEB,
                'terminal_enabled': False,
                'web_access_enabled': True,
                'created_by': ins1,
                'is_published': True,
            }
        )
        LabObjective.objects.get_or_create(
            lab=lab_juice, order=1,
            defaults={'title': "Discover hidden Score Board administration route", 'points': 50, 'required': True}
        )
        LabObjective.objects.get_or_create(
            lab=lab_juice, order=2,
            defaults={'title': "Bypass Admin Login using SQL Injection", 'points': 100, 'required': True}
        )
        LabObjective.objects.get_or_create(
            lab=lab_juice, order=3,
            defaults={'title': "Execute DOM-based Cross-Site Scripting (XSS)", 'points': 100, 'required': True}
        )
        LabObjective.objects.get_or_create(
            lab=lab_juice, order=4,
            defaults={'title': "Exfiltrate acquisition files via Path Traversal", 'points': 100, 'required': True}
        )
        LabObjective.objects.get_or_create(
            lab=lab_juice, order=5,
            defaults={'title': "Tamper with Basket IDOR in REST API", 'points': 150, 'required': True}
        )

        LabHint.objects.get_or_create(
            lab=lab_juice, order=1,
            defaults={'hint_text': "Inspect bundled main.js and router configurations in your browser DevTools for path declarations.", 'penalty_percent': 10}
        )
        LabHint.objects.get_or_create(
            lab=lab_juice, order=2,
            defaults={'hint_text': "Use classic boolean OR payloads (' OR 1=1--) in the email login field.", 'penalty_percent': 10}
        )

        LabFlag.objects.get_or_create(
            lab=lab_juice,
            flag_type=FlagType.DYNAMIC_FLAG,
            defaults={
                'dynamic_flag_pattern': "FTACK{js_scoreboard_{instance_uuid}}",
                'points': 50,
            }
        )

        # CTF Challenge Categories
        cc_crypto, _ = ChallengeCategory.objects.get_or_create(
            name="Cryptography", slug="cryptography", defaults={'icon': 'key'}
        )
        cc_web, _ = ChallengeCategory.objects.get_or_create(
            name="Web Exploitation", slug="web-exploitation", defaults={'icon': 'globe'}
        )
        cc_forensics, _ = ChallengeCategory.objects.get_or_create(
            name="Forensics", slug="forensics", defaults={'icon': 'search'}
        )
        cc_osint, _ = ChallengeCategory.objects.get_or_create(
            name="OSINT", slug="osint", defaults={'icon': 'eye'}
        )

        # Standalone CTF Challenges
        Challenge.objects.get_or_create(
            slug="broken-jwt-signature",
            defaults={
                'title': "Broken JWT: None Algorithm Forge",
                'category': cc_web,
                'difficulty': LabDifficulty.EASY,
                'points': 100,
                'description': "A vulnerable API endpoint allows authentication tokens signed with 'alg': 'none'. Forge an administrator session token and claim the flag.",
                'instructions': "Inspect the JWT header and payload in base64url. Change 'role' to 'admin' and strip the signature component.",
                'flag': "FTACK{jwt_4lg_n0n3_f0rg3_succ3ss}",
                'is_active': True,
                'solves_count': 14,
            }
        )
        Challenge.objects.get_or_create(
            slug="rsa-small-e-attack",
            defaults={
                'title': "RSA Small Public Exponent Attack",
                'category': cc_crypto,
                'difficulty': LabDifficulty.MEDIUM,
                'points': 150,
                'description': "An intercepted RSA encrypted ciphertext used e=3 without proper padding. Compute the integer cube root of the ciphertext to decrypt the message.",
                'instructions': "Since m^e < n, the modulus did not wrap around. A direct integer cube root yields the plaintext bytes.",
                'flag': "FTACK{rs4_sm4ll_3_c0mput3_r00t}",
                'is_active': True,
                'solves_count': 8,
            }
        )
        Challenge.objects.get_or_create(
            slug="wireshark-stream-carving",
            defaults={
                'title': "Suspicious DNS Tunnel Carving",
                'category': cc_forensics,
                'difficulty': LabDifficulty.EASY,
                'points': 100,
                'description': "An insider threat exfiltrated company secrets encoded in DNS subdomain queries. Reassemble the hexadecimal stream to recover the flag.",
                'flag': "FTACK{dns_tunn3l_st3n0_3xf1ltr4t10n}",
                'is_active': True,
                'solves_count': 22,
            }
        )
        Challenge.objects.get_or_create(
            slug="covert-subdomain-recon",
            defaults={
                'title': "Covert Subdomain Recon & Certificate Transparency",
                'category': cc_osint,
                'difficulty': LabDifficulty.BEGINNER,
                'points': 75,
                'description': "Query Certificate Transparency logs for `futuretech-academy.internal` to locate the hidden development staging portal and read the flag.",
                'flag': "FTACK{ct_l0gs_r3v34l_4ll_s3cr3ts}",
                'is_active': True,
                'solves_count': 35,
            }
        )

        # CTF Event
        now = timezone.now()
        CTFEvent.objects.get_or_create(
            slug="futuretech-national-cyber-cup-2026",
            defaults={
                'name': "Future Tech National Cyber Cup 2026",
                'description': "The annual premier Capture The Flag competition for Myanmar and ASEAN cybersecurity cadets.",
                'start_time': now - timezone.timedelta(days=2),
                'end_time': now + timezone.timedelta(days=5),
                'status': CTFEventStatus.LIVE,
                'max_participants': 100,
                'is_team_event': False,
            }
        )

        # Cumulative Leaderboard Scores
        CTFScore.objects.get_or_create(
            student=neo,
            defaults={
                'points': 450,
                'lab_points': 250,
                'challenge_points': 200,
                'solves_count': 3,
                'labs_completed_count': 2,
            }
        )
        if 'trinity' in locals() or User.objects.filter(username='trinity').exists():
            trin_user = User.objects.get(username='trinity')
            CTFScore.objects.get_or_create(
                student=trin_user,
                defaults={
                    'points': 325,
                    'lab_points': 150,
                    'challenge_points': 175,
                    'solves_count': 2,
                    'labs_completed_count': 1,
                }
            )

        self.stdout.write(self.style.SUCCESS("Seeded Cyber Range Labs, CTF Challenges, Events & Leaderboard."))
        self.stdout.write(self.style.SUCCESS("=== Demo Data Seeding Completed Successfully! ==="))



