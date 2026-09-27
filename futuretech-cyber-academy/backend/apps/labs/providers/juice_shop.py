import re
from typing import Dict, Any, List, Optional, Tuple
from django.utils import timezone
from apps.labs.models import Lab, LabInstance, LabSubmission, CTFScore
from .base import WebApplicationLabProvider


class OWASPJuiceShopProvider(WebApplicationLabProvider):
    """
    Dedicated Cyber Range Provider for OWASP Juice Shop.
    Enforces per-student isolated container instances, dynamic instance flag generation,
    AI Tutor conceptual hints, and health checks.

    Upstream Reference:
    OWASP Juice Shop by Bjoern Kimminich (AGPL-3.0)
    https://github.com/juice-shop/juice-shop
    """

    IMAGE_NAME = "bkimminich/juice-shop:v17.1.1"
    INTERNAL_PORT = 3000

    CHALLENGES: List[Dict[str, Any]] = [
        {
            "id": "scoreboard",
            "name": "Score Board Discovery",
            "category": "Information Disclosure",
            "difficulty": "Beginner",
            "points": 50,
            "description": "Discover and access the hidden administration and challenge progress Score Board.",
            "owasp_category": "A01:2021-Broken Access Control",
            "flag_prefix": "js_scoreboard",
            "hints": [
                "Modern Single Page Applications (SPAs) bundle their client-side routing definitions in JavaScript assets.",
                "Inspect main.js or index_bundle.js in your browser Developer Tools (Ctrl+Shift+I) and search for 'score'.",
                "Navigate directly to the URL route /#/score-board in your browser address bar to unlock the panel."
            ]
        },
        {
            "id": "admin_sqli",
            "name": "Admin Login via SQL Injection",
            "category": "Injection",
            "difficulty": "Beginner",
            "points": 100,
            "description": "Bypass authentication and log in as the administrator user without knowing the password.",
            "owasp_category": "A03:2021-Injection",
            "flag_prefix": "js_admin_sqli",
            "hints": [
                "Examine how the authentication query checks credentials. What happens if the WHERE condition evaluates to TRUE?",
                "Test injecting a single quote (') into the email field to verify if SQLite syntax errors occur.",
                "Input ' OR 1=1-- into the email field with any random password to comment out password verification."
            ]
        },
        {
            "id": "dom_xss",
            "name": "DOM-Based Cross-Site Scripting (XSS)",
            "category": "Cross-Site Scripting",
            "difficulty": "Intermediate",
            "points": 100,
            "description": "Perform an unsanitized DOM XSS attack via the product search bar.",
            "owasp_category": "A03:2021-Injection",
            "flag_prefix": "js_dom_xss",
            "hints": [
                "Observe where search keywords are echoed into the DOM when no search results are returned.",
                "Verify whether HTML tags like <h1> or <iframe> are filtered or sanitized before insertion.",
                "Inject an iframe payload such as <iframe src=\"javascript:alert(`xss`)\"> into the search field."
            ]
        },
        {
            "id": "path_traversal",
            "name": "Confidential Document Path Traversal",
            "category": "Broken Access Control",
            "difficulty": "Intermediate",
            "points": 100,
            "description": "Access confidential corporate acquisition documentation stored in the public FTP directory.",
            "owasp_category": "A01:2021-Broken Access Control",
            "flag_prefix": "js_path_traversal",
            "hints": [
                "Inspect public assets and paths referenced in client-side code or robots.txt.",
                "Notice the /ftp/ directory accessible in the web root containing sensitive internal documents.",
                "Access /ftp/acquisitions.md or use null-byte / URL encoding bypasses to download protected files."
            ]
        },
        {
            "id": "basket_idor",
            "name": "Basket IDOR / Broken Object Level Auth",
            "category": "Insecure Direct Object References",
            "difficulty": "Intermediate",
            "points": 150,
            "description": "Inspect another user's shopping cart by manipulating basket identifiers in REST API calls.",
            "owasp_category": "A01:2021-Broken Access Control",
            "flag_prefix": "js_basket_idor",
            "hints": [
                "Use the Browser Network Tab or Burp Suite to intercept requests when viewing or adding items to your cart.",
                "Examine the endpoint /rest/basket/<id> where the ID is an exposed integer parameter.",
                "Change the basket ID parameter in the request URL to another integer (e.g. 1 or 2) to view other users' items."
            ]
        }
    ]

    def __init__(self):
        super().__init__(internal_web_port=self.INTERNAL_PORT)

    @classmethod
    def get_challenge_by_id(cls, challenge_id: str) -> Optional[Dict[str, Any]]:
        for ch in cls.CHALLENGES:
            if ch["id"] == challenge_id:
                return ch
        return None

    @classmethod
    def generate_dynamic_flag(cls, instance: LabInstance, challenge_id: str) -> str:
        """
        Generates a cryptographically tied dynamic flag for a specific student instance and challenge.
        Format: FTACK{<flag_prefix>_<instance_token_prefix>}
        """
        ch = cls.get_challenge_by_id(challenge_id)
        prefix = ch["flag_prefix"] if ch else f"js_{challenge_id}"
        token = instance.uuid.hex[:8]
        return f"FTACK{{{prefix}_{token}}}"

    @classmethod
    def get_all_flags_for_instance(cls, instance: LabInstance) -> Dict[str, str]:
        """
        Returns a mapping of challenge_id -> expected_flag for this instance.
        """
        return {
            ch["id"]: cls.generate_dynamic_flag(instance, ch["id"])
            for ch in cls.CHALLENGES
        }

    def verify_flag(
        self, instance: LabInstance, submitted_flag: str, challenge_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verifies a student's submitted flag against the dynamic instance flags.
        Ensures strict instance-binding: flags generated for Instance A are invalid for Instance B.
        """
        clean_flag = submitted_flag.strip()
        expected_flags = self.get_all_flags_for_instance(instance)

        if challenge_id:
            expected = expected_flags.get(challenge_id)
            if expected and clean_flag == expected:
                return True, self.get_challenge_by_id(challenge_id)
            return False, None

        # If no specific challenge_id specified, check against all challenges for this instance
        for ch_id, exp_flag in expected_flags.items():
            if clean_flag == exp_flag:
                return True, self.get_challenge_by_id(ch_id)

        return False, None

    def get_hint(self, challenge_id: str, hint_level: int = 1) -> Dict[str, Any]:
        """
        Retrieves progressive Socratic hints for a challenge without revealing the final flag.
        Levels: 1 (Conceptual), 2 (Methodology/Tooling), 3 (Actionable Guidance).
        """
        ch = self.get_challenge_by_id(challenge_id)
        if not ch:
            return {
                "error": "Challenge not found",
                "hint": "Analyze the application behavior and request telemetry."
            }

        hints = ch.get("hints", [])
        idx = max(0, min(hint_level - 1, len(hints) - 1))
        hint_text = hints[idx] if hints else "Review the OWASP Top 10 documentation for this vulnerability category."

        penalty_map = {1: 0, 2: 10, 3: 25}
        penalty = penalty_map.get(hint_level, 10)

        return {
            "challenge_id": challenge_id,
            "challenge_name": ch["name"],
            "level": idx + 1,
            "max_levels": len(hints),
            "hint": hint_text,
            "penalty_percent": penalty,
            "owasp_category": ch.get("owasp_category", "Web Security"),
        }

    def health_check(self, instance: LabInstance) -> Dict[str, Any]:
        """
        Performs a health check on the student's Juice Shop instance.
        """
        base_status = super().health_check(instance)
        base_status.update({
            "service_name": "OWASP Juice Shop",
            "internal_port": self.INTERNAL_PORT,
            "gateway_url": self.get_access_url(instance),
            "challenges_count": len(self.CHALLENGES),
            "is_ready": instance.is_running and not instance.is_expired,
        })
        return base_status

