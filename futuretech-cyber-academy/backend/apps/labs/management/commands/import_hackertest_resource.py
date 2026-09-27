from django.core.management.base import BaseCommand
from apps.labs.models import (
    ChallengeCategory, Challenge, ExternalResource, LabDifficulty
)


class Command(BaseCommand):
    help = "Imports HackerTest.net as an External Resource and creates original Future Tech Security Challenges."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Importing HackerTest External Resource & Future Tech Challenges ==="))

        # 1. Register HackerTest.net as ExternalResource
        resource, r_created = ExternalResource.objects.get_or_create(
            slug="hackertest",
            defaults={
                "name": "HackerTest",
                "url": "https://www.hackertest.net/",
                "source_type": "EXTERNAL_RESOURCE",
                "attribution": "HackerTest.net",
                "description": (
                    "External cybersecurity challenge resource. Test your web security, client-side script "
                    "analysis, and reconnaissance skills across 20 progressive challenge levels on the official "
                    "HackerTest platform."
                ),
                "is_active": True,
                "display_order": 1,
                "tags": "Cyber Security Fundamentals, Ethical Hacking, Web Security, Security Challenges",
            }
        )

        if not r_created:
            resource.name = "HackerTest"
            resource.url = "https://www.hackertest.net/"
            resource.source_type = "EXTERNAL_RESOURCE"
            resource.attribution = "HackerTest.net"
            resource.description = (
                "External cybersecurity challenge resource. Test your web security, client-side script "
                "analysis, and reconnaissance skills across 20 progressive challenge levels on the official "
                "HackerTest platform."
            )
            resource.is_active = True
            resource.display_order = 1
            resource.tags = "Cyber Security Fundamentals, Ethical Hacking, Web Security, Security Challenges"
            resource.save()
            self.stdout.write(self.style.SUCCESS("Updated ExternalResource: HackerTest"))
        else:
            self.stdout.write(self.style.SUCCESS("Created ExternalResource: HackerTest"))

        # 2. Create Future Tech Security Challenges Category
        ft_cat, _ = ChallengeCategory.objects.get_or_create(
            slug="future-tech-security-challenges",
            defaults={
                "name": "Future Tech Security Challenges",
                "icon": "shield",
                "description": (
                    "Original cybersecurity challenges designed by Future Tech Cyber Security Academy "
                    "spanning web exploitation, cryptography, network packet carving, authentication, "
                    "and digital forensics."
                ),
            }
        )

        # Link HackerTest category if not set
        if not resource.category:
            resource.category = ft_cat
            resource.save()

        # 3. Seed 8 Original Future Tech Security Challenges
        ORIGINAL_CHALLENGES = [
            {
                "title": "FutureTech Web Header Analysis",
                "slug": "futuretech-web-header-analysis",
                "difficulty": LabDifficulty.BEGINNER,
                "points": 50,
                "description": (
                    "Modern web applications rely on defensive HTTP security headers to mitigate cross-site "
                    "scripting and framing attacks. Inspect the mock application security headers "
                    "(CSP, X-Frame-Options, Strict-Transport-Security) to find the validation token."
                ),
                "instructions": (
                    "Category: Web Security\n\n"
                    "Analyze the response headers for the simulated corporate web server. The verification "
                    "token is embedded within a custom security directive."
                ),
                "flag": "FTACK{csp_header_security_audited}",
            },
            {
                "title": "FutureTech SUID Inspector",
                "slug": "futuretech-suid-inspector",
                "difficulty": LabDifficulty.EASY,
                "points": 60,
                "description": (
                    "SetUID binaries allow unprivileged users to execute code with the permissions of the file owner. "
                    "Audit the system binary directory for misconfigured elevated executables."
                ),
                "instructions": (
                    "Category: Linux Security\n\n"
                    "Construct a find query looking for permissions mode -4000. Examine the target utility to locate the flag."
                ),
                "flag": "FTACK{suid_privilege_audit_complete}",
            },
            {
                "title": "FutureTech PCAP Packet Stream",
                "slug": "futuretech-pcap-packet-stream",
                "difficulty": LabDifficulty.MEDIUM,
                "points": 70,
                "description": (
                    "Sensitive data was transmitted over an unencrypted TCP session. Follow the TCP stream and carve "
                    "out the base64 exfiltration token."
                ),
                "instructions": (
                    "Category: Networking\n\n"
                    "Examine packet captures in Wireshark or tshark. Filter for TCP port 4444 and decode the payload."
                ),
                "flag": "FTACK{tcp_stream_exfiltration_carved}",
            },
            {
                "title": "FutureTech XOR Keybreaker",
                "slug": "futuretech-xor-keybreaker",
                "difficulty": LabDifficulty.MEDIUM,
                "points": 75,
                "description": (
                    "A proprietary cipher uses single-byte XOR encryption to conceal confidential telemetry. "
                    "Analyze the byte frequency and recover the single-byte key to decrypt the ciphertext."
                ),
                "instructions": (
                    "Category: Cryptography\n\n"
                    "Perform frequency analysis or iterate keys 0x00 to 0xFF. The plaintext begins with 'FTACK{'."
                ),
                "flag": "FTACK{single_byte_xor_broken}",
            },
            {
                "title": "FutureTech JWT Algorithm Tampering",
                "slug": "futuretech-jwt-algorithm-tampering",
                "difficulty": LabDifficulty.MEDIUM,
                "points": 80,
                "description": (
                    "Insecure JSON Web Token verification can fall victim to algorithm confusion where signature "
                    "verification is bypassed by switching 'alg' to 'none'."
                ),
                "instructions": (
                    "Category: Authentication\n\n"
                    "Review the token structure (header.payload.signature) and identify why unsigned tokens could pass naive verification."
                ),
                "flag": "FTACK{jwt_none_alg_defense_hardened}",
            },
            {
                "title": "FutureTech Memory String Carving",
                "slug": "futuretech-memory-string-carving",
                "difficulty": LabDifficulty.HARD,
                "points": 85,
                "description": (
                    "An ephemeral process created an in-memory encryption key before terminating. "
                    "Carve the memory dump artifact to locate the residual credential string."
                ),
                "instructions": (
                    "Category: Forensics\n\n"
                    "Use strings utility with UTF-8 and UTF-16 encoding switches (-e l) against the process memory image."
                ),
                "flag": "FTACK{memory_dump_string_carved}",
            },
            {
                "title": "FutureTech Python Sandbox Jailbreak",
                "slug": "futuretech-python-sandbox-jailbreak",
                "difficulty": LabDifficulty.HARD,
                "points": 90,
                "description": (
                    "A restricted Python execution sandbox attempted to prevent command execution by sanitizing "
                    "`os` and `eval`. Audit the AST validator and implement secure execution boundaries."
                ),
                "instructions": (
                    "Category: Programming & Secure Coding\n\n"
                    "Analyze how object introspection (__subclasses__) can traverse class hierarchies and identify defense-in-depth mitigations."
                ),
                "flag": "FTACK{python_ast_sandbox_secured}",
            },
            {
                "title": "FutureTech CIA Triad Threat Classifier",
                "slug": "futuretech-cia-triad-classifier",
                "difficulty": LabDifficulty.BEGINNER,
                "points": 50,
                "description": (
                    "Information assurance requires mapping incident scenarios to Confidentiality, Integrity, "
                    "or Availability impacts under the STRIDE threat model."
                ),
                "instructions": (
                    "Category: Security Fundamentals\n\n"
                    "Review the three intrusion telemetry scenarios and classify each against the CIA triad pillars."
                ),
                "flag": "FTACK{cia_triad_threat_model_mastered}",
            },
        ]

        ch_created_count = 0
        ch_updated_count = 0

        for item in ORIGINAL_CHALLENGES:
            ch, created = Challenge.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "category": ft_cat,
                    "difficulty": item["difficulty"],
                    "points": item["points"],
                    "description": item["description"],
                    "instructions": item["instructions"],
                    "flag": item["flag"],
                    "is_active": True,
                }
            )

            if not created:
                ch.title = item["title"]
                ch.category = ft_cat
                ch.difficulty = item["difficulty"]
                ch.points = item["points"]
                ch.description = item["description"]
                ch.instructions = item["instructions"]
                ch.flag = item["flag"]
                ch.is_active = True
                ch.save()
                ch_updated_count += 1
            else:
                ch_created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully processed Future Tech Security Challenges: "
            f"{ch_created_count} created, {ch_updated_count} updated."
        ))
        self.stdout.write(self.style.NOTICE(
            "HackerTest is integrated as an EXTERNAL_RESOURCE link to https://www.hackertest.net/ "
            "without copying or scraping proprietary third-party assets."
        ))

