import unittest
import yaml
from pathlib import Path


class JuiceShopSpecTestCase(unittest.TestCase):
    """
    Validates OWASP Juice Shop lab definition specification and constraints.
    """
    def setUp(self):
        self.lab_dir = Path(__file__).resolve().parent.parent
        self.yaml_file = self.lab_dir / "lab.yaml"

    def test_yaml_spec_exists_and_valid(self):
        self.assertTrue(self.yaml_file.exists(), "lab.yaml must exist in the lab root")
        with open(self.yaml_file, "r") as f:
            data = yaml.safe_load(f)

        self.assertEqual(data.get("slug"), "owasp-juice-shop")
        self.assertEqual(data.get("type"), "WEB_APPLICATION")
        self.assertEqual(data.get("docker_image"), "bkimminich/juice-shop:v17.1.1")
        self.assertEqual(data.get("internal_port"), 3000)

        # Resource verification
        resources = data.get("resources", {})
        self.assertIn("cpu_limit", resources)
        self.assertIn("memory_limit_mb", resources)
        self.assertLessEqual(resources.get("memory_limit_mb", 0), 2048)

        # Security policies
        security = data.get("security", {})
        self.assertEqual(security.get("isolation"), "per-student-container")
        self.assertTrue(security.get("no_new_privileges"))
        self.assertIn("ALL", security.get("cap_drop", []))

        # Challenges
        challenges = data.get("challenges", [])
        self.assertGreaterEqual(len(challenges), 5)
        ch_ids = [c["id"] for c in challenges]
        self.assertIn("scoreboard", ch_ids)
        self.assertIn("admin_sqli", ch_ids)


if __name__ == "__main__":
    unittest.main()

