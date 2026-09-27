import datetime
import ipaddress
import logging
from django.conf import settings
from django.utils import timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .models import VpnProfile, VpnServerConfig

logger = logging.getLogger(__name__)


class VpnCertificateService:
    """
    Automated PKI certificate and OpenVPN client configuration engine.
    Issues cryptographically valid X.509 client certificates and .ovpn bundles.
    """

    @classmethod
    def get_or_create_server_config(cls) -> VpnServerConfig:
        """Fetch or initialize the Root CA and OpenVPN server configuration."""
        config = VpnServerConfig.objects.first()
        if not config:
            host = getattr(settings, 'VPN_SERVER_HOST', '127.0.0.1')
            port = getattr(settings, 'VPN_SERVER_PORT', 1194)
            config = VpnServerConfig.objects.create(
                server_host=host,
                server_port=port,
                protocol='udp',
                vpn_subnet='10.8.0.0/24',
                lab_subnet='10.10.0.0/16',
            )

        if not config.ca_cert or not config.ca_key:
            logger.info("Initializing fresh Root Certificate Authority (CA) for OpenVPN...")
            # 1. Generate 2048-bit Root CA RSA key
            ca_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            ca_key_pem = ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode('utf-8')

            # 2. Build Self-signed Root CA Certificate (valid for 10 years)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "MM"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, getattr(settings, 'PLATFORM_NAME', "Myanmar E-Learning")),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Cyber Range Lab Security"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Myanmar-ELearning-CA"),
            ])
            now = datetime.datetime.now(datetime.timezone.utc)
            ca_cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(ca_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(minutes=5))
                .not_valid_after(now + datetime.timedelta(days=3650))
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=None),
                    critical=True,
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=True,
                        crl_sign=True,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .sign(ca_key, hashes.SHA256())
            )
            ca_cert_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

            config.ca_cert = ca_cert_pem
            config.ca_key = ca_key_pem
            config.save()

        return config

    @classmethod
    def _allocate_virtual_ip(cls) -> str:
        """Find the next available IP address in the 10.8.0.0/24 client subnet."""
        assigned = set(
            VpnProfile.objects.exclude(virtual_ip__isnull=True)
            .values_list('virtual_ip', flat=True)
        )
        # Allocate between 10.8.0.2 and 10.8.0.254 (10.8.0.1 reserved for gateway)
        for host in range(2, 254):
            ip_str = f"10.8.0.{host}"
            if ip_str not in assigned:
                return ip_str
        return "10.8.0.254"

    @classmethod
    def generate_profile_for_user(cls, user, force_regenerate: bool = False) -> VpnProfile:
        """
        Generate or fetch an existing OpenVPN profile for the specified student/user.
        """
        config = cls.get_or_create_server_config()

        profile, created = VpnProfile.objects.get_or_create(user=user)
        if not created and profile.ovpn_content and not force_regenerate and not profile.revoked:
            return profile

        # Allocate virtual IP if user doesn't already have one
        if not profile.virtual_ip:
            profile.virtual_ip = cls._allocate_virtual_ip()

        # Load CA Key & Cert
        ca_key = serialization.load_pem_private_key(config.ca_key.encode('utf-8'), password=None)
        ca_cert = x509.load_pem_x509_certificate(config.ca_cert.encode('utf-8'))

        # 1. Generate 2048-bit Client RSA Key
        client_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        client_key_pem = client_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode('utf-8')

        # 2. Build Client Certificate signed by CA (valid for 1 year)
        client_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "MM"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, getattr(settings, 'PLATFORM_NAME', "Myanmar E-Learning")),
            x509.NameAttribute(NameOID.COMMON_NAME, f"mel-user-{user.username}"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        client_cert = (
            x509.CertificateBuilder()
            .subject_name(client_subject)
            .issuer_name(ca_cert.subject)
            .public_key(client_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        client_cert_pem = client_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

        # 3. Assemble unified .ovpn profile file
        server_host = config.server_host
        server_port = config.server_port
        proto = config.protocol.lower()

        ovpn_lines = [
            f"# ========================================================",
            f"# Myanmar E-Learning Cyber Range VPN Access Pack",
            f"# User: {user.username} | Virtual IP: {profile.virtual_ip}",
            f"# Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"# ========================================================",
            f"client",
            f"dev tun",
            f"proto {proto}",
            f"remote {server_host} {server_port}",
            f"resolv-retry infinite",
            f"nobind",
            f"persist-key",
            f"persist-tun",
            f"remote-cert-tls server",
            f"cipher AES-256-GCM",
            f"auth SHA256",
            f"verb 3",
            f"mute-replay-warnings",
            f"# Route traffic to isolated Lab Network (10.10.0.0/16)",
            f"route 10.10.0.0 255.255.0.0",
            f"",
            f"<ca>",
            config.ca_cert.strip(),
            f"</ca>",
            f"",
            f"<cert>",
            client_cert_pem.strip(),
            f"</cert>",
            f"",
            f"<key>",
            client_key_pem.strip(),
            f"</key>",
            f"",
        ]
        ovpn_content = "\n".join(ovpn_lines)

        profile.client_cert = client_cert_pem
        profile.client_key = client_key_pem
        profile.ovpn_content = ovpn_content
        profile.revoked = False
        profile.save()

        logger.info(f"Generated new OpenVPN profile for user '{user.username}' with IP {profile.virtual_ip}")
        return profile
