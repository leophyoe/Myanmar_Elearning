from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.courses.models import Course, Module, Lesson, Topic, Quiz, Question, Choice
from apps.labs.models import LabTemplate, Lab, LabCategory, LabDifficulty, LabType
from apps.ctf.models import Challenge, ChallengeCategory, ChallengeDifficulty
from apps.scoring.models import Badge, BadgeCriteriaType

class Command(BaseCommand):
    help = "Seeds the complete 14-Module 10-Month Diploma in Cyber Security curriculum, labs, CTF challenges, and badges."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Future Tech Cyber Range curriculum..."))

        # 1. Main Course: Diploma in Cyber Security
        course, created = Course.objects.get_or_create(
            slug="diploma-in-cyber-security",
            defaults={
                "title": "Diploma in Cyber Security",
                "description": (
                    "A rigorous 10-month professional diploma combining theoretical defense engineering, "
                    "hands-on offensive security laboratories, CTF challenge solving, SOC/SIEM operations, "
                    "and a capstone enterprise cyber range final project."
                ),
                "duration_months": 10,
                "is_published": True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Course: {course.title}"))

        # 2. Define Curriculum Specifications (14 Modules)
        modules_data = [
            {
                "order": 1,
                "code": "MOD-01",
                "title": "Introduction to Cyber Security",
                "summary": "Core principles of confidentiality, integrity, availability, threat landscapes, social engineering, and legal ethics.",
                "objectives": [
                    "Master CIA Triad and risk assessment equations",
                    "Identify social engineering and phishing tactics",
                    "Understand attack surfaces and vulnerability taxonomies",
                    "Apply legal and ethical boundaries in cybersecurity"
                ],
                "lessons": [
                    {"title": "Cybersecurity Terminology & The CIA Triad", "minutes": 45},
                    {"title": "Threats, Vulnerabilities & Risk Management", "minutes": 50},
                    {"title": "Phishing, Social Engineering & Password Attacks", "minutes": 60, "has_lab": True},
                    {"title": "Legal Responsibilities & Professional Ethics", "minutes": 40, "has_quiz": True},
                ]
            },
            {
                "order": 2,
                "code": "MOD-02",
                "title": "Computer Systems & Operating System Security",
                "summary": "Architectural security mechanisms across modern Linux and Windows environments, permissions, and system hardening.",
                "objectives": [
                    "Examine OS process lifecycles, memory structures, and kernel boundaries",
                    "Enforce discretionary and mandatory access controls",
                    "Configure security logging, auditing, and hardening baselines"
                ],
                "lessons": [
                    {"title": "Operating System Architecture & Kernel Security", "minutes": 50},
                    {"title": "Linux Permissions, Users & Group Management", "minutes": 60, "has_lab": True},
                    {"title": "Windows Security Architecture & Services", "minutes": 55, "has_lab": True},
                    {"title": "System Hardening & Baseline Auditing", "minutes": 50, "has_quiz": True},
                ]
            },
            {
                "order": 3,
                "code": "MOD-03",
                "title": "Networking Fundamentals",
                "summary": "Comprehensive examination of the OSI and TCP/IP protocol stacks, IPv4/IPv6 subnetting, routing, DNS, and traffic analysis.",
                "objectives": [
                    "Dissect packet headers across OSI and TCP/IP layers",
                    "Calculate IPv4 subnets and CIDR blocks",
                    "Investigate DNS and DHCP infrastructure vulnerabilities",
                    "Capture and analyze raw traffic with packet analyzers"
                ],
                "lessons": [
                    {"title": "OSI 7-Layer & TCP/IP Model Deep Dive", "minutes": 60},
                    {"title": "IPv4, IPv6 & Subnetting Mechanics", "minutes": 60, "has_lab": True},
                    {"title": "Core Protocols: DNS, DHCP, ARP & ICMP", "minutes": 50, "has_lab": True},
                    {"title": "Packet Capture & Protocol Inspection", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 4,
                "code": "MOD-04",
                "title": "Linux for Cyber Security",
                "summary": "Advanced command-line mastery, bash security automation, SSH cryptographic hardening, permissions, and log analysis.",
                "objectives": [
                    "Operate efficiently inside headless Linux environments",
                    "Audit SUID/SGID binaries and file permissions",
                    "Harden SSH daemon configurations with cryptographic keys",
                    "Parse and triage system logs with awk, sed, and grep"
                ],
                "lessons": [
                    {"title": "Linux CLI Mastery & File Hierarchy Standard", "minutes": 55, "has_lab": True},
                    {"title": "POSIX Permissions & SUID Privilege Escalation", "minutes": 65, "has_lab": True},
                    {"title": "SSH Cryptographic Hardening & Key Authentication", "minutes": 50, "has_lab": True},
                    {"title": "Syslog & Auditd Log Investigation", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 5,
                "code": "MOD-05",
                "title": "Windows & Active Directory Security",
                "summary": "Enterprise Active Directory domain architecture, Kerberos authentication, Group Policy enforcement, and Windows Event logs.",
                "objectives": [
                    "Administer Active Directory Domain Services (AD DS)",
                    "Configure and audit Group Policy Objects (GPOs)",
                    "Analyze Kerberos tickets (TGT, TGS) and NTLM fallback",
                    "Triage Windows Event IDs for security breaches"
                ],
                "lessons": [
                    {"title": "Windows Security Internals & PowerShell Administration", "minutes": 60, "has_lab": True},
                    {"title": "Active Directory Domain Services, OUs & Group Policy", "minutes": 65, "has_lab": True},
                    {"title": "Kerberos & NTLM Authentication Protocols", "minutes": 60},
                    {"title": "Windows Security Event Log Analysis", "minutes": 55, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 6,
                "code": "MOD-06",
                "title": "Ethical Hacking Fundamentals",
                "summary": "Penetration testing methodology, Rules of Engagement, OSINT reconnaissance, port scanning, service enumeration, and reporting.",
                "objectives": [
                    "Formulate professional penetration testing Rules of Engagement",
                    "Conduct active and passive reconnaissance",
                    "Execute stealthy and thorough network scans using Nmap",
                    "Document technical findings into executive remediation reports"
                ],
                "lessons": [
                    {"title": "Ethical Hacking Methodologies & Rules of Engagement", "minutes": 45},
                    {"title": "Passive Reconnaissance & OSINT Techniques", "minutes": 55, "has_lab": True},
                    {"title": "Network Scanning & Service Fingerprinting with Nmap", "minutes": 65, "has_lab": True},
                    {"title": "Service Enumeration & Vulnerability Mapping", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 7,
                "code": "MOD-07",
                "title": "Web Application Security",
                "summary": "Deep dive into web technologies, HTTP protocol mechanics, session management, and exploitation of the OWASP Top 10 vulnerabilities.",
                "objectives": [
                    "Intercept and manipulate HTTP/HTTPS traffic with proxy tools",
                    "Exploit and mitigate SQL Injection flaws",
                    "Identify Stored, Reflected, and DOM-based Cross-Site Scripting (XSS)",
                    "Audit Broken Object Level Authorization (BOLA) and access controls"
                ],
                "lessons": [
                    {"title": "HTTP Protocol Mechanics, Cookies & Session Security", "minutes": 50, "has_lab": True},
                    {"title": "SQL Injection: Detection, Exploitation & Prepared Statements", "minutes": 70, "has_lab": True},
                    {"title": "Cross-Site Scripting (XSS) & Content Security Policy", "minutes": 65, "has_lab": True},
                    {"title": "Broken Access Control & Insecure Direct Object References", "minutes": 60, "has_lab": True},
                    {"title": "Arbitrary File Upload Vulnerabilities & Web Shells", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 8,
                "code": "MOD-08",
                "title": "Network Security",
                "summary": "Network traffic monitoring, stateful firewalls, Intrusion Detection and Prevention Systems (IDS/IPS), and segmentation.",
                "objectives": [
                    "Dissect malicious traffic patterns with Wireshark and tcpdump",
                    "Configure Linux iptables and nftables firewall rules",
                    "Write signature rules for Suricata / Snort IDS",
                    "Design secure segmented network architectures"
                ],
                "lessons": [
                    {"title": "Deep Packet Inspection with Wireshark & tcpdump", "minutes": 65, "has_lab": True},
                    {"title": "Stateful Firewall Engineering (iptables & nftables)", "minutes": 60, "has_lab": True},
                    {"title": "Intrusion Detection & Prevention with Suricata", "minutes": 65, "has_lab": True},
                    {"title": "Network Segmentation & VLAN Security", "minutes": 50, "has_quiz": True},
                ]
            },
            {
                "order": 9,
                "code": "MOD-09",
                "title": "Vulnerability Assessment & Penetration Testing",
                "summary": "Systematic vulnerability lifecycle management, automated vulnerability scanning, CVSS v3.1 calculation, and technical reporting.",
                "objectives": [
                    "Execute vulnerability scans with automated scanners",
                    "Calculate and score risks using CVSS v3.1 metrics",
                    "Verify false positives through manual confirmation",
                    "Draft formal penetration testing reports with remediation strategies"
                ],
                "lessons": [
                    {"title": "Vulnerability Assessment Lifecycles & CVSS Scoring", "minutes": 55},
                    {"title": "Network Vulnerability Scanning & NSE Scripting", "minutes": 65, "has_lab": True},
                    {"title": "Web Application Vulnerability Assessment", "minutes": 65, "has_lab": True},
                    {"title": "Vulnerability Management & Pen Testing Reporting", "minutes": 60, "has_quiz": True},
                ]
            },
            {
                "order": 10,
                "code": "MOD-10",
                "title": "SOC, SIEM & Incident Response",
                "summary": "Security Operations Center procedures, log aggregation with Wazuh SIEM, alert triage, MITRE ATT&CK mapping, and containment.",
                "objectives": [
                    "Navigate SOC Tier 1, 2, and 3 incident escalation workflows",
                    "Deploy and query Wazuh SIEM rules and alerts",
                    "Extract and correlate Indicators of Compromise (IOCs)",
                    "Execute incident containment, eradication, and post-mortem recovery"
                ],
                "lessons": [
                    {"title": "SOC Architecture, Roles & MITRE ATT&CK Framework", "minutes": 50},
                    {"title": "SIEM Deployment & Log Ingestion with Wazuh", "minutes": 70, "has_lab": True},
                    {"title": "Alert Triage, Correlation & Threat Hunting", "minutes": 65, "has_lab": True},
                    {"title": "Incident Response: Containment, Eradication & Recovery", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 11,
                "code": "MOD-11",
                "title": "Digital Forensics & Malware Fundamentals",
                "summary": "Digital evidence preservation, chain of custody, file carving, memory analysis with Volatility, and static malware triage.",
                "objectives": [
                    "Maintain evidentiary integrity and cryptographic chain of custody",
                    "Analyze Windows and Linux filesystem forensic artifacts",
                    "Extract memory injection artifacts with Volatility",
                    "Perform static malware analysis with strings, hashes, and PE headers"
                ],
                "lessons": [
                    {"title": "Digital Evidence Handling & Chain of Custody", "minutes": 45},
                    {"title": "Filesystem Artifacts & Browser Forensics", "minutes": 65, "has_lab": True},
                    {"title": "Volatile Memory Forensics & Process Injection", "minutes": 70, "has_lab": True},
                    {"title": "Static Malware Analysis & IOC Extraction", "minutes": 60, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 12,
                "code": "MOD-12",
                "title": "Python for Cyber Security",
                "summary": "Python automation for offensive and defensive security operations, socket programming, regex log triage, and REST API scripting.",
                "objectives": [
                    "Script custom network socket port scanners",
                    "Automate high-throughput log analysis with regex and JSON",
                    "Build cryptographic file integrity monitoring daemons",
                    "Query threat intelligence feeds programmatically"
                ],
                "lessons": [
                    {"title": "Python Scripting Fundamentals & Regex for Security", "minutes": 55},
                    {"title": "Socket Programming: Port Scanners & Banner Grabbers", "minutes": 65, "has_lab": True},
                    {"title": "Security Automation: Log Analyzers & File Integrity Checkers", "minutes": 65, "has_lab": True},
                    {"title": "Threat Intelligence APIs & Automated IOC Lookup", "minutes": 55, "has_lab": True, "has_quiz": True},
                ]
            },
            {
                "order": 13,
                "code": "MOD-13",
                "title": "Cloud Security, DevSecOps & Modern Cyber Security",
                "summary": "Cloud shared responsibility, AWS/GCP IAM least privilege, container isolation, Docker hardening, and CI/CD security scanning.",
                "objectives": [
                    "Audit cloud Identity and Access Management (IAM) permissions",
                    "Harden Docker container images and runtimes against breakout",
                    "Integrate SAST and DAST vulnerability scanners into CI/CD pipelines",
                    "Architect Zero-Trust cloud network micro-segmentation"
                ],
                "lessons": [
                    {"title": "Cloud Architecture, Shared Responsibility & IAM Least Privilege", "minutes": 55, "has_lab": True},
                    {"title": "Container Security: Docker Benchmarking & Isolation", "minutes": 65, "has_lab": True},
                    {"title": "DevSecOps CI/CD Pipeline Automation (SAST & DAST)", "minutes": 60, "has_lab": True},
                    {"title": "Zero Trust Architecture & Modern Perimeter Defense", "minutes": 50, "has_quiz": True},
                ]
            },
            {
                "order": 14,
                "code": "MOD-14",
                "title": "Integrated Cyber Security Laboratory & Capstone",
                "summary": "End-to-end cyber range defense and attack simulation. Students propose, design, assess, remediate, report, and defend in a live Viva.",
                "objectives": [
                    "Conduct holistic enterprise attack and defense operations",
                    "Synthesize network, OS, web, and SOC skills into an enterprise assessment",
                    "Deliver an executive-level risk remediation roadmap",
                    "Defend findings and technical evidence before an examination board (Viva)"
                ],
                "lessons": [
                    {"title": "Capstone Proposal & Enterprise Cyber Range Architecture", "minutes": 60},
                    {"title": "Enterprise Security Assessment & Attack Simulation", "minutes": 120, "has_lab": True},
                    {"title": "Remediation Engineering & Technical Audit Report", "minutes": 90},
                    {"title": "Capstone Defense & Viva Voce Examination", "minutes": 60, "has_quiz": True},
                ]
            }
        ]

        created_lessons_map = {}

        for m_data in modules_data:
            module, _ = Module.objects.get_or_create(
                course=course,
                code=m_data["code"],
                defaults={
                    "order": m_data["order"],
                    "title": m_data["title"],
                    "summary": m_data["summary"],
                    "learning_objectives": m_data["objectives"],
                    "icon_name": "shield",
                }
            )

            for idx, l_data in enumerate(m_data["lessons"], start=1):
                lesson, _ = Lesson.objects.get_or_create(
                    module=module,
                    order=idx,
                    defaults={
                        "title": l_data["title"],
                        "content_markdown": (
                            f"# {l_data['title']}\n\n"
                            f"**Module:** {module.code} - {module.title}\n\n"
                            f"## Overview\n"
                            f"In this lesson, students analyze the foundational architecture, defensive counter-measures, "
                            f"and adversarial techniques relevant to {l_data['title']}.\n\n"
                            f"## Learning Objectives\n"
                            f"- Understand the technical mechanisms governing this topic.\n"
                            f"- Perform security assessments adhering to standard Rules of Engagement.\n"
                            f"- Validate security controls through practical verification.\n\n"
                            f"## Practical Hands-On Component\n"
                            f"Review the associated laboratory environment below to test your skills in an isolated Docker sandbox."
                        ),
                        "estimated_minutes": l_data.get("minutes", 45),
                        "has_lab": l_data.get("has_lab", False),
                        "has_quiz": l_data.get("has_quiz", False),
                    }
                )
                created_lessons_map[f"{module.code}_L{idx}"] = lesson

                # Create sample quiz if indicated
                if l_data.get("has_quiz", False) and not hasattr(lesson, 'quiz'):
                    quiz = Quiz.objects.create(
                        lesson=lesson,
                        title=f"{module.code} Checkpoint Quiz: {lesson.title}",
                        passing_percentage=75
                    )
                    q1 = Question.objects.create(
                        quiz=quiz,
                        order=1,
                        prompt="Which principle of the CIA Triad is violated when an attacker alters financial transaction records?",
                        points=10,
                        explanation="Integrity ensures that data has not been modified or corrupted by unauthorized parties."
                    )
                    Choice.objects.create(question=q1, text="Confidentiality", is_correct=False)
                    Choice.objects.create(question=q1, text="Integrity", is_correct=True)
                    Choice.objects.create(question=q1, text="Availability", is_correct=False)
                    Choice.objects.create(question=q1, text="Non-repudiation", is_correct=False)

                    q2 = Question.objects.create(
                        quiz=quiz,
                        order=2,
                        prompt="In an isolated Docker laboratory, why is the network created with internal=True?",
                        points=10,
                        explanation="An internal Docker network blocks default gateway routes, preventing any packets from egressing to the public WAN."
                    )
                    Choice.objects.create(question=q2, text="To increase packet speed", is_correct=False)
                    Choice.objects.create(question=q2, text="To prevent unauthorized scanning or attacking of public Internet targets", is_correct=True)
                    Choice.objects.create(question=q2, text="To allow external SSH connections from anywhere", is_correct=False)
                    Choice.objects.create(question=q2, text="To bypass Docker firewall rules", is_correct=False)

        self.stdout.write(self.style.SUCCESS("All 14 Modules and structured Lessons created."))

        # 3. Seed the 16 Required Sample Labs and LabTemplates
        sample_labs_config = [
            ("Linux File Permissions", "linux-file-permissions", LabCategory.LINUX, LabDifficulty.EASY, LabType.GUIDED, "ftcr-labs/linux-permissions:latest", "MOD-02_L2"),
            ("Linux Log Investigation", "linux-log-investigation", LabCategory.LINUX, LabDifficulty.MEDIUM, LabType.INVESTIGATION, "ftcr-labs/linux-logs:latest", "MOD-04_L4"),
            ("Network Discovery", "network-discovery", LabCategory.NETWORKING, LabDifficulty.EASY, LabType.GUIDED, "ftcr-labs/net-discovery:latest", "MOD-03_L2"),
            ("Nmap Fundamentals", "nmap-fundamentals", LabCategory.NETWORKING, LabDifficulty.EASY, LabType.CHALLENGE, "ftcr-labs/nmap-basics:latest", "MOD-06_L3"),
            ("Wireshark Packet Analysis", "wireshark-packet-analysis", LabCategory.NETWORKING, LabDifficulty.MEDIUM, LabType.INVESTIGATION, "ftcr-labs/wireshark-pcap:latest", "MOD-08_L1"),
            ("HTTP Fundamentals", "http-fundamentals", LabCategory.WEB, LabDifficulty.EASY, LabType.GUIDED, "ftcr-labs/http-basics:latest", "MOD-07_L1"),
            ("SQL Injection Basics", "sql-injection-basics", LabCategory.WEB, LabDifficulty.MEDIUM, LabType.CHALLENGE, "ftcr-labs/sqli-basics:latest", "MOD-07_L2"),
            ("XSS Basics", "xss-basics", LabCategory.WEB, LabDifficulty.EASY, LabType.CHALLENGE, "ftcr-labs/xss-basics:latest", "MOD-07_L3"),
            ("Authentication Security", "authentication-security", LabCategory.WEB, LabDifficulty.MEDIUM, LabType.DEFENSIVE, "ftcr-labs/auth-security:latest", "MOD-07_L1"),
            ("Access Control", "access-control", LabCategory.WEB, LabDifficulty.MEDIUM, LabType.CHALLENGE, "ftcr-labs/access-control:latest", "MOD-07_L4"),
            ("Vulnerability Assessment", "vulnerability-assessment", LabCategory.NETWORKING, LabDifficulty.MEDIUM, LabType.ATTACK_SIMULATION, "ftcr-labs/vapt-scan:latest", "MOD-09_L2"),
            ("SOC Log Investigation", "soc-log-investigation", LabCategory.SOC, LabDifficulty.MEDIUM, LabType.INVESTIGATION, "ftcr-labs/soc-triage:latest", "MOD-10_L3"),
            ("IOC Investigation", "ioc-investigation", LabCategory.SOC, LabDifficulty.MEDIUM, LabType.INVESTIGATION, "ftcr-labs/ioc-investigation:latest", "MOD-10_L4"),
            ("Digital Forensics", "digital-forensics", LabCategory.FORENSICS, LabDifficulty.HARD, LabType.INVESTIGATION, "ftcr-labs/forensics-disk:latest", "MOD-11_L2"),
            ("Python Log Analyzer", "python-log-analyzer", LabCategory.LINUX, LabDifficulty.MEDIUM, LabType.CHALLENGE, "ftcr-labs/python-automation:latest", "MOD-12_L3"),
            ("Docker Security", "docker-security", LabCategory.CLOUD, LabDifficulty.HARD, LabType.DEFENSIVE, "ftcr-labs/docker-hardening:latest", "MOD-13_L2"),
        ]

        for lab_title, slug, category, difficulty, lab_type, img, lesson_key in sample_labs_config:
            # Create Template
            tmpl, _ = LabTemplate.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": f"Template: {lab_title}",
                    "category": category,
                    "description": f"Standardized isolated sandbox container template for {lab_title}.",
                    "image_name": img,
                    "cpu_limit": "0.5",
                    "mem_limit": "512m",
                    "pids_limit": 100,
                    "read_only_root": True,
                    "default_duration_minutes": 90,
                }
            )

            lesson = created_lessons_map.get(lesson_key)

            # Create Lab
            lab, _ = Lab.objects.get_or_create(
                slug=slug,
                defaults={
                    "template": tmpl,
                    "lesson": lesson,
                    "title": lab_title,
                    "difficulty": difficulty,
                    "lab_type": lab_type,
                    "description": f"Comprehensive hands-on exercise evaluating skills in {lab_title}.",
                    "learning_objectives": [
                        f"Identify vulnerabilities or configurations related to {lab_title}",
                        "Apply defense or exploitation techniques inside isolated container sandbox",
                        "Extract and verify target dynamic flag"
                    ],
                    "prerequisites": "Completion of corresponding theoretical lesson and basic Linux CLI familiarity.",
                    "tasks": [
                        {"id": 1, "title": "Launch Lab Sandbox", "hint": "Click 'Start Lab' to provision your private container.", "points": 20},
                        {"id": 2, "title": "Perform Enumeration & Triage", "hint": "Inspect system directories and processes using the Web Terminal.", "points": 30},
                        {"id": 3, "title": "Locate and Submit Flag", "hint": "The flag is located in /root or the application database.", "points": 50, "flag_required": True},
                    ],
                    "points": 100,
                    "estimated_minutes": 60,
                }
            )

            # Create corresponding CTF Challenge
            ctf_cat_mapping = {
                LabCategory.LINUX: ChallengeCategory.LINUX,
                LabCategory.NETWORKING: ChallengeCategory.NETWORK,
                LabCategory.WEB: ChallengeCategory.WEB,
                LabCategory.WINDOWS: ChallengeCategory.LINUX,
                LabCategory.SOC: ChallengeCategory.SOC,
                LabCategory.FORENSICS: ChallengeCategory.FORENSICS,
                LabCategory.CLOUD: ChallengeCategory.CLOUD,
                LabCategory.CAPSTONE: ChallengeCategory.INCIDENT_RESPONSE,
            }
            diff_mapping = {
                LabDifficulty.EASY: ChallengeDifficulty.EASY,
                LabDifficulty.MEDIUM: ChallengeDifficulty.MEDIUM,
                LabDifficulty.HARD: ChallengeDifficulty.HARD,
            }

            Challenge.objects.get_or_create(
                slug=f"ctf-{slug}",
                defaults={
                    "title": f"Challenge: {lab_title}",
                    "category": ctf_cat_mapping.get(category, ChallengeCategory.LINUX),
                    "difficulty": diff_mapping.get(difficulty, ChallengeDifficulty.EASY),
                    "description": f"Target machine challenge for {lab_title}. Spawn the machine and extract the hidden flag.",
                    "points": 100,
                    "is_dynamic": True,
                    "lab": lab,
                    "hints": [{"hint": "Review the lesson documentation and inspect file permissions.", "cost": 10}],
                }
            )

        self.stdout.write(self.style.SUCCESS("All 16 Required Labs and CTF Challenges seeded."))

        # 4. Seed Achievement Badges
        badges_data = [
            ("Linux Beginner", "linux-beginner", "Awarded upon completing the first Linux security laboratory.", "terminal", BadgeCriteriaType.LABS_COMPLETED, 1),
            ("Network Analyst", "network-analyst", "Awarded upon completing 3 networking and packet analysis labs.", "network", BadgeCriteriaType.LABS_COMPLETED, 3),
            ("Web Security Beginner", "web-security-beginner", "Awarded upon solving your first OWASP web vulnerability challenge.", "code", BadgeCriteriaType.CHALLENGES_SOLVED, 1),
            ("Ethical Hacker", "ethical-hacker", "Awarded upon accumulating 500 CTF challenge points.", "shield-alert", BadgeCriteriaType.POINTS_THRESHOLD, 500),
            ("SOC Analyst", "soc-analyst", "Awarded upon completing the SOC and SIEM incident response laboratories.", "eye", BadgeCriteriaType.LABS_COMPLETED, 5),
            ("Forensics Investigator", "forensics-investigator", "Awarded upon solving memory and disk forensic challenges.", "search", BadgeCriteriaType.CHALLENGES_SOLVED, 5),
            ("Python Security Developer", "python-security-developer", "Awarded upon automating security tooling with Python.", "cpu", BadgeCriteriaType.LABS_COMPLETED, 7),
            ("Cloud Security", "cloud-security", "Awarded upon completing Docker and Cloud security laboratories.", "cloud", BadgeCriteriaType.LABS_COMPLETED, 9),
            ("Cyber Range Specialist", "cyber-range-specialist", "Awarded upon accumulating 1,500 total points in the cyber range.", "award", BadgeCriteriaType.POINTS_THRESHOLD, 1500),
        ]

        for b_name, b_slug, b_desc, b_icon, b_type, b_thresh in badges_data:
            Badge.objects.get_or_create(
                slug=b_slug,
                defaults={
                    "name": b_name,
                    "description": b_desc,
                    "icon": b_icon,
                    "criteria_type": b_type,
                    "criteria_threshold": b_thresh,
                }
            )

        self.stdout.write(self.style.SUCCESS("Platform Badges and Gamification milestones seeded."))
        self.stdout.write(self.style.SUCCESS("=== Curriculum Seeding Completed Successfully! ==="))

