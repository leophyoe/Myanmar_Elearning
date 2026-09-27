import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.accounts.models import User, RoleChoices
from apps.courses.models import (
    Course, CourseCategory, CourseModule, Lesson, LessonType,
    LearningObjective, CourseType, CourseLevel, CourseStatus
)
from apps.assessments.models import (
    Quiz, Question, QuestionOption, QuestionType,
    Assignment, AssignmentStatus, Exam, ExamType, ExamQuestion, ExamOption,
    FinalProject, AssessmentWeight
)

logger = logging.getLogger(__name__)


MODULES_SPEC = [
    {
        'order': 1,
        'title_en': "Introduction to Cyber Security",
        'title_my': "ဆိုက်ဘာလုံခြုံရေး မိတ်ဆက်",
        'desc_en': "Foundational security concepts, CIA Triad, threat classifications, risk management, and professional ethics.",
        'desc_my': "ဆိုက်ဘာလုံခြုံရေး အခြေခံသဘောတရားများ၊ CIA Triad၊ ခြိမ်းခြောက်မှု အမျိုးအစားများ၊ ဘေးအန္တရာယ် စီမံခန့်ခွဲမှုနှင့် ကျင့်ဝတ်များ။",
        'objectives': [
            ("Explain core information assurance principles (CIA Triad)", "သတင်းအချက်အလက် လုံခြုံရေး အခြေခံမူများ (CIA Triad) ကို ရှင်းပြနိုင်ရမည်။"),
            ("Identify common threat actors and vulnerability taxonomies", "ခြိမ်းခြောက်မှု ဖြစ်စေနိုင်သော အကြောင်းရင်းများနှင့် အားနည်းချက် အမျိုးအစားများကို ခွဲခြားသိရှိနိုင်ရမည်။"),
            ("Analyze social engineering attack vectors and password defense", "လူမှုအင်ဂျင်နီယာဆိုင်ရာ တိုက်ခိုက်မှု နည်းလမ်းများနှင့် စကားဝှက် ကာကွယ်ရေးကို ခွဲခြမ်းစိတ်ဖြာနိုင်ရမည်။"),
        ],
        'lessons': [
            ("The CIA Triad & Core Principles of Information Assurance", "CIA Triad နှင့် သတင်းအချက်အလက် လုံခြုံရေး အခြေခံသဘောတရားများ", LessonType.THEORY, 45,
             "# The CIA Triad\n\nConfidentiality (လျှို့ဝှက်ထားရှိခြင်း), Integrity (တိကျမှန်ကန်မှု မပျက်စီးစေခြင်း), Availability (အမြဲရယူသုံးစွဲနိုင်ခြင်း)."),
            ("Threat Modeling & Attack Surfaces", "ခြိမ်းခြောက်မှု ပုံစံထုတ်ခြင်းနှင့် တိုက်ခိုက်ခံရနိုင်သော မျက်နှာပြင်များ", LessonType.READING, 45,
             "# Threat Modeling\n\nIdentifying assets, threat actors, and attack vectors to protect systems proactively."),
            ("Password Security Architecture & Authentication", "စကားဝှက် လုံခြုံရေး ဗိသုကာနှင့် အထောက်အထားစစ်ဆေးခြင်း", LessonType.PRACTICAL, 60,
             "# Authentication Mechanisms\n\nConfiguring strong password policies, salted hashes (Argon2), and Multi-Factor Authentication (MFA)."),
        ],
        'quiz_question': ("Which pillar of the CIA Triad is protected by SHA-256 cryptographic hashing?", "CIA Triad ၏ မည်သည့်အပိုင်းကို SHA-256 hash ဖြင့် အဓိက ကာကွယ်ပေးသနည်း?", "Integrity", "Confidentiality"),
        'assignment_title': ("Analyze Corporate Threat Profile", "လုပ်ငန်းသုံး ခြိမ်းခြောက်မှု ပရိုဖိုင်ကို ခွဲခြမ်းစိတ်ဖြာခြင်း"),
        'exam_title': ("Module 1 Formal Examination: Security Fundamentals", "မော်ဂျူး ၁ စာမေးပွဲ - လုံခြုံရေး အခြေခံသဘောတရားများ"),
    },
    {
        'order': 2,
        'title_en': "Computer Systems & Operating System Security",
        'title_my': "ကွန်ပျူတာစနစ်များနှင့် စက်လည်ပတ်ရေးစနစ် လုံခြုံရေး",
        'title_my': "ကွန်ပျူတာစနစ်နှင့် Operating System လုံခြုံရေး",
        'desc_en': "Architectural security paradigms across operating systems, user privilege separation, DAC/MAC, and system hardening.",
        'desc_my': "OS ဗိသုကာဆိုင်ရာ လုံခြုံရေး၊ အသုံးပြုသူ အခွင့်အရေးခွဲခြားခြင်း၊ DAC/MAC မူဝါဒများနှင့် စနစ်လုံခြုံရေး တင်းကျပ်ခြင်း။",
        'objectives': [
            ("Understand CPU privilege levels and kernel space protection", "CPU အခွင့်အရေး အဆင့်များနှင့် Kernel ကာကွယ်ရေးကို နားလည်စေရန်။"),
            ("Differentiate Discretionary vs Mandatory Access Control", "DAC နှင့် MAC ခွင့်ပြုချက် စီမံခန့်ခွဲမှုပုံစံများကို ခွဲခြားသိရှိရန်။"),
            ("Apply operating system hardening baselines", "OS လုံခြုံရေး အခြေခံ စံသတ်မှတ်ချက်များကို လက်တွေ့အသုံးချရန်။"),
        ],
        'lessons': [
            ("Operating System Architecture & Kernel Boundaries", "OS ဗိသုကာနှင့် Kernel နယ်နိမိတ်များ", LessonType.THEORY, 45,
             "# OS Architecture\n\nRing 0 (Kernel) vs Ring 3 (User Space) separation and secure system calls."),
            ("Discretionary vs Mandatory Access Control", "ခွင့်ပြုချက် စီမံခန့်ခွဲမှု စနစ်များ (DAC vs MAC)", LessonType.READING, 45,
             "# Access Control Models\n\nUnderstanding permissions in POSIX, Windows ACLs, and SELinux/AppArmor."),
            ("OS Hardening & Attack Surface Reduction", "စနစ်လုံခြုံရေး တင်းကျပ်ခြင်းနှင့် တိုက်ခိုက်ခံရနိုင်ခြေ လျှော့ချခြင်း", LessonType.PRACTICAL, 60,
             "# Hardening Guidelines\n\nDisabling unnecessary daemons, configuring secure kernel parameters, and audit logging."),
        ],
        'quiz_question': ("In x86 architecture, which protection ring grants highest privilege?", "x86 ဗိသုကာတွင် မည်သည့် Ring က အမြင့်ဆုံး အခွင့်အရေးရှိသနည်း?", "Ring 0", "Ring 3"),
        'assignment_title': ("Host Hardening Audit Report", "ကွန်ပျူတာစနစ် လုံခြုံရေး စစ်ဆေးမှု အစီရင်ခံစာ"),
        'exam_title': ("Module 2 Formal Examination: OS Security", "မော်ဂျူး ၂ စာမေးပွဲ - OS လုံခြုံရေး"),
    },
    {
        'order': 3,
        'title_en': "Networking Fundamentals",
        'title_my': "ကွန်ရက် အခြေခံသဘောတရားများ",
        'title_my': "ကွန်ရက်အခြေခံများ",
        'desc_en': "OSI and TCP/IP models, packet structure, IP subnetting, routing protocols, and Wireshark packet capture analysis.",
        'desc_my': "OSI နှင့် TCP/IP မော်ဒယ်များ၊ Packet တည်ဆောက်ပုံ၊ Subnetting၊ လမ်းကြောင်းရှာဖွေခြင်းနှင့် Wireshark သုံးသပ်ခြင်း။",
        'objectives': [
            ("Deconstruct packets across all 7 OSI layers", "OSI အလွှာ ၇ ခုလုံးတွင် Packet စီးဆင်းပုံကို ခွဲခြမ်းစိတ်ဖြာနိုင်ရန်။"),
            ("Calculate binary IPv4/IPv6 CIDR subnets", "IPv4/IPv6 Subnet များ တွက်ချက်နိုင်ရန်။"),
            ("Inspect raw network frames with packet analyzers", "Wireshark ဖြင့် ကွန်ရက် အသွားအလာများကို ဖမ်းယူစစ်ဆေးနိုင်ရန်။"),
        ],
        'lessons': [
            ("OSI 7-Layer Model & TCP/IP Protocol Suite", "OSI အလွှာ ၇ ခုနှင့် TCP/IP ပရိုတိုကော စနစ်", LessonType.THEORY, 50,
             "# Networking Protocol Architecture\n\nEncapsulation and decapsulation across Physical to Application layers."),
            ("IPv4/IPv6 Addressing & CIDR Subnetting", "IPv4/IPv6 လိပ်စာများနှင့် Subnet ခွဲခြမ်းခြင်း", LessonType.THEORY, 60,
             "# Subnet Calculations\n\nNetwork addresses, broadcast domains, subnet masks, and slash notation (/24, /28)."),
            ("Packet Capture Analysis with Wireshark", "Wireshark ဖြင့် Packet များကို လက်တွေ့စစ်ဆေးခြင်း", LessonType.PRACTICAL, 60,
             "# Traffic Inspection\n\nFiltering TCP handshakes, DNS queries, and detecting unencrypted plaintext passwords."),
        ],
        'quiz_question': ("Which protocol operates at the Transport layer to provide reliable data delivery?", "ယုံကြည်စိတ်ချရသော ဒေတာပေးပို့မှုအတွက် Transport layer တွင် မည်သည့် protocol ကို သုံးသနည်း?", "TCP", "UDP"),
        'assignment_title': ("Wireshark Network Traffic Forensic Report", "Wireshark ကွန်ရက် မှုခင်း စစ်ဆေးမှု အစီရင်ခံစာ"),
        'exam_title': ("Module 3 Formal Examination: Networking Fundamentals", "မော်ဂျူး ၃ စာမေးပွဲ - ကွန်ရက် အခြေခံ"),
    },
    {
        'order': 4,
        'title_en': "Linux for Cyber Security",
        'title_my': "ဆိုက်ဘာလုံခြုံရေးအတွက် Linux စနစ်",
        'title_my': "Cyber Security အတွက် Linux",
        'desc_en': "Linux terminal mastery, filesystem hierarchy, user administration, file permissions, and Bash automation.",
        'desc_my': "Linux Terminal သုံးစွဲမှု၊ ဖိုင်စနစ် ဖွဲ့စည်းပုံ၊ အသုံးပြုသူ စီမံခန့်ခွဲမှု၊ ခွင့်ပြုချက်များနှင့် Bash Scripting။",
        'objectives': [
            ("Navigate the Linux Filesystem Hierarchy Standard (FHS)", "Linux ဖိုင်စနစ် ဖွဲ့စည်းပုံ (FHS) ကို ကျွမ်းကျင်စွာ အသုံးပြုနိုင်ရန်။"),
            ("Configure granular file permissions and sudo privileges", "ဖိုင်ခွင့်ပြုချက်များနှင့် sudo အခွင့်အရေးများကို လုံခြုံစွာ သတ်မှတ်ရန်။"),
            ("Automate system management with Bash shell scripting", "Bash Scripting ဖြင့် စနစ်စီမံခန့်ခွဲမှုများကို အလိုအလျောက် ဆောင်ရွက်ရန်။"),
        ],
        'lessons': [
            ("Linux CLI Navigation & Filesystem Hierarchy", "Linux Terminal အသုံးပြုနည်းနှင့် ဖိုင်စနစ်", LessonType.THEORY, 45,
             "# Linux FHS\n\nUnderstanding `/etc`, `/var`, `/bin`, and navigating directories with terminal commands."),
            ("Linux Users, Groups & POSIX File Permissions", "အသုံးပြုသူ၊ အုပ်စုနှင့် ဖိုင်ခွင့်ပြုချက်များ", LessonType.PRACTICAL, 55,
             "# File Permissions\n\n`chmod`, `chown`, `chgrp`, SUID, SGID, and Sticky bit security implications."),
            ("Bash Shell Scripting for Security Automation", "လုံခြုံရေးအတွက် Bash Scripting အလိုအလျောက်စနစ်", LessonType.PRACTICAL, 60,
             "# Bash Scripting\n\nWriting defensive health checks, cron schedules, and log parser scripts."),
        ],
        'quiz_question': ("What permission bit allows a binary to execute with the permissions of the file owner?", "ဖိုင်ပိုင်ရှင်၏ အခွင့်အရေးအတိုင်း run ခွင့်ပေးသော permission bit သည် အဘယ်နည်း?", "SUID (SetUID)", "Sticky Bit"),
        'assignment_title': ("Linux Hardening & User Audit Script", "Linux စနစ် လုံခြုံရေး စစ်ဆေးသည့် Script ရေးသားခြင်း"),
        'exam_title': ("Module 4 Formal Examination: Linux Administration", "မော်ဂျူး ၄ စာမေးပွဲ - Linux စနစ် စီမံခန့်ခွဲမှု"),
    },
    {
        'order': 5,
        'title_en': "Windows & Active Directory Security",
        'title_my': "Windows နှင့် Active Directory လုံခြုံရေး",
        'desc_en': "Windows enterprise security, Active Directory domain architecture, Kerberos authentication, and Group Policy Objects.",
        'desc_my': "Windows လုပ်ငန်းသုံး လုံခြုံရေး၊ Active Directory ဒိုမိန်း ဗိသုကာ၊ Kerberos စစ်ဆေးခြင်းနှင့် GPO မူဝါဒများ။",
        'objectives': [
            ("Understand Active Directory Domain Services (AD DS)", "Active Directory ဒိုမိန်း ဝန်ဆောင်မှုများကို နားလည်စေရန်။"),
            ("Analyze Kerberos authentication tickets and attack surfaces", "Kerberos အထောက်အထားစစ်ဆေးမှု လက်မှတ်များနှင့် တိုက်ခိုက်ခံရနိုင်ခြေကို စစ်ဆေးရန်။"),
            ("Enforce enterprise security using Group Policy (GPO)", "Group Policy (GPO) အသုံးပြု၍ လုပ်ငန်းသုံး လုံခြုံရေးမူဝါဒများ ချမှတ်ရန်။"),
        ],
        'lessons': [
            ("Windows Security Architecture & SAM Database", "Windows လုံခြုံရေး ဗိသုကာနှင့် SAM ဒေတာဘေ့စ်", LessonType.THEORY, 45,
             "# Windows Security Subsystem\n\nLSASS, SAM, NTLM hashing, and Local Security Authority architecture."),
            ("Active Directory Domain Services & Kerberos", "Active Directory နှင့် Kerberos အထောက်အထားစစ်ဆေးခြင်း", LessonType.THEORY, 50,
             "# Enterprise Active Directory\n\nDomain Controllers, TGT, TGS, Service Principal Names (SPNs), and ticketing."),
            ("Group Policy Hardening & Privilege Delegation", "Group Policy ဖြင့် လုံခြုံရေး တင်းကျပ်ခြင်း", LessonType.PRACTICAL, 60,
             "# GPO Enforcement\n\nConfiguring password complexity, disabling LLMNR/NBT-NS, and restricting local admins."),
        ],
        'quiz_question': ("Which Windows process manages local security policies and user authentication in memory?", "Windows တွင် အသုံးပြုသူ အထောက်အထား စစ်ဆေးခြင်းကို memory ထဲ၌ စီမံသော process မှာ အဘယ်နည်း?", "LSASS.exe", "Explorer.exe"),
        'assignment_title': ("Active Directory Group Policy Hardening Checklist", "Active Directory GPO လုံခြုံရေး စစ်ဆေးချက် စာရင်း"),
        'exam_title': ("Module 5 Formal Examination: Windows Enterprise Security", "မော်ဂျူး ၅ စာမေးပွဲ - Windows လုံခြုံရေး"),
    },
    {
        'order': 6,
        'title_en': "Ethical Hacking Fundamentals",
        'title_my': "ကျင့်ဝတ်ညီ ဟက်ကာအခြေခံသဘောတရားများ",
        'title_my': "Ethical Hacking အခြေခံများ",
        'desc_en': "Reconnaissance techniques, passive and active scanning, vulnerability mapping, and the cyber kill chain methodology.",
        'desc_my': "သတင်းအချက်အလက် စုံစမ်းခြင်း၊ စကင်ဖတ်စစ်ဆေးခြင်း၊ အားနည်းချက်ရှာဖွေခြင်းနှင့် Cyber Kill Chain လုပ်ငန်းစဉ်။",
        'objectives': [
            ("Execute structured OSINT reconnaissance ethically", "ကျင့်ဝတ်နှင့်အညီ OSINT သတင်းအချက်အလက် စုဆောင်းနိုင်ရန်။"),
            ("Perform port scanning and service detection with Nmap", "Nmap ဖြင့် Port နှင့် ဝန်ဆောင်မှုများကို စကင်ဖတ်စစ်ဆေးနိုင်ရန်။"),
            ("Map offensive vectors to the Lockheed Martin Cyber Kill Chain", "တိုက်ခိုက်မှု အဆင့်များကို Cyber Kill Chain နှင့် ချိတ်ဆက်နားလည်ရန်။"),
        ],
        'lessons': [
            ("Ethical Hacking Standards & Legal Frameworks", "ကျင့်ဝတ်ညီ ဟက်ကာ စံနှုန်းများနှင့် ဥပဒေရေးရာ မူဘောင်များ", LessonType.THEORY, 40,
             "# Ethics and Legalities\n\nRules of Engagement, non-disclosure agreements, and authorized scopes of work."),
            ("Reconnaissance & Open Source Intelligence (OSINT)", "သတင်းအချက်အလက် စုံစမ်းခြင်း (OSINT)", LessonType.PRACTICAL, 55,
             "# OSINT Methodologies\n\nDNS enumeration, Whois queries, search engine dorking, and certificate transparency logs."),
            ("Network Scanning & Service Enumeration with Nmap", "Nmap ဖြင့် ကွန်ရက် စကင်ဖတ်စစ်ဆေးခြင်း", LessonType.PRACTICAL, 60,
             "# Nmap Scanning\n\nTCP SYN stealth scans (`-sS`), version detection (`-sV`), and NSE security scripts."),
        ],
        'quiz_question': ("Which Nmap flag performs default NSE vulnerability and security script scans?", "Nmap တွင် အခြေခံ security script များ စကင်ဖတ်ရန် မည်သည့် flag ကို သုံးသနည်း?", "-sC", "-O"),
        'assignment_title': ("Reconnaissance & Threat Surface Mapping Report", "သတင်းအချက်အလက် စုံစမ်းခြင်း အစီရင်ခံစာ"),
        'exam_title': ("Module 6 Formal Examination: Ethical Hacking Foundations", "မော်ဂျူး ၆ စာမေးပွဲ - ဟက်ကာအခြေခံသဘောတရားများ"),
    },
    {
        'order': 7,
        'title_en': "Web Application Security",
        'title_my': "ဝဘ်အက်ပလီကေးရှင်း လုံခြုံရေး",
        'title_my': "Web Application လုံခြုံရေး",
        'desc_en': "OWASP Top 10 vulnerabilities, SQL injection, Cross-Site Scripting (XSS), CSRF, authentication flaws, and secure coding.",
        'desc_my': "OWASP Top 10 အားနည်းချက်များ၊ SQL Injection၊ XSS၊ CSRF၊ အထောက်အထား စစ်ဆေးမှု အမှားများနှင့် လုံခြုံသော ကုဒ်ရေးသားခြင်း။",
        'objectives': [
            ("Identify and mitigate OWASP Top 10 web vulnerabilities", "OWASP Top 10 အားနည်းချက်များကို ရှာဖွေပြင်ဆင်နိုင်ရန်။"),
            ("Analyze SQL Injection and implement Parameterized Queries", "SQL Injection ကို ကာကွယ်ရန် Parameterized Queries အသုံးပြုရန်။"),
            ("Implement robust Content Security Policy (CSP) against XSS", "XSS ကာကွယ်ရန် Content Security Policy (CSP) ချမှတ်ရန်။"),
        ],
        'lessons': [
            ("OWASP Top 10 Overview & HTTP Protocol Security", "OWASP Top 10 မိတ်ဆက်နှင့် HTTP လုံခြုံရေး", LessonType.THEORY, 45,
             "# OWASP Top 10\n\nCommon web application security risks, HTTP request/response headers, cookies, and tokens."),
            ("SQL Injection (SQLi) Mechanics & Defense", "SQL Injection ဖြစ်ပေါ်ပုံနှင့် ကာကွယ်နည်းများ", LessonType.PRACTICAL, 60,
             "# SQL Injection\n\nExploitation mechanics and defense via ORMs and Prepared Statements."),
            ("Cross-Site Scripting (XSS) & Modern Defenses", "Cross-Site Scripting (XSS) နှင့် ခေတ်သစ်ကာကွယ်ရေး", LessonType.PRACTICAL, 60,
             "# XSS Mitigation\n\nStored, Reflected, and DOM XSS, contextual output encoding, and CSP headers."),
        ],
        'quiz_question': ("What is the primary defense against SQL Injection vulnerabilities in web backends?", "ဝဘ် application များတွင် SQL Injection ကို ကာကွယ်ရန် အဓိက နည်းလမ်းမှာ အဘယ်နည်း?", "Parameterized Queries (Prepared Statements)", "Client-side Regex"),
        'assignment_title': ("OWASP Web Vulnerability Audit & Fix Plan", "ဝဘ်အားနည်းချက် စစ်ဆေးခြင်းနှင့် ဖြေရှင်းရေး အစီအစဉ်"),
        'exam_title': ("Module 7 Formal Examination: Web Security", "မော်ဂျူး ၇ စာမေးပွဲ - ဝဘ်လုံခြုံရေး"),
    },
    {
        'order': 8,
        'title_en': "Network Security",
        'title_my': "ကွန်ရက်လုံခြုံရေး",
        'title_my': "Network လုံခြုံရေး",
        'desc_en': "Stateful firewalls, Next-Gen Firewalls, IDS/IPS architectures (Snort/Suricata), VPN tunneling, and zero trust segmentation.",
        'desc_my': "Firewall စနစ်များ၊ IDS/IPS ကာကွယ်ရေး (Snort/Suricata)၊ VPN လုံခြုံသော လှိုဏ်ခေါင်းချိတ်ဆက်မှုနှင့် Zero Trust ကွန်ရက်ခွဲခြားခြင်း။",
        'objectives': [
            ("Configure packet filtering and stateful firewall rules", "Firewall ၏ စည်းမျဉ်းများကို စနစ်တကျ ရေးဆွဲချမှတ်နိုင်ရန်။"),
            ("Deploy Snort/Suricata Intrusion Detection Systems", "Snort/Suricata ကျူးကျော်မှု ရှာဖွေရေး စနစ်များကို တပ်ဆင်အသုံးပြုရန်။"),
            ("Design Zero Trust network micro-segmentation", "Zero Trust ကွန်ရက် ခွဲခြားခြင်း ဗိသုကာကို ရေးဆွဲနိုင်ရန်။"),
        ],
        'lessons': [
            ("Firewall Architectures: Packet Filtering to NGFW", "Firewall အမျိုးအစားများနှင့် နည်းပညာများ", LessonType.THEORY, 45,
             "# Firewalls\n\nStateless vs stateful inspection, application-layer gateways, and deep packet inspection (DPI)."),
            ("Intrusion Detection & Prevention Systems (IDS/IPS)", "ကျူးကျော်မှု ရှာဖွေရေးနှင့် တားဆီးရေး စနစ်များ", LessonType.THEORY, 50,
             "# IDS/IPS Concepts\n\nSignature-based vs anomaly-based detection with Snort/Suricata rules."),
            ("Virtual Private Networks (VPN) & Zero Trust Network Access", "VPN နှင့် Zero Trust ကွန်ရက် ချိတ်ဆက်မှု", LessonType.PRACTICAL, 55,
             "# Secure Tunneling\n\nIPsec, WireGuard, TLS VPNs, and software-defined perimeters."),
        ],
        'quiz_question': ("Which detection engine evaluates network traffic against known attack pattern signatures?", "သိရှိပြီးသား တိုက်ခိုက်မှု ပုံစံများကို စစ်ဆေးသည့် engine သည် အဘယ်နည်း?", "Signature-based IDS", "Statistical Profiler"),
        'assignment_title': ("Enterprise Firewall Rule-Base Design", "လုပ်ငန်းသုံး Firewall စည်းမျဉ်းများ ရေးဆွဲခြင်း"),
        'exam_title': ("Module 8 Formal Examination: Network Defense", "မော်ဂျူး ၈ စာမေးပွဲ - ကွန်ရက် ကာကွယ်ရေး"),
    },
    {
        'order': 9,
        'title_en': "Vulnerability Assessment & Penetration Testing",
        'title_my': "အားနည်းချက်ရှာဖွေခြင်းနှင့် ထိုးဖောက်စမ်းသပ်ခြင်း",
        'title_my': "Vulnerability Assessment နှင့် Penetration Testing",
        'desc_en': "Automated vulnerability scanning, exploit frameworks (Metasploit), privilege escalation, and executive remediation reporting.",
        'desc_my': "အလိုအလျောက် အားနည်းချက် ရှာဖွေခြင်း၊ Metasploit အသုံးချခြင်း၊ အခွင့်အရေးမြှင့်တင်ခြင်းနှင့် အစီရင်ခံစာ တင်ပြခြင်း။",
        'objectives': [
            ("Operate vulnerability scanners and prioritize CVEs with CVSS", "Vulnerability Scanner များကို အသုံးပြုပြီး CVSS ဖြင့် ဦးစားပေး သတ်မှတ်ရန်။"),
            ("Execute controlled exploits using penetration testing frameworks", "ထိန်းချုပ်ထားသော ပတ်ဝန်းကျင်တွင် စနစ်ထိုးဖောက်စမ်းသပ်မှုများ ပြုလုပ်ရန်။"),
            ("Author executive-ready penetration testing reports", "အဆင့်မြင့် အုပ်ချုပ်ရေးပိုင်းသို့ တင်ပြနိုင်မည့် Pentest အစီရင်ခံစာ ရေးသားရန်။"),
        ],
        'lessons': [
            ("Vulnerability Lifecycle & CVSS Scoring Methodology", "အားနည်းချက် သံသရာနှင့် CVSS အမှတ်ပေးစနစ်", LessonType.THEORY, 45,
             "# Vulnerability Metrics\n\nBase, temporal, and environmental scores across Common Vulnerabilities and Exposures (CVE)."),
            ("Metasploit Framework Architecture & Payloads", "Metasploit Framework ဗိသုကာနှင့် Payload များ", LessonType.PRACTICAL, 60,
             "# Metasploit Usage\n\nAuxiliary modules, exploits, staged vs non-staged Meterpreter payloads."),
            ("Privilege Escalation & Executive Pentest Reporting", "အခွင့်အရေး မြှင့်တင်ခြင်းနှင့် အစီရင်ခံစာ ရေးသားခြင်း", LessonType.PRACTICAL, 60,
             "# Reporting Deliverables\n\nTranslating technical vulnerabilities into quantifiable business impact."),
        ],
        'quiz_question': ("In CVSS v3.1, a vulnerability score of 9.0 to 10.0 is categorized under which severity rating?", "CVSS v3.1 တွင် 9.0 မှ 10.0 အမှတ်ရှိသော အားနည်းချက်ကို မည်သည့်အဆင့်အဖြစ် သတ်မှတ်သနည်း?", "Critical", "High"),
        'assignment_title': ("Penetration Testing Executive Summary & Remediation Roadmap", "ထိုးဖောက်စမ်းသပ်မှု အစီရင်ခံစာ အကျဉ်းချုပ်"),
        'exam_title': ("Module 9 Formal Examination: VAPT", "မော်ဂျူး ၉ စာမေးပွဲ - VAPT"),
    },
    {
        'order': 10,
        'title_en': "SOC, SIEM & Incident Response",
        'title_my': "SOC၊ SIEM နှင့် မတော်တဆမှု တုံ့ပြန်စီမံခြင်း",
        'title_my': "SOC, SIEM နှင့် Incident Response",
        'desc_en': "Security Operations Center tiering, Wazuh SIEM log collection, alert triage, threat hunting, and the NIST incident response lifecycle.",
        'desc_my': "SOC လုပ်ငန်းစဉ်များ၊ Wazuh SIEM ဖြင့် Log စုဆောင်းခြင်း၊ သတိပေးချက် စစ်ဆေးခြင်းနှင့် NIST အရေးပေါ် တုံ့ပြန်မှု လုပ်ငန်းစဉ်။",
        'objectives': [
            ("Understand SOC analyst workflows and tier escalation", "SOC Analyst တစ်ဦး၏ နေ့စဉ် လုပ်ငန်းစဉ်များနှင့် အဆင့်ဆင့် တင်ပြပုံကို နားလည်ရန်။"),
            ("Aggregate and analyze security telemetry in Wazuh SIEM", "Wazuh SIEM တွင် Log ဒေတာများကို စုစည်းစစ်ဆေးရန်။"),
            ("Execute the 6-phase NIST Incident Response lifecycle", "NIST အရေးပေါ် တုံ့ပြန်မှု အဆင့် ၆ ဆင့်ကို လက်တွေ့ကျင့်သုံးရန်။"),
        ],
        'lessons': [
            ("SOC Organization, Metrics & Operational Tiering", "SOC အဖွဲ့အစည်း ဖွဲ့စည်းပုံနှင့် စံသတ်မှတ်ချက်များ", LessonType.THEORY, 45,
             "# SOC Operations\n\nTier 1 Triage, Tier 2 Incident Response, MTTD (Mean Time to Detect) and MTTR."),
            ("SIEM Log Ingestion & Threat Detection with Wazuh", "Wazuh SIEM ဖြင့် Log စုဆောင်းခြင်းနှင့် ခြိမ်းခြောက်မှု ရှာဖွေခြင်း", LessonType.PRACTICAL, 60,
             "# SIEM Telemetry\n\nSyslog aggregation, Wazuh agent rules, decorrelation, and threat alerts."),
            ("The NIST Incident Response Lifecycle in Practice", "NIST အရေးပေါ် တုံ့ပြန်မှု လုပ်ငန်းစဉ် လက်တွေ့ကျင့်သုံးခြင်း", LessonType.THEORY, 50,
             "# Incident Response\n\nPreparation, Detection, Containment, Eradication, Recovery, and Lessons Learned."),
        ],
        'quiz_question': ("What is the third phase of the NIST SP 800-61 incident handling lifecycle?", "NIST SP 800-61 မတော်တဆမှု တုံ့ပြန်ရေး လုပ်ငန်းစဉ်၏ တတိယအဆင့်မှာ အဘယ်နည်း?", "Containment, Eradication, and Recovery", "Preparation"),
        'assignment_title': ("Incident Response Playbook for Ransomware Attack", "Ransomware တိုက်ခိုက်မှု တုံ့ပြန်ရေး စီမံချက် ရေးဆွဲခြင်း"),
        'exam_title': ("Module 10 Formal Examination: SOC Operations", "မော်ဂျူး ၁၀ စာမေးပွဲ - SOC နှင့် အရေးပေါ်တုံ့ပြန်မှု"),
    },
    {
        'order': 11,
        'title_en': "Digital Forensics & Malware Fundamentals",
        'title_my': "ဒစ်ဂျစ်တယ်မှုခင်းနှင့် မဲလ်ဝဲလ်အခြေခံများ",
        'title_my': "Digital Forensics နှင့် Malware အခြေခံများ",
        'desc_en': "Digital evidence preservation, chain of custody, memory acquisition, disk forensics (Autopsy), and static malware analysis.",
        'desc_my': "ဒစ်ဂျစ်တယ် သက်သေခံပစ္စည်း ထိန်းသိမ်းခြင်း၊ Memory နှင့် Disk မှုခင်းစစ်ဆေးခြင်း၊ မဲလ်ဝဲလ် သဘောတရားများ။",
        'objectives': [
            ("Preserve legal chain of custody and forensic disk integrity", "တရားဥပဒေနှင့်အညီ သက်သေခံပစ္စည်း ခိုင်လုံမှုနှင့် Chain of Custody ကို ထိန်းသိမ်းရန်။"),
            ("Acquire and analyze volatile RAM memory artifacts with Volatility", "Volatility ဖြင့် RAM Memory အတွင်းမှ သက်သေအထောက်အထားများကို စစ်ဆေးရန်။"),
            ("Perform safe static malware triage in sandbox environments", "သီးခြားလုံခြုံသော ပတ်ဝန်းကျင်တွင် Malware static triage ပြုလုပ်နိုင်ရန်။"),
        ],
        'lessons': [
            ("Digital Evidence Handling & Chain of Custody", "ဒစ်ဂျစ်တယ် သက်သေခံပစ္စည်း ကိုင်တွယ်မှုနှင့် Chain of Custody", LessonType.THEORY, 45,
             "# Forensic Integrity\n\nWrite blockers, cryptographic verification hashes, and legal admissibility standards."),
            ("Volatile Memory Analysis with Volatility Framework", "Volatility ဖြင့် Memory မှုခင်း စစ်ဆေးခြင်း", LessonType.PRACTICAL, 60,
             "# RAM Forensics\n\nProcess trees, injected DLLs, network sockets, and dumping malicious code segments."),
            ("Malware Classifications & Static Triage Essentials", "မဲလ်ဝဲလ် အမျိုးအစားများနှင့် Static Triage အခြေခံ", LessonType.PRACTICAL, 55,
             "# Malware Triage\n\nPE file headers, strings extraction, entropy calculation, and VirusTotal hash lookups."),
        ],
        'quiz_question': ("Why must physical write-blockers be used when acquiring forensic disk images?", "Forensic Disk ပုံရိပ် ဖမ်းယူရာတွင် write-blocker ကို အဘယ်ကြောင့် မဖြစ်မနေ သုံးရသနည်း?", "To prevent any alteration to the original evidence drive", "To speed up copying"),
        'assignment_title': ("Memory Dump Forensic Analysis Report", "Memory စစ်ဆေးမှု မှုခင်း အစီရင်ခံစာ"),
        'exam_title': ("Module 11 Formal Examination: Digital Forensics", "မော်ဂျူး ၁၁ စာမေးပွဲ - ဒစ်ဂျစ်တယ် မှုခင်း"),
    },
    {
        'order': 12,
        'title_en': "Python for Cyber Security",
        'title_my': "ဆိုက်ဘာလုံခြုံရေးအတွက် Python ပရိုဂရမ်မင်း",
        'title_my': "Cyber Security အတွက် Python",
        'desc_en': "Python security scripting, raw socket programming, Scapy packet manipulation, API automation, and custom tool development.",
        'desc_my': "လုံခြုံရေးအတွက် Python Script ရေးသားခြင်း၊ Socket ပရိုဂရမ်မင်း၊ Scapy ဖြင့် Packet တည်ဆောက်ခြင်းနှင့် ကိရိယာများ ဖန်တီးခြင်း။",
        'objectives': [
            ("Develop custom security utilities using Python standard libraries", "Python သုံး၍ လုံခြုံရေး စစ်ဆေးသည့် ကိုယ်ပိုင် ကိရိယာများ ရေးသားရန်။"),
            ("Craft, inject, and analyze custom network packets with Scapy", "Scapy ဖြင့် Packet များကို စိတ်ကြိုက် တည်ဆောက် ပေးပို့စစ်ဆေးရန်။"),
            ("Automate threat intelligence gathering using REST APIs", "REST API များကို အသုံးပြု၍ ခြိမ်းခြောက်မှု သတင်းအချက်အလက် စုဆောင်းမှုကို အလိုအလျောက် ဆောင်ရွက်ရန်။"),
        ],
        'lessons': [
            ("Python Core for Security Analysts", "လုံခြုံရေး ပညာရှင်များအတွက် Python အခြေခံ", LessonType.THEORY, 45,
             "# Python Security Primitives\n\nStrings, bytes, file handling, hashing, and regex pattern matching."),
            ("Socket Programming & Port Scanner Development", "Socket Programming နှင့် ကိုယ်ပိုင် Port Scanner ရေးသားခြင်း", LessonType.PRACTICAL, 60,
             "# Socket Engineering\n\nCreating TCP client/servers, non-blocking sockets, and building a multi-threaded scanner."),
            ("Packet Manipulation with Scapy & API Automation", "Scapy ဖြင့် Packet ဖန်တီးခြင်းနှင့် API အလိုအလျောက်စနစ်", LessonType.PRACTICAL, 60,
             "# Scapy & APIs\n\nForging ARP/ICMP packets, sniffing traffic, and querying VirusTotal/Shodan via Python."),
        ],
        'quiz_question': ("Which powerful Python library allows low-level packet crafting, forging, and sniffing?", "Python တွင် Packet များကို စိတ်ကြိုက် ဖန်တီးပေးပို့စစ်ဆေးနိုင်သော library သည် အဘယ်နည်း?", "Scapy", "Pandas"),
        'assignment_title': ("Custom Multi-threaded Network Security Scanner in Python", "Python ဖြင့် Port Scanner ကိရိယာ ရေးသားခြင်း"),
        'exam_title': ("Module 12 Formal Examination: Security Scripting", "မော်ဂျူး ၁၂ စာမေးပွဲ - လုံခြုံရေး Scripting"),
    },
    {
        'order': 13,
        'title_en': "Cloud Security, DevSecOps & Modern Cyber Security",
        'title_my': "Cloud လုံခြုံရေး၊ DevSecOps နှင့် ခေတ်သစ်ဆိုက်ဘာလုံခြုံရေး",
        'title_my': "Cloud Security, DevSecOps နှင့် Modern Cyber Security",
        'desc_en': "Cloud shared responsibility, AWS/Azure IAM hardening, CI/CD pipeline security (SAST/DAST), and container security basics.",
        'desc_my': "Cloud လုံခြုံရေး မျှဝေမှု မော်ဒယ်၊ IAM စီမံခန့်ခွဲမှု၊ CI/CD ပိုက်လိုင်း လုံခြုံရေး (SAST/DAST) နှင့် Container လုံခြုံရေး။",
        'objectives': [
            ("Evaluate the Cloud Shared Responsibility Model across IaaS, PaaS, and SaaS", "IaaS, PaaS, SaaS များတွင် Cloud လုံခြုံရေး တာဝန်ခွဲဝေမှု မော်ဒယ်ကို နားလည်စေရန်။"),
            ("Implement Least Privilege Identity and Access Management (IAM)", "IAM တွင် အနည်းဆုံး လိုအပ်သော အခွင့်အရေးသာ ပေးသည့် မူဝါဒ ချမှတ်ရန်။"),
            ("Embed automated security testing (SAST/DAST) into CI/CD pipelines", "CI/CD ပိုက်လိုင်းများတွင် အလိုအလျောက် လုံခြုံရေး စစ်ဆေးမှုများ ပေါင်းစပ်ထည့်သွင်းရန်။"),
        ],
        'lessons': [
            ("Cloud Shared Responsibility & Architecture", "Cloud လုံခြုံရေး တာဝန်ခွဲဝေမှုနှင့် ဗိသုကာ", LessonType.THEORY, 45,
             "# Cloud Security Models\n\nProvider vs customer security boundaries in AWS, Azure, and Google Cloud."),
            ("Cloud IAM Hardening & Policy Enforcement", "Cloud IAM လုံခြုံရေး တင်းကျပ်ခြင်း", LessonType.PRACTICAL, 55,
             "# IAM Configuration\n\nRole-based access, MFA enforcement, session tokens, and conditional policies."),
            ("DevSecOps & Automated Security Pipelines", "DevSecOps နှင့် အလိုအလျောက် လုံခြုံရေး ပိုက်လိုင်းများ", LessonType.THEORY, 50,
             "# CI/CD Pipeline Security\n\nShifting left, Static Application Security Testing (SAST), dependency scanning, and secret detection."),
        ],
        'quiz_question': ("In the Cloud Shared Responsibility Model for IaaS, who is responsible for OS patching?", "IaaS ပုံစံတွင် OS လုံခြုံရေး update များ ပြုလုပ်ရန် မည်သူ့တွင် တာဝန်ရှိသနည်း?", "The Customer", "The Cloud Provider"),
        'assignment_title': ("DevSecOps CI/CD Security Audit & Architecture Design", "DevSecOps လုံခြုံရေး ဗိသုကာ ရေးဆွဲခြင်း"),
        'exam_title': ("Module 13 Formal Examination: Cloud & DevSecOps", "မော်ဂျူး ၁၃ စာမေးပွဲ - Cloud နှင့် DevSecOps"),
    },
    {
        'order': 14,
        'title_en': "Integrated Cyber Security Laboratory & Capstone Project",
        'title_my': "ပေါင်းစပ်လက်တွေ့စမ်းသပ်ခန်းနှင့် စီမံကိန်း",
        'title_my': "Integrated Cyber Security Laboratory နှင့် Capstone Project",
        'desc_en': "Synthesizing defensive architecture, vulnerability audit, incident response, and end-to-end enterprise capstone delivery.",
        'desc_my': "သင်ကြားခဲ့သမျှ လုံခြုံရေး ဗိသုကာ၊ အားနည်းချက် စစ်ဆေးခြင်းနှင့် အရေးပေါ် တုံ့ပြန်မှုများကို ပေါင်းစပ်လက်တွေ့ အသုံးချသည့် စီမံကိန်း။",
        'objectives': [
            ("Synthesize offensive and defensive techniques across enterprise infrastructure", "လုပ်ငန်းသုံး အခြေခံအဆောက်အအုံတွင် တိုက်ခိုက်မှုနှင့် ကာကွယ်မှု ပညာရပ်များကို ပေါင်းစပ်အသုံးချရန်။"),
            ("Execute a comprehensive practical scenario investigation", "လက်တွေ့ စိန်ခေါ်မှု အခြေအနေများကို စနစ်တကျ စုံစမ်းစစ်ဆေး ဖြေရှင်းရန်။"),
            ("Deliver a professional cybersecurity capstone defense and documentation", "ဆိုက်ဘာလုံခြုံရေး စီမံကိန်း စာတမ်းနှင့် လက်တွေ့ အကောင်အထည်ဖော်မှုကို အောင်မြင်စွာ တင်ပြနိုင်ရန်။"),
        ],
        'lessons': [
            ("Capstone Project Guidelines & Scope Definition", "စီမံကိန်း လမ်းညွှန်ချက်များနှင့် နယ်ပယ် သတ်မှတ်ခြင်း", LessonType.THEORY, 45,
             "# Capstone Architecture\n\nRequirements definition, repository setup, documentation structure, and evaluation rubric."),
            ("End-to-End Enterprise Scenario Walkthrough", "လုပ်ငန်းသုံး လုံခြုံရေး အခြေအနေ လက်တွေ့ သရုပ်ပြချက်", LessonType.PRACTICAL, 75,
             "# Enterprise Defense Scenario\n\nCombining network capture, log correlation, hardening, and incident triage."),
            ("Final Project Defense Preparation & Technical Writing", "စီမံကိန်း တင်ပြမှု ပြင်ဆင်ခြင်းနှင့် နည်းပညာ အစီရင်ခံစာ ရေးသားခြင်း", LessonType.THEORY, 45,
             "# Viva & Presentation\n\nOrganizing executive presentation slides, code repositories, and technical defense."),
        ],
        'quiz_question': ("What is the primary objective of a professional capstone project defense?", "ဆိုက်ဘာလုံခြုံရေး စီမံကိန်း တင်ပြခြင်း၏ အဓိက ရည်ရွယ်ချက်မှာ အဘယ်နည်း?", "To demonstrate comprehensive mastery across theoretical and practical domains", "To write a short memo"),
        'assignment_title': ("Capstone Architecture Proposal & Scope Document", "စီမံကိန်း အဆိုပြုလွှာနှင့် နယ်ပယ် သတ်မှတ်ချက်"),
        'exam_title': ("Module 14 Formal Examination: Capstone Synthesis", "မော်ဂျူး ၁၄ စာမေးပွဲ - စီမံကိန်း ပေါင်းစပ်စစ်ဆေးခြင်း"),
    },
]


