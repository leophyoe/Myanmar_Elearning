from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.accounts.models import User
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabAccessType,
    LabObjective, LabHint, LabFlag, FlagType
)


class Command(BaseCommand):
    help = "Imports the LabEx Cybersecurity Labs for Beginners collection (22 labs) with full upstream attribution."

    SOURCE_NAME = "LabEx"
    SOURCE_URL = "https://github.com/labex-labs/cybersecurity-labs-for-beginners"
    SOURCE_TYPE = "OPEN_SOURCE"
    ATTRIBUTION_REQUIRED = True
    LICENSE_NAME = "Apache-2.0"

    # Category definitions
    CATEGORY_MAPPING = {
        "password-security": ("Ethical Hacking / Password Security", "ethical-hacking-password-security", "key", "Password cracking, dictionary attacks, and credential auditing."),
        "reconnaissance": ("Network Security / Reconnaissance", "network-security-reconnaissance", "scan", "Port scanning, service discovery, and network enumeration with Nmap."),
        "cryptography": ("Cryptography", "cryptography", "shield", "Symmetric encryption, cipher algorithms, and OpenSSL cryptography."),
        "networking": ("Networking", "networking", "network", "Socket programming, raw network data transmission, and Netcat communication."),
        "network-analysis": ("Network Analysis", "network-analysis", "activity", "Deep packet inspection, traffic carving, and Wireshark dissection."),
        "host-security": ("Host Security / File Integrity", "host-security-file-integrity", "file-text", "Host monitoring, baseline auditing, and file integrity with Tripwire."),
        "network-scanning": ("Network Scanning", "network-scanning", "radio", "High-speed asynchronous subnet port scanning with Masscan."),
        "steganography": ("Digital Forensics / Steganography", "digital-forensics-steganography", "eye-off", "Hiding and carving covert payload files with Steghide."),
        "web-assessment": ("Web Security / Vulnerability Assessment", "web-security-vulnerability-assessment", "globe", "Web server misconfiguration and vulnerability auditing with Nikto."),
        "auth-defense": ("Authentication / Defensive Security", "authentication-defensive-security", "lock", "Threat modeling, authentication hardening, and MFA/TOTP integration."),
        "defensive-security": ("Defensive Security", "defensive-security", "shield-check", "Defense-in-depth architecture, local firewalling, and secret protection."),
    }

    # Complete 22 Labs Catalog Definition
    LABS_DATA = [
        {
            "order": 1,
            "title": "Using Hydra to Crack Passwords",
            "slug": "using-hydra-to-crack-passwords",
            "cat_key": "password-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Learn the mechanics of dictionary-based online password auditing against network authentication daemons using THC-Hydra.",
            "objectives": [
                ("Analyze Hydra command-line syntax and protocols", 20),
                ("Execute dictionary attack against target authentication service", 30),
            ],
            "hint": "Specify the username with -l and wordlist with -P followed by target protocol (e.g., hydra -l admin -P /usr/share/wordlists/rockyou.txt target ssh).",
            "flag": "FTACK{hydra_dictionary_attack_success}",
        },
        {
            "order": 2,
            "title": "Cracking a Specific User Account",
            "slug": "cracking-a-specific-user-account",
            "cat_key": "password-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Perform targeted password recovery against a single known username using focused credential wordlists and Hydra.",
            "objectives": [
                ("Identify target user identifier and authentication endpoint", 20),
                ("Conduct targeted dictionary attack to recover user credentials", 30),
            ],
            "hint": "When targeting a specific user, use lowercase -l with the exact username to focus all dictionary attempts on that account.",
            "flag": "FTACK{user_account_hydra_cracked}",
        },
        {
            "order": 3,
            "title": "Network Scanning with Nmap",
            "slug": "network-scanning-with-nmap",
            "cat_key": "reconnaissance",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Discover open ports, identify running network services, and perform host detection using Nmap.",
            "objectives": [
                ("Perform TCP SYN port scan across standard ports", 20),
                ("Enumerate service banners and exact daemon versions", 30),
            ],
            "hint": "Use nmap -sV -sC -T4 <target-ip> to run service version detection and default NSE scripts.",
            "flag": "FTACK{nmap_port_recon_mastered}",
        },
        {
            "order": 4,
            "title": "Scanning Subnet with Nmap",
            "slug": "scanning-subnet-with-nmap",
            "cat_key": "reconnaissance",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Discover live network devices and map IP address space across an entire CIDR subnet range using Nmap sweep techniques.",
            "objectives": [
                ("Execute ICMP and ARP ping sweeps across /24 subnet", 20),
                ("Identify and document all active network hosts", 30),
            ],
            "hint": "The -sn flag performs a ping sweep without probing port numbers, rapidly identifying live subnet nodes (nmap -sn 192.168.1.0/24).",
            "flag": "FTACK{nmap_subnet_sweep_complete}",
        },
        {
            "order": 5,
            "title": "Introduction to Encryption with OpenSSL",
            "slug": "introduction-to-encryption-with-openssl",
            "cat_key": "cryptography",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Understand symmetric cipher mechanics, initialization vectors (IVs), and data confidentiality by encrypting files with OpenSSL.",
            "objectives": [
                ("Encrypt plaintext file using AES-256-CBC cipher", 25),
                ("Verify ciphertext randomness and decrypt back to plaintext", 25),
            ],
            "hint": "Use openssl enc -aes-256-cbc -salt -in file.txt -out file.enc -k <password> to encrypt.",
            "flag": "FTACK{openssl_aes_symmetric_crypto}",
        },
        {
            "order": 6,
            "title": "Decrypting Top Secret Document",
            "slug": "decrypting-top-secret-document",
            "cat_key": "cryptography",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Practice cryptographic recovery operations by decrypting an intercepted confidential document using OpenSSL command-line tools.",
            "objectives": [
                ("Inspect encrypted payload format and determine cipher mode", 20),
                ("Decrypt confidential document using target key parameter", 30),
            ],
            "hint": "Use openssl enc -d -aes-256-cbc -in secret.enc -out secret.txt -k <key> to decrypt.",
            "flag": "FTACK{top_secret_document_decrypted}",
        },
        {
            "order": 7,
            "title": "Using Netcat for Simple Network Communication",
            "slug": "using-netcat-for-simple-network-communication",
            "cat_key": "networking",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Deploy Netcat ('Swiss Army Knife of TCP/IP') to establish point-to-point network connections and transmit raw data streams.",
            "objectives": [
                ("Establish raw TCP client connection to remote port", 20),
                ("Send and receive bidirectional data packets over socket", 30),
            ],
            "hint": "Connect as client using nc <host> <port>, or listen as server with nc -lvnp <port>.",
            "flag": "FTACK{netcat_raw_socket_connection}",
        },
        {
            "order": 8,
            "title": "Receive Messages Using Netcat",
            "slug": "receive-messages-using-netcat",
            "cat_key": "networking",
            "difficulty": LabDifficulty.MEDIUM,
            "type": LabType.CHALLENGE,
            "points": 75,
            "estimated_minutes": 45,
            "description": "Configure an unprivileged Netcat listener daemon, handle inbound TCP socket transmissions, and redirect network payloads to disk.",
            "objectives": [
                ("Bind listening socket to high port on loopback interface", 35),
                ("Capture incoming transmitted network message into file", 40),
            ],
            "hint": "Redirect the incoming stream to a local file using redirection: nc -lvnp 4444 > received_data.txt.",
            "flag": "FTACK{netcat_listen_message_captured}",
        },
        {
            "order": 9,
            "title": "Network Analysis with Wireshark",
            "slug": "network-analysis-with-wireshark",
            "cat_key": "network-analysis",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Capture live network traffic, dissect protocol layers (Ethernet, IP, TCP, UDP), and inspect packet payload bytes using Wireshark.",
            "objectives": [
                ("Capture live network packets on active network interface", 20),
                ("Inspect TCP three-way handshake flags and payload data", 30),
            ],
            "hint": "Analyze SYN, SYN-ACK, and ACK sequence numbers in the TCP header flags panel.",
            "flag": "FTACK{wireshark_packet_dissection}",
        },
        {
            "order": 10,
            "title": "Capture Google Traffic with Wireshark",
            "slug": "capture-google-traffic-with-wireshark",
            "cat_key": "network-analysis",
            "difficulty": LabDifficulty.MEDIUM,
            "type": LabType.CHALLENGE,
            "points": 75,
            "estimated_minutes": 45,
            "description": "Capture DNS resolution queries, inspect TLS 1.3 Client Hello handshakes, and isolate outbound Google web requests.",
            "objectives": [
                ("Filter DNS queries matching google.com domain names", 35),
                ("Analyze Server Name Indication (SNI) in Client Hello packet", 40),
            ],
            "hint": "Use Wireshark display filter: dns.qry.name contains 'google' or tls.handshake.extensions_server_name contains 'google'.",
            "flag": "FTACK{wireshark_google_tls_captured}",
        },
        {
            "order": 11,
            "title": "Brute Force SSH in Hydra",
            "slug": "brute-force-ssh-in-hydra",
            "cat_key": "password-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Audit an SSH server for weak passwords, handle protocol connection limits, and configure thread counts safely with Hydra.",
            "objectives": [
                ("Configure Hydra SSH module parameters and connection limits", 20),
                ("Recover administrative SSH password credentials", 30),
            ],
            "hint": "Use the ssh protocol module with -t 4 to limit concurrent connections to avoid triggering remote SSH server rate limits.",
            "flag": "FTACK{hydra_ssh_bruteforce_pwned}",
        },
        {
            "order": 12,
            "title": "Scan Vulnerabilities in Nmap",
            "slug": "scan-vulnerabilities-in-nmap",
            "cat_key": "reconnaissance",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Leverage Nmap Scripting Engine (NSE) vulnerability categories (vuln, safe, default) to detect known unpatched CVEs on target daemons.",
            "objectives": [
                ("Run NSE vulnerability scripts against open service ports", 20),
                ("Identify unpatched security flaws and associated CVE identifiers", 30),
            ],
            "hint": "Run nmap --script vuln <target-ip> to execute the automated vulnerability scanning script category.",
            "flag": "FTACK{nmap_nse_vuln_detection}",
        },
        {
            "order": 13,
            "title": "Encrypt Files in OpenSSL",
            "slug": "encrypt-files-in-openssl",
            "cat_key": "cryptography",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Master password-based key derivation (PBKDF2) and secure file at rest encryption workflows using the OpenSSL CLI suite.",
            "objectives": [
                ("Generate cryptographic salt and encrypt sensitive file", 25),
                ("Verify encryption integrity and test tamper resilience", 25),
            ],
            "hint": "Always use the -pbkdf2 flag with OpenSSL 1.1.1+ to ensure modern key derivation instead of legacy weak key hashing.",
            "flag": "FTACK{openssl_file_crypto_secured}",
        },
        {
            "order": 14,
            "title": "Filter Traffic in Wireshark",
            "slug": "filter-traffic-in-wireshark",
            "cat_key": "network-analysis",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Isolate security incidents in large PCAP files using Wireshark display filter syntax, boolean operators, and protocol expressions.",
            "objectives": [
                ("Apply IP address and port-based display filters", 20),
                ("Construct compound boolean filters (and, or, not) to isolate attack traffic", 30),
            ],
            "hint": "Filter syntax example: ip.addr == 10.10.10.5 && tcp.port == 80 && http.request.method == 'POST'.",
            "flag": "FTACK{wireshark_display_filter_expert}",
        },
        {
            "order": 15,
            "title": "Crack ZIP Passwords in John the Ripper",
            "slug": "crack-zip-passwords-in-john-the-ripper",
            "cat_key": "password-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Extract password hashes from encrypted ZIP archives using zip2john and crack password hashes using John the Ripper.",
            "objectives": [
                ("Extract PKZIP/WinZip hash string using zip2john utility", 20),
                ("Execute dictionary attack with John the Ripper to recover archive key", 30),
            ],
            "hint": "First run zip2john encrypted.zip > hash.txt, then crack using john --wordlist=/path/to/wordlist.txt hash.txt.",
            "flag": "FTACK{john_zip_hash_cracked}",
        },
        {
            "order": 16,
            "title": "Monitor Files in Tripwire",
            "slug": "monitor-files-in-tripwire",
            "cat_key": "host-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Configure host-based File Integrity Monitoring (FIM) with Tripwire to establish baseline cryptographic hashes and detect tampering.",
            "objectives": [
                ("Initialize Tripwire database baseline of critical system files", 20),
                ("Simulate unauthorized modification and detect anomaly in integrity report", 30),
            ],
            "hint": "Tripwire compares SHA-256 hashes of system binaries (/bin, /etc) against an encrypted baseline database.",
            "flag": "FTACK{tripwire_fim_tamper_detected}",
        },
        {
            "order": 17,
            "title": "Scan Ports with Masscan",
            "slug": "scan-ports-with-masscan",
            "cat_key": "network-scanning",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Operate Masscan, an ultra-high-speed asynchronous TCP port scanner, to scan thousands of ports per second safely.",
            "objectives": [
                ("Configure rate limiting to prevent network saturation", 20),
                ("Scan multiple subnet ports asynchronously and parse results", 30),
            ],
            "hint": "Set transmission rate using --rate (e.g. masscan -p80,443 192.168.1.0/24 --rate=1000).",
            "flag": "FTACK{masscan_async_scanner_speed}",
        },
        {
            "order": 18,
            "title": "Hide Data in Steghide",
            "slug": "hide-data-in-steghide",
            "cat_key": "steganography",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Understand digital steganography by embedding sensitive secret text inside cover image/audio files using Steghide.",
            "objectives": [
                ("Embed encrypted secret text inside JPEG cover image", 25),
                ("Extract hidden payload from steganographic carrier file", 25),
            ],
            "hint": "Embed with: steghide embed -cf image.jpg -ef secret.txt. Extract with: steghide extract -sf image.jpg.",
            "flag": "FTACK{steghide_covert_data_revealed}",
        },
        {
            "order": 19,
            "title": "Scan Web Servers in Nikto",
            "slug": "scan-web-servers-in-nikto",
            "cat_key": "web-assessment",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Perform web server reconnaissance with Nikto to identify dangerous files, outdated server software, and misconfigured HTTP headers.",
            "objectives": [
                ("Run Nikto scan against web server target", 20),
                ("Analyze findings (missing security headers, outdated software, exposed paths)", 30),
            ],
            "hint": "Run nikto -h http://<target-ip> to audit server configurations and indexable backup files.",
            "flag": "FTACK{nikto_web_vuln_scanned}",
        },
        {
            "order": 20,
            "title": "Map Threats in a Simple Login Service",
            "slug": "map-threats-in-a-simple-login-service",
            "cat_key": "auth-defense",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Apply the STRIDE threat modeling framework to analyze an authentication service and identify spoofing, tampering, and denial-of-service risks.",
            "objectives": [
                ("Deconstruct login architecture and data flow diagram", 20),
                ("Map vulnerabilities against STRIDE categories and propose mitigations", 30),
            ],
            "hint": "STRIDE categories: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege.",
            "flag": "FTACK{threat_modeling_stride_login}",
        },
        {
            "order": 21,
            "title": "Add a Second Factor to a Login Script",
            "slug": "add-a-second-factor-to-a-login-script",
            "cat_key": "auth-defense",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Strengthen password-only authentication by implementing Time-Based One-Time Password (TOTP, RFC 6238) multi-factor authentication.",
            "objectives": [
                ("Generate shared secret seed and QR code setup for authenticator app", 20),
                ("Verify time-synchronized 6-digit TOTP tokens during login verification", 30),
            ],
            "hint": "TOTP calculates HMAC-SHA1 over the current 30-second Unix time counter and truncates the hash to 6 digits.",
            "flag": "FTACK{mfa_totp_second_factor_added}",
        },
        {
            "order": 22,
            "title": "Layer Defenses Around a Local Secret Service",
            "slug": "layer-defenses-around-a-local-secret-service",
            "cat_key": "defensive-security",
            "difficulty": LabDifficulty.BEGINNER,
            "type": LabType.GUIDED,
            "points": 50,
            "estimated_minutes": 30,
            "description": "Implement defense-in-depth principles by combining host firewalls (iptables), API access tokens, and rate limiters around a sensitive service.",
            "objectives": [
                ("Enforce IP-based network filtering rules on incoming traffic", 20),
                ("Implement application-level authentication tokens and rate limiting", 30),
            ],
            "hint": "Defense-in-depth ensures that if one security layer fails (e.g. firewall), inner layers (tokens, rate limits) prevent compromise.",
            "flag": "FTACK{defense_in_depth_layered_shield}",
        },
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Importing LabEx Beginner Cybersecurity Labs Collection ==="))

        admin_user = User.objects.filter(is_staff=True).first()
        if not admin_user:
            admin_user = User.objects.create_user(
                email="admin@futuretech.edu",
                username="academy_admin",
                is_staff=True,
                is_superuser=True
            )

        # 1. Ensure all Lab Categories exist
        categories = {}
        for cat_key, (name, slug, icon, desc) in self.CATEGORY_MAPPING.items():
            cat, _ = LabCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "description": desc,
                }
            )
            categories[cat_key] = cat

        # 2. Import / Update all 22 labs idempotently
        created_count = 0
        updated_count = 0

        for item in self.LABS_DATA:
            category = categories[item["cat_key"]]
            lab, created = Lab.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["title"],
                    "category": category,
                    "difficulty": item["difficulty"],
                    "type": item["type"],
                    "short_description": item["description"][:500],
                    "description": item["description"],
                    "points": item["points"],
                    "estimated_minutes": item["estimated_minutes"],
                    "docker_image": "futuretech/linux-base:latest",
                    "access_type": LabAccessType.TERMINAL,
                    "terminal_enabled": True,
                    "web_access_enabled": False,
                    "max_runtime_minutes": 60,
                    "cpu_limit": Decimal("1.0"),
                    "memory_limit_mb": 512,
                    "storage_limit_mb": 1024,
                    "process_limit": 100,
                    "source_name": self.SOURCE_NAME,
                    "source_url": self.SOURCE_URL,
                    "source_type": self.SOURCE_TYPE,
                    "attribution_required": self.ATTRIBUTION_REQUIRED,
                    "license_name": self.LICENSE_NAME,
                    "display_order": 100 + item["order"],
                    "is_published": True,
                    "created_by": admin_user,
                }
            )

            if not created:
                # Update metadata while strictly preserving student progress & existing IDs
                lab.name = item["title"]
                lab.category = category
                lab.difficulty = item["difficulty"]
                lab.type = item["type"]
                lab.short_description = item["description"][:500]
                lab.description = item["description"]
                lab.points = item["points"]
                lab.estimated_minutes = item["estimated_minutes"]
                lab.source_name = self.SOURCE_NAME
                lab.source_url = self.SOURCE_URL
                lab.source_type = self.SOURCE_TYPE
                lab.attribution_required = self.ATTRIBUTION_REQUIRED
                lab.license_name = self.LICENSE_NAME
                lab.display_order = 100 + item["order"]
                lab.is_published = True
                lab.save()
                updated_count += 1
            else:
                created_count += 1

            # Seed Objectives
            for idx, (obj_title, obj_pts) in enumerate(item["objectives"], start=1):
                LabObjective.objects.get_or_create(
                    lab=lab,
                    order=idx,
                    defaults={
                        "title": obj_title,
                        "points": obj_pts,
                        "required": True,
                    }
                )

            # Seed Hint
            LabHint.objects.get_or_create(
                lab=lab,
                order=1,
                defaults={
                    "hint_text": item["hint"],
                    "penalty_percent": 10,
                }
            )

            # Seed Static Flag
            LabFlag.objects.get_or_create(
                lab=lab,
                defaults={
                    "flag_type": FlagType.STATIC_FLAG,
                    "static_flag": item["flag"],
                    "points": item["points"],
                }
            )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully processed {len(self.LABS_DATA)} LabEx labs: "
            f"{created_count} created, {updated_count} updated."
        ))
        self.stdout.write(self.style.NOTICE(
            f"Attribution: Originating from {self.SOURCE_NAME} under {self.LICENSE_NAME} license "
            f"({self.SOURCE_URL})."
        ))

