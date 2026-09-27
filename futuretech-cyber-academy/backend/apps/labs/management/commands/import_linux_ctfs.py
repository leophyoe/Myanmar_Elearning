from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.accounts.models import User
from apps.courses.models import Course, CourseModule
from apps.labs.models import (
    LabCategory, Lab, LabDifficulty, LabType, LabAccessType,
    LabObjective, LabHint, LabFlag, FlagType,
    ChallengeCategory, Challenge
)


class Command(BaseCommand):
    help = "Imports the LearnToCloud Linux CTFs collection (19 labs & challenges) with full upstream attribution."

    SOURCE_NAME = "LearnToCloud"
    SOURCE_URL = "https://github.com/learntocloud/linux-ctfs"
    SOURCE_TYPE = "OPEN_SOURCE"
    ATTRIBUTION_REQUIRED = True
    LICENSE_NAME = "MIT"

    # 10 Linux Categories mapped to (Name, Slug, Icon, Description)
    CATEGORY_MAPPING = {
        "linux-fundamentals": (
            "Linux Fundamentals",
            "linux-fundamentals",
            "terminal",
            "Core terminal navigation, basic file interactions, and shell environment concepts."
        ),
        "linux-commands": (
            "Linux Commands",
            "linux-commands",
            "terminal",
            "Essential command-line utilities, pipelines, search commands, and text stream manipulation."
        ),
        "linux-filesystem": (
            "Linux Filesystem",
            "linux-filesystem",
            "folder",
            "Linux Filesystem Hierarchy Standard (FHS), directory trees, inodes, and symlink structures."
        ),
        "linux-permissions": (
            "Linux Permissions",
            "linux-permissions",
            "lock",
            "POSIX discretionary access controls, chmod octal modes, SUID/SGID bits, and privilege auditing."
        ),
        "linux-users-groups": (
            "Linux Users & Groups",
            "linux-users-groups",
            "users",
            "User account management, UIDs/GIDs, /etc/passwd and group file auditing, and profile configs."
        ),
        "linux-processes": (
            "Linux Processes",
            "linux-processes",
            "cpu",
            "Process monitoring, background jobs, cron scheduling, and /proc virtual filesystem inspection."
        ),
        "linux-networking": (
            "Linux Networking",
            "linux-networking",
            "network",
            "Socket analysis, listening ports, DNS resolution, systemd-resolved, and packet capture."
        ),
        "linux-services": (
            "Linux Services",
            "linux-services",
            "server",
            "Systemd daemons, service discovery, web server configuration, and port administration."
        ),
        "linux-security": (
            "Linux Security",
            "linux-security",
            "shield",
            "SSH key auditing, defense hardening, authentication security, and shell history hygiene."
        ),
        "linux-troubleshooting": (
            "Linux Troubleshooting",
            "linux-troubleshooting",
            "tool",
            "System diagnostic triage, disk image loopback mounting, log analysis, and file carving."
        ),
    }

    # Complete 19 LearnToCloud Challenges & Labs (0 to 18)
    CHALLENGES_DATA = [
        {
            "order": 0,
            "title": "Example Challenge",
            "slug": "ltc-00-example-challenge",
            "cat_key": "linux-fundamentals",
            "difficulty": LabDifficulty.BEGINNER,
            "points": 50,
            "estimated_minutes": 15,
            "description": "Practice Linux CTF flag verification mechanics. Execute the verify CLI utility to test flag submission connectivity.",
            "objectives": [
                ("Verify system environment and access verify tool", 20),
                ("Submit tutorial test flag to confirm scoring connectivity", 30),
            ],
            "hint": "Run: verify 0 CTF{example} inside the terminal.",
            "flag": "CTF{example}",
            "module_order": 2,
        },
        {
            "order": 1,
            "title": "Hidden File Discovery",
            "slug": "ltc-01-the-hidden-file",
            "cat_key": "linux-filesystem",
            "difficulty": LabDifficulty.BEGINNER,
            "points": 50,
            "estimated_minutes": 20,
            "description": "Hidden files in Unix filesystems start with a dot (.). Explore the ctf_challenges directory and uncover the hidden flag file.",
            "objectives": [
                ("Inspect directory contents including hidden dotfiles using ls -la", 20),
                ("Read and extract the hidden flag file contents", 30),
            ],
            "hint": "Hidden files in Linux start with a dot. Try 'ls -la' in the ctf_challenges directory.",
            "flag": "CTF{hidden_files_found}",
            "module_order": 2,
        },
        {
            "order": 2,
            "title": "The Secret File",
            "slug": "ltc-02-the-secret-file",
            "cat_key": "linux-commands",
            "difficulty": LabDifficulty.BEGINNER,
            "points": 50,
            "estimated_minutes": 20,
            "description": "Locate a file containing 'secret' in its filename located somewhere under your home directory hierarchy.",
            "objectives": [
                ("Construct recursive search queries with the find command", 20),
                ("Locate the target secret file and extract the flag", 30),
            ],
            "hint": "Use the 'find' command to search for files. Try: find ~ -name '*secret*' 2>/dev/null",
            "flag": "CTF{file_search_master}",
            "module_order": 4,
        },
        {
            "order": 3,
            "title": "Log Analysis",
            "slug": "ltc-03-the-largest-log",
            "cat_key": "linux-troubleshooting",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "High-volume application logs frequently conceal security indicators. Find and read an unusually large log file in /var/log.",
            "objectives": [
                ("Analyze file sizes in /var/log using sort and size inspection", 35),
                ("Inspect the identified log file using tail or grep to extract the flag", 40),
            ],
            "hint": "Large log files can hide secrets. Check /var/log and use 'tail' or 'ls -lhS' to sort by size.",
            "flag": "CTF{log_analysis_expert}",
            "module_order": 4,
        },
        {
            "order": 4,
            "title": "User Investigation",
            "slug": "ltc-04-the-user-detective",
            "cat_key": "linux-users-groups",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Audit system user accounts. Another user configured on the host holds a hidden flag in their login profile or configuration files.",
            "objectives": [
                ("Enumerate system users from /etc/passwd and inspect UID allocations", 35),
                ("Audit home directories and login dotfiles to recover the flag", 40),
            ],
            "hint": "Investigate other users on the system. Check /etc/passwd or use 'getent passwd' and check home directories.",
            "flag": "CTF{user_enum_detective}",
            "module_order": 2,
        },
        {
            "order": 5,
            "title": "Permission Analysis",
            "slug": "ltc-05-the-permissive-file",
            "cat_key": "linux-permissions",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Insecure file permissions violate least privilege. Search /opt for suspicious files with wide-open permissions (777 mode).",
            "objectives": [
                ("Audit POSIX permissions across /opt using find with octal permission filters", 35),
                ("Read and analyze the world-writable file to extract the flag", 40),
            ],
            "hint": "Look for files with unusual permissions. Try: find /opt -perm 777 2>/dev/null",
            "flag": "CTF{perm_sleuth_chmod}",
            "module_order": 2,
        },
        {
            "order": 6,
            "title": "Service Discovery",
            "slug": "ltc-06-the-hidden-service",
            "cat_key": "linux-services",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "An unknown background service is listening on port 8080. Identify the daemon, establish a socket connection, and retrieve the flag.",
            "objectives": [
                ("Identify listening TCP ports using netstat or ss sockets", 35),
                ("Interact with localhost:8080 using curl or netcat to obtain the response", 40),
            ],
            "hint": "What services are running? Use 'netstat -tulpn' or 'ss -tulpn' to find listening ports, then connect with 'curl http://localhost:8080'.",
            "flag": "CTF{net_detective_port8080}",
            "module_order": 4,
        },
        {
            "order": 7,
            "title": "Encoding Challenge",
            "slug": "ltc-07-the-encoded-secret",
            "cat_key": "linux-fundamentals",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 25,
            "description": "An obfuscated security token has been encoded to evade detection. Discover the encoded asset in ctf_challenges and decode it.",
            "objectives": [
                ("Locate encoded base64 assets within the challenge directory", 35),
                ("Decode the payload using command-line transformation tools", 40),
            ],
            "hint": "The flag is encoded. Look for encoded files in ctf_challenges and use 'base64 -d' to decode.",
            "flag": "CTF{decode_master_base64}",
            "module_order": 2,
        },
        {
            "order": 8,
            "title": "SSH Secrets",
            "slug": "ltc-08-ssh-secrets",
            "cat_key": "linux-security",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Secure Shell credentials and configurations require strict access governance. Investigate SSH keys and configurations to find the secret.",
            "objectives": [
                ("Inspect SSH configurations and authorized keys in ~/.ssh", 35),
                ("Carve out hidden credentials and cryptographic metadata", 40),
            ],
            "hint": "SSH configurations often hide secrets. Explore ~/.ssh directory thoroughly, checking key comments and config.",
            "flag": "CTF{ssh_secrets_authorized}",
            "module_order": 4,
        },
        {
            "order": 9,
            "title": "DNS Inspection",
            "slug": "ltc-09-dns-inspection",
            "cat_key": "linux-networking",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "DNS resolution on modern systemd Linux distributions is mediated by systemd-resolved. Inspect the resolver configuration.",
            "objectives": [
                ("Analyze /etc/resolv.conf and systemd-resolved resolver status", 35),
                ("Extract the flag configured within resolver domain or search settings", 40),
            ],
            "hint": "Modern Ubuntu DNS is usually managed by systemd-resolved. Inspect /etc/resolv.conf, resolvectl status, and /etc/systemd/resolved.conf.d/.",
            "flag": "CTF{dns_name_resolver}",
            "module_order": 4,
        },
        {
            "order": 10,
            "title": "Remote Upload Detection",
            "slug": "ltc-10-remote-upload",
            "cat_key": "linux-networking",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "An automated directory sentinel monitors filesystem events. Transfer or create a file in ctf_challenges to trigger the automated flag drop.",
            "objectives": [
                ("Detect directory monitor behavior using inotify or process inspection", 35),
                ("Trigger file creation event and capture the generated flag", 40),
            ],
            "hint": "Monitor file creation with tools like inotifywait, or try creating a file in ctf_challenges.",
            "flag": "CTF{net_copy_file_drop}",
            "module_order": 4,
        },
        {
            "order": 11,
            "title": "Web Configuration",
            "slug": "ltc-11-web-configuration",
            "cat_key": "linux-services",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "An Nginx web server is serving content on a non-standard port. Investigate virtual host configurations and verify the site.",
            "objectives": [
                ("Inspect Nginx site configurations in /etc/nginx/sites-available/", 35),
                ("Locate the non-standard port configuration and verify HTTP response", 40),
            ],
            "hint": "Web servers serve content from specific directories. Check what ports nginx is listening on and /etc/nginx/sites-available/.",
            "flag": "CTF{web_config_nginx_port}",
            "module_order": 4,
        },
        {
            "order": 12,
            "title": "Network Traffic Analysis",
            "slug": "ltc-12-network-traffic-analysis",
            "cat_key": "linux-networking",
            "difficulty": LabDifficulty.HARD,
            "points": 100,
            "estimated_minutes": 40,
            "description": "Covert channels transmit exfiltrated data inside packet payloads. Capture and analyze ICMP ping traffic using packet sniffing tools.",
            "objectives": [
                ("Execute live packet capture on loopback or primary interface with tcpdump", 45),
                ("Filter ICMP Echo requests and carve ASCII payload strings to find the flag", 55),
            ],
            "hint": "Network traffic can carry hidden messages. Look at ping patterns with 'sudo tcpdump -i any -X icmp'.",
            "flag": "CTF{icmp_covert_traffic}",
            "module_order": 4,
        },
        {
            "order": 13,
            "title": "Cron Job Hunter",
            "slug": "ltc-13-cron-job-hunter",
            "cat_key": "linux-processes",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Scheduled cron tasks execute recurrently in the background. Audit cron configuration directories and user tables to locate the flag.",
            "objectives": [
                ("Audit /etc/cron* directories and crontab definitions", 35),
                ("Inspect scheduled commands and logs to extract the execution secret", 40),
            ],
            "hint": "Cron jobs run on schedules. Check /etc/cron.d/, /etc/crontab, and user crontabs with 'crontab -l' or 'cat /etc/cron.d/*'.",
            "flag": "CTF{cron_master_scheduler}",
            "module_order": 2,
        },
        {
            "order": 14,
            "title": "Process Environment",
            "slug": "ltc-14-process-environment",
            "cat_key": "linux-processes",
            "difficulty": LabDifficulty.HARD,
            "points": 100,
            "estimated_minutes": 40,
            "description": "Processes inherit environment variables that may expose sensitive credentials. Inspect /proc filesystem tables to extract the process secret.",
            "objectives": [
                ("Enumerate running processes with ps aux and map process identifiers (PIDs)", 45),
                ("Read /proc/<PID>/environ and decode null-delimited environment strings", 55),
            ],
            "hint": "Process info lives in /proc. Each process has a directory with its environment in /proc/PID/environ. Use 'tr \\0 \\n < /proc/<PID>/environ'.",
            "flag": "CTF{proc_env_process_secret}",
            "module_order": 2,
        },
        {
            "order": 15,
            "title": "Archive Archaeologist",
            "slug": "ltc-15-archive-archaeologist",
            "cat_key": "linux-commands",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Attackers and administrators package nested archives across multiple compression formats. Recursively unpack the multi-layer archive to recover the flag.",
            "objectives": [
                ("Identify container formats using the file utility", 35),
                ("Recursively extract nested tar, gzip, and bzip2 archives to recover the payload", 40),
            ],
            "hint": "Archives can be nested. Use 'tar -xzf' or 'gunzip' to extract layers. Check file types with 'file' command.",
            "flag": "CTF{archive_dig_unpacked}",
            "module_order": 4,
        },
        {
            "order": 16,
            "title": "Symbolic Sleuth",
            "slug": "ltc-16-symbolic-sleuth",
            "cat_key": "linux-filesystem",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 30,
            "description": "Symbolic links can form complex multi-hop dependency chains. Trace the symlink trail across filesystem directories to discover the destination.",
            "objectives": [
                ("Analyze filesystem links using ls -l and readlink", 35),
                ("Follow recursive pointer chains to reach the target flag data", 40),
            ],
            "hint": "Symlinks can chain together. Use 'readlink -f' to find the final target, or 'ls -la' to see link targets.",
            "flag": "CTF{link_follow_symlink}",
            "module_order": 4,
        },
        {
            "order": 17,
            "title": "History Mystery",
            "slug": "ltc-17-history-mystery",
            "cat_key": "linux-fundamentals",
            "difficulty": LabDifficulty.MEDIUM,
            "points": 75,
            "estimated_minutes": 25,
            "description": "Operators occasionally leak credentials or sensitive tokens directly into interactive shell command histories. Audit history logs to recover the flag.",
            "objectives": [
                ("Locate and examine shell history records across user accounts", 35),
                ("Parse command lines and environment overrides in .bash_history", 40),
            ],
            "hint": "Bash stores command history in ~/.bash_history. Other users may have history files too. Search with grep.",
            "flag": "CTF{history_sleuth_terminal}",
            "module_order": 2,
        },
        {
            "order": 18,
            "title": "Disk Detective",
            "slug": "ltc-18-disk-detective",
            "cat_key": "linux-troubleshooting",
            "difficulty": LabDifficulty.HARD,
            "points": 100,
            "estimated_minutes": 45,
            "description": "Digital forensics investigators mount unallocated disk images to examine evidence. Mount the provided disk image loopback device and inspect its structure.",
            "objectives": [
                ("Examine raw disk image files and partition layouts with fdisk or file", 45),
                ("Mount loopback disk image to a temporary mountpoint and extract the flag", 55),
            ],
            "hint": "A disk image file exists on the system. Try mounting it with 'sudo mount -o loop <image> <mountpoint>' to explore its contents.",
            "flag": "CTF{disk_sleuth_forensics}",
            "module_order": 4,
        },
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Importing LearnToCloud Linux CTFs Collection ==="))

        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()

        # 1. Ensure Categories exist in LabCategory and ChallengeCategory
        lab_cat_map = {}
        ch_cat_map = {}
        for key, (name, slug, icon, desc) in self.CATEGORY_MAPPING.items():
            lcat, _ = LabCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "description": desc,
                }
            )
            lab_cat_map[key] = lcat

            ccat, _ = ChallengeCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "description": desc,
                }
            )
            ch_cat_map[key] = ccat

        # 2. Resolve Course and Modules for Learning Path Linkage
        diploma = Course.objects.filter(slug="diploma-in-cyber-security").first()
        mod2 = CourseModule.objects.filter(course=diploma, order=2).first() if diploma else None
        mod4 = CourseModule.objects.filter(course=diploma, order=4).first() if diploma else None

        labs_created = 0
        labs_updated = 0
        challenges_created = 0
        challenges_updated = 0

        # 3. Seed Guided Labs and CTF Challenges
        for item in self.CHALLENGES_DATA:
            cat_key = item["cat_key"]
            lab_cat = lab_cat_map[cat_key]
            ch_cat = ch_cat_map[cat_key]

            # Choose module linkage
            target_mod = mod2 if item.get("module_order") == 2 else mod4

            # --- A. Guided Lab (Lab model) ---
            lab, l_created = Lab.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["title"],
                    "category": lab_cat,
                    "difficulty": item["difficulty"],
                    "course": diploma,
                    "module": target_mod,
                    "type": LabType.GUIDED,
                    "short_description": item["description"][:500],
                    "description": item["description"],
                    "points": item["points"],
                    "estimated_minutes": item["estimated_minutes"],
                    "docker_image": "futuretech/linux-ctf:latest",
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
                    "display_order": 300 + item["order"],
                    "is_published": True,
                    "created_by": admin_user,
                }
            )

            if not l_created:
                lab.name = item["title"]
                lab.category = lab_cat
                lab.difficulty = item["difficulty"]
                lab.course = diploma
                lab.module = target_mod
                lab.type = LabType.GUIDED
                lab.short_description = item["description"][:500]
                lab.description = item["description"]
                lab.points = item["points"]
                lab.estimated_minutes = item["estimated_minutes"]
                lab.source_name = self.SOURCE_NAME
                lab.source_url = self.SOURCE_URL
                lab.source_type = self.SOURCE_TYPE
                lab.attribution_required = self.ATTRIBUTION_REQUIRED
                lab.license_name = self.LICENSE_NAME
                lab.display_order = 300 + item["order"]
                lab.is_published = True
                lab.save()
                labs_updated += 1
            else:
                labs_created += 1

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

            # --- B. CTF Challenge (Challenge model) ---
            ch_slug = f"linux-{item['slug']}"
            challenge, c_created = Challenge.objects.get_or_create(
                slug=ch_slug,
                defaults={
                    "title": f"Linux: {item['title']}",
                    "category": ch_cat,
                    "difficulty": item["difficulty"],
                    "points": item["points"],
                    "description": item["description"],
                    "instructions": f"Skills Tested: {item['cat_key'].replace('linux-', '').replace('-', ' ').title()}\n\nTip: {item['hint']}",
                    "flag": item["flag"],
                    "is_active": True,
                }
            )

            if not c_created:
                challenge.title = f"Linux: {item['title']}"
                challenge.category = ch_cat
                challenge.difficulty = item["difficulty"]
                challenge.points = item["points"]
                challenge.description = item["description"]
                challenge.instructions = f"Skills Tested: {item['cat_key'].replace('linux-', '').replace('-', ' ').title()}\n\nTip: {item['hint']}"
                challenge.flag = item["flag"]
                challenge.is_active = True
                challenge.save()
                challenges_updated += 1
            else:
                challenges_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully processed LearnToCloud collection: "
            f"{labs_created} labs created, {labs_updated} labs updated | "
            f"{challenges_created} challenges created, {challenges_updated} challenges updated."
        ))
        self.stdout.write(self.style.NOTICE(
            f"Attribution: Originating from {self.SOURCE_NAME} under {self.LICENSE_NAME} license "
            f"({self.SOURCE_URL})."
        ))