class Command(BaseCommand):
    help = "Seeds the complete 14-Module bilingual curriculum for the Certificate in Cyber Security."

    def handle(self, *args, **options):
        self.stdout.write("=== Seeding Certificate in Cyber Security Bilingual Curriculum ===")

        # 1. Ensure instructor account
        instructor = User.objects.filter(role__in=[RoleChoices.INSTRUCTOR, RoleChoices.SUPER_ADMIN]).first()
        if not instructor:
            instructor = User.objects.create_user(
                email="instructor.lead@futuretech.edu",
                username="lead_instructor",
                first_name="Lead",
                last_name="Instructor",
                role=RoleChoices.INSTRUCTOR
            )
            instructor.set_password("FutureTech2026!")
            instructor.save()

        # 2. Get or create Category
        cyber_cat, _ = CourseCategory.objects.get_or_create(
            name="Cybersecurity",
            defaults={'slug': 'cybersecurity', 'description': 'Offensive, defensive, and enterprise cybersecurity.'}
        )

        # 3. Create or update Flagship Course: CERTIFICATE IN CYBER SECURITY
        course, _ = Course.objects.get_or_create(
            slug="diploma-in-cyber-security",
            defaults={
                'title': "CERTIFICATE IN CYBER SECURITY",
                'title_en': "Certificate in Cyber Security",
                'title_my': "ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း",
                'course_type': CourseType.CERTIFICATE,
                'short_description': "A comprehensive 10-month professional cybersecurity certificate program combining theory and practical learning.",
                'description': (
                    "Welcome to the Future Tech Cyber Security Academy flagship certificate program. "
                    "This comprehensive curriculum covers 14 rigorous professional modules spanning foundational computer security, "
                    "operating systems, networking, ethical penetration testing, web defense, Wazuh SIEM telemetry, "
                    "incident response, digital forensics, and capstone engineering."
                ),
                'description_en': (
                    "Welcome to the Future Tech Cyber Security Academy flagship certificate program. "
                    "This comprehensive curriculum covers 14 rigorous professional modules spanning foundational computer security, "
                    "operating systems, networking, ethical penetration testing, web defense, Wazuh SIEM telemetry, "
                    "incident response, digital forensics, and capstone engineering."
                ),
                'description_my': (
                    "Future Tech Cyber Security Academy ၏ ပင်မ အထူးပြု လက်မှတ် သင်ရိုးညွှန်းတမ်းမှ ကြိုဆိုပါသည်။ "
                    "ဤပြည့်စုံသော သင်ရိုးတွင် အခြေခံ ကွန်ပျူတာ လုံခြုံရေး၊ ကွန်ရက်၊ Linux၊ Windows Active Directory၊ "
                    "Ethical Hacking၊ Web Security၊ SOC & Wazuh SIEM၊ Digital Forensics၊ Python နှင့် Cloud Security အပါအဝင် "
                    "မော်ဂျူး ၁၄ ခုကို သီအိုရီနှင့် လက်တွေ့ ပေါင်းစပ် သင်ကြားပေးပါသည်။"
                ),
                'level': CourseLevel.BEGINNER,
                'duration': "10 Months",
                'passing_percentage': Decimal('70.00'),
                'certificate_enabled': True,
                'is_free': True,
                'status': CourseStatus.PUBLISHED,
                'created_by': instructor,
            }
        )
        course.title = "CERTIFICATE IN CYBER SECURITY"
        course.title_en = "Certificate in Cyber Security"
        course.title_my = "ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း"
        course.course_type = CourseType.CERTIFICATE
        course.duration = "10 Months"
        course.short_description = "A comprehensive 10-month professional cybersecurity certificate program combining theory and practical learning."
        course.categories.add(cyber_cat)
        course.save()

        # 4. Assessment Weight
        AssessmentWeight.objects.get_or_create(
            course=course,
            defaults={
                'assignments_weight': Decimal('10.00'),
                'quizzes_weight': Decimal('10.00'),
                'labs_weight': Decimal('25.00'),
                'module_exams_weight': Decimal('20.00'),
                'practical_exam_weight': Decimal('15.00'),
                'final_project_weight': Decimal('20.00'),
            }
        )

        # 5. Populate all 14 Modules
        total_modules = 0
        total_lessons = 0
        total_quizzes = 0
        total_assignments = 0
        total_exams = 0

        for m_data in MODULES_SPEC:
            m_order = m_data['order']
            m_slug = f"mod-{m_order}-{slugify(m_data['title_en'])}"[:50]
            module, _ = CourseModule.objects.get_or_create(
                course=course,
                order=m_order,
                defaults={
                    'title': f"Module {m_order}: {m_data['title_en']}",
                    'title_en': f"Module {m_order}: {m_data['title_en']}",
                    'title_my': f"မော်ဂျူး {m_order}: {m_data['title_my']}",
                    'slug': m_slug,
                    'description': m_data['desc_en'],
                    'description_en': m_data['desc_en'],
                    'description_my': m_data['desc_my'],
                    'estimated_hours': 20,
                    'is_published': True,
                }
            )
            module.title_en = f"Module {m_order}: {m_data['title_en']}"
            module.title_my = f"မော်ဂျူး {m_order}: {m_data['title_my']}"
            module.description_en = m_data['desc_en']
            module.description_my = m_data['desc_my']
            module.save()
            total_modules += 1

            # Learning Objectives
            for o_order, (obj_en, obj_my) in enumerate(m_data['objectives'], start=1):
                LearningObjective.objects.get_or_create(
                    module=module,
                    order=o_order,
                    defaults={
                        'title_en': obj_en,
                        'title_my': obj_my,
                        'is_active': True,
                    }
                )

            # Lessons
            for l_order, (l_en, l_my, l_type, l_min, l_content) in enumerate(m_data['lessons'], start=1):
                l_slug = f"m{m_order}-l{l_order}-{slugify(l_en)}"[:50]
                Lesson.objects.get_or_create(
                    module=module,
                    order=l_order,
                    defaults={
                        'title': l_en,
                        'title_en': l_en,
                        'title_my': l_my,
                        'slug': l_slug,
                        'lesson_type': l_type,
                        'content': l_content,
                        'content_en': l_content,
                        'content_my': f"# {l_my}\n\n{l_content}",
                        'estimated_minutes': l_min,
                        'is_published': True,
                        'is_required': True,
                    }
                )
                total_lessons += 1

            # Quiz
            q_en, q_my, opt_correct, opt_incorrect = m_data['quiz_question']
            quiz, _ = Quiz.objects.get_or_create(
                module=module,
                defaults={
                    'course': course,
                    'title': f"{m_data['title_en']} Quiz",
                    'title_en': f"{m_data['title_en']} Quiz",
                    'title_my': f"{m_data['title_my']} စစ်ဆေးချက် စာမေးပွဲ",
                    'time_limit_minutes': 15,
                    'passing_score': 70,
                    'max_attempts': 3,
                    'randomize_questions': True,
                    'is_published': True,
                    'is_required': True,
                }
            )
            total_quizzes += 1
            if quiz.questions.count() == 0:
                q = Question.objects.create(
                    quiz=quiz,
                    order=1,
                    question_text=q_en,
                    question_en=q_en,
                    question_my=q_my,
                    question_type=QuestionType.MULTIPLE_CHOICE,
                    points=Decimal('10.00'),
                    explanation=f"Correct answer: {opt_correct}",
                    explanation_en=f"Correct answer: {opt_correct}",
                    explanation_my=f"မှန်ကန်သော အဖြေ - {opt_correct}",
                )
                QuestionOption.objects.create(question=q, option_text=opt_correct, option_en=opt_correct, option_my=opt_correct, is_correct=True, order=1)
                QuestionOption.objects.create(question=q, option_text=opt_incorrect, option_en=opt_incorrect, option_my=opt_incorrect, is_correct=False, order=2)

            # Assignment
            a_en, a_my = m_data['assignment_title']
            Assignment.objects.get_or_create(
                module=module,
                defaults={
                    'course': course,
                    'title': a_en,
                    'title_en': a_en,
                    'title_my': a_my,
                    'description': f"Practical assignment for {m_data['title_en']}.",
                    'instructions': f"Complete and upload your submission file for {a_en}.",
                    'instructions_en': f"Complete and upload your submission file for {a_en}.",
                    'instructions_my': f"{a_my} အတွက် သင်၏ အစီရင်ခံစာ သို့မဟုတ် ဖိုင်ကို တင်ပြပေးပါ။",
                    'max_score': Decimal('100.00'),
                    'passing_score': Decimal('70.00'),
                    'is_required': True,
                    'status': AssignmentStatus.PUBLISHED,
                }
            )
            total_assignments += 1

            # Module Exam
            e_en, e_my = m_data['exam_title']
            exam, _ = Exam.objects.get_or_create(
                module=module,
                exam_type=ExamType.MODULE_EXAM,
                defaults={
                    'course': course,
                    'title': e_en,
                    'title_en': e_en,
                    'title_my': e_my,
                    'description': f"Summative examination for {m_data['title_en']}.",
                    'instructions_en': "Answer all questions within the allocated time limit.",
                    'instructions_my': "သတ်မှတ်ထားသော အချိန်အတွင်း မေးခွန်းအားလုံးကို ဖြေဆိုပါ။",
                    'duration_minutes': 45,
                    'passing_score': 70,
                    'max_attempts': 2,
                    'is_published': True,
                    'is_required': True,
                }
            )
            total_exams += 1
            if exam.questions.count() == 0:
                eq = ExamQuestion.objects.create(
                    exam=exam,
                    order=1,
                    question_text=q_en,
                    question_en=q_en,
                    question_my=q_my,
                    question_type=QuestionType.MULTIPLE_CHOICE,
                    points=Decimal('20.00'),
                    explanation=f"Correct answer: {opt_correct}",
                    explanation_en=f"Correct answer: {opt_correct}",
                    explanation_my=f"မှန်ကန်သော အဖြေ - {opt_correct}",
                )
                ExamOption.objects.create(question=eq, option_text=opt_correct, option_en=opt_correct, option_my=opt_correct, is_correct=True, order=1)
                ExamOption.objects.create(question=eq, option_text=opt_incorrect, option_en=opt_incorrect, option_my=opt_incorrect, is_correct=False, order=2)

        # 6. Practical Examination (Academic assessment placeholder for Phase 1/2)
        Exam.objects.get_or_create(
            course=course,
            exam_type=ExamType.PRACTICAL,
            defaults={
                'title': "Comprehensive Practical Security Examination",
                'title_en': "Comprehensive Practical Security Examination",
                'title_my': "ဘက်စုံ လက်တွေ့ လုံခြုံရေး စာမေးပွဲကြီး",
                'description': "Academic practical evaluation testing multi-vector investigation, packet forensics, and hardening.",
                'instructions_en': "Perform analysis according to scenario instructions and submit your forensic evidence.",
                'instructions_my': "လက်တွေ့ စစ်ဆေးမှု လမ်းညွှန်ချက်များအတိုင်း ဖြေဆိုပြီး သက်သေ အထောက်အထားများ တင်သွင်းပါ။",
                'duration_minutes': 120,
                'passing_score': 70,
                'max_attempts': 2,
                'is_published': True,
                'is_required': True,
            }
        )

        # 7. Final Project (Capstone System)
        FinalProject.objects.get_or_create(
            course=course,
            defaults={
                'title': "Enterprise Cyber Security Architecture & Capstone Defense",
                'title_en': "Enterprise Cyber Security Architecture & Capstone Defense",
                'title_my': "လုပ်ငန်းသုံး ဆိုက်ဘာလုံခြုံရေး ဗိသုကာနှင့် စီမံကိန်း ကာကွယ်တင်ပြချက်",
                'description': "Comprehensive final capstone project demonstrating end-to-end defensive architecture, threat hunting, and executive reporting.",
                'description_en': "Comprehensive final capstone project demonstrating end-to-end defensive architecture, threat hunting, and executive reporting.",
                'description_my': "လက်မှတ်ရ စီမံကိန်းကြီးအဖြစ် လုပ်ငန်းသုံး လုံခြုံရေး ဗိသုကာ၊ ခြိမ်းခြောက်မှု စုံစမ်းခြင်းနှင့် အုပ်ချုပ်ရေးပိုင်းသို့ အစီရင်ခံ တင်ပြချက်များကို ရေးသား တင်ပြရမည် ဖြစ်ပါသည်။",
                'requirements': "1. Complete technical architecture report (PDF)\n2. Source code repository (Git)\n3. Executive presentation slides (PPTX)\n4. Viva defense",
                'requirements_en': "1. Complete technical architecture report (PDF)\n2. Source code repository (Git)\n3. Executive presentation slides (PPTX)\n4. Viva defense",
                'requirements_my': "၁။ နည်းပညာ ဗိသုကာ အစီရင်ခံစာ အပြည့်အစုံ (PDF)\n၂။ ပရိုဂရမ် ကုဒ် ရီပိုဆီထရီ (Git URL)\n၃။ တင်ပြမှု ဆလိုက်များ (PPTX)\n၄။ နှုတ်ဖြေ စစ်ဆေးမှု ခံယူခြင်း (Viva)",
                'max_score': Decimal('100.00'),
                'passing_score': Decimal('70.00'),
                'is_required': True,
                'is_published': True,
            }
        )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded Certificate in Cyber Security:\n"
            f"- {total_modules} Modules\n"
            f"- {total_lessons} Lessons\n"
            f"- {total_quizzes} Quizzes\n"
            f"- {total_assignments} Assignments\n"
            f"- {total_exams} Module Exams\n"
            f"- 1 Practical Examination\n"
            f"- 1 Final Capstone Project"
        ))

