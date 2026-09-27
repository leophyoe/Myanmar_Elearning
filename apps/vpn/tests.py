from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from apps.vpn.models import VpnProfile, VpnServerConfig
from apps.vpn.services import VpnCertificateService

User = get_user_model()


class VpnCertificateServiceTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="student_neo",
            email="neo@example.com",
            password="matrixpassword123",
            role="STUDENT",
        )
        self.user2 = User.objects.create_user(
            username="student_trinity",
            email="trinity@example.com",
            password="matrixpassword123",
            role="STUDENT",
        )

    def test_pki_ca_and_server_config_creation(self):
        """Test automatic creation of Root CA certificate, private key and server config."""
        config = VpnCertificateService.get_or_create_server_config()
        self.assertIsNotNone(config)
        self.assertIn("BEGIN CERTIFICATE", config.ca_cert)
        self.assertIn("BEGIN RSA PRIVATE KEY", config.ca_key)
        self.assertEqual(config.server_port, 1194)
        self.assertEqual(config.vpn_subnet, "10.8.0.0/24")
        self.assertEqual(config.lab_subnet, "10.10.0.0/16")

    def test_client_bundle_generation(self):
        """Test generation of client private key, X.509 cert and ready-to-run .ovpn file."""
        profile = VpnCertificateService.generate_profile_for_user(self.user1)

        self.assertIsInstance(profile, VpnProfile)
        self.assertEqual(profile.user, self.user1)
        self.assertEqual(profile.virtual_ip, "10.8.0.2")
        self.assertIn("BEGIN CERTIFICATE", profile.client_cert)
        self.assertIn("BEGIN RSA PRIVATE KEY", profile.client_key)

        # Check .ovpn content
        ovpn = profile.ovpn_content
        self.assertIn("client", ovpn)
        self.assertIn("dev tun", ovpn)
        self.assertIn("<ca>", ovpn)
        self.assertIn("</ca>", ovpn)
        self.assertIn("<cert>", ovpn)
        self.assertIn("</cert>", ovpn)
        self.assertIn("<key>", ovpn)
        self.assertIn("</key>", ovpn)
        self.assertIn("10.10.0.0 255.255.0.0", ovpn)

    def test_sequential_ip_allocation(self):
        """Subsequent users should receive sequentially allocated virtual IPs."""
        prof1 = VpnCertificateService.generate_profile_for_user(self.user1)
        prof2 = VpnCertificateService.generate_profile_for_user(self.user2)

        self.assertEqual(prof1.virtual_ip, "10.8.0.2")
        self.assertEqual(prof2.virtual_ip, "10.8.0.3")

    def test_bundle_regeneration(self):
        """Regenerating a user bundle should update the existing profile with a new cert."""
        prof1 = VpnCertificateService.generate_profile_for_user(self.user1)
        old_cert = prof1.client_cert

        prof2 = VpnCertificateService.generate_profile_for_user(self.user1, force_regenerate=True)
        self.assertEqual(prof1.pk, prof2.pk)
        self.assertNotEqual(old_cert, prof2.client_cert)
        self.assertEqual(prof2.virtual_ip, "10.8.0.2")


class VpnViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username="sec_researcher",
            email="sec@example.com",
            password="safe_password_2026",
            role="STUDENT",
        )

    def test_unauthenticated_access_redirects(self):
        """Unauthenticated requests must be redirected to login."""
        response = self.client.get(reverse("vpn-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_authenticated_vpn_dashboard(self):
        """Authenticated student can view the VPN dashboard and auto-generated profile."""
        self.client.login(username="sec_researcher", password="safe_password_2026")
        response = self.client.get(reverse("vpn-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sec_researcher")
        self.assertContains(response, "10.8.0.2")
        self.assertContains(response, "10.10.0.0/16")

    def test_download_ovpn_file(self):
        """Download endpoint serves the user's .ovpn configuration file."""
        self.client.login(username="sec_researcher", password="safe_password_2026")
        response = self.client.get(reverse("vpn-download"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/x-openvpn-profile")
        self.assertIn("mel_sec_researcher.ovpn", response["Content-Disposition"])
        self.assertIn(b"dev tun", response.content)
        self.assertIn(b"<ca>", response.content)

        profile = VpnProfile.objects.get(user=self.student)
        self.assertEqual(profile.download_count, 1)

    def test_regenerate_profile(self):
        """POST to regenerate should generate a fresh keypair and cert."""
        self.client.login(username="sec_researcher", password="safe_password_2026")
        # Generate initial
        VpnCertificateService.generate_profile_for_user(self.student)
        old_cert = VpnProfile.objects.get(user=self.student).client_cert

        response = self.client.post(reverse("vpn-regenerate"))
        self.assertEqual(response.status_code, 302)

        new_cert = VpnProfile.objects.get(user=self.student).client_cert
        self.assertNotEqual(old_cert, new_cert)

    def test_vpn_status_api(self):
        """Status API returns JSON metadata about student's VPN profile."""
        self.client.login(username="sec_researcher", password="safe_password_2026")
        VpnCertificateService.generate_profile_for_user(self.student)
        response = self.client.get(reverse("vpn-status"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["provisioned"])
        self.assertEqual(data["virtual_ip"], "10.8.0.2")
        self.assertEqual(data["download_count"], 0)


class SetupVpnCommandTests(TestCase):
    def test_setup_vpn_command(self):
        """Management command setup_vpn initializes or updates configuration."""
        call_command("setup_vpn", host="vpn.myanmar-elearning.local", port=1194, proto="udp")
        config = VpnServerConfig.objects.first()
        self.assertIsNotNone(config)
        self.assertEqual(config.server_host, "vpn.myanmar-elearning.local")
        self.assertEqual(config.server_port, 1194)
        self.assertEqual(config.protocol, "udp")
        self.assertTrue(len(config.ca_cert) > 50)
