from django.db import models
from django.conf import settings
from apps.common.models import BaseModel


class VpnProfile(BaseModel):
    """
    Dedicated OpenVPN profile generated per student/user.
    Enables encrypted, routed access into the isolated lab subnet (10.10.0.0/16).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vpn_profile'
    )
    virtual_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Assigned tunnel IP in 10.8.0.0/24 subnet (e.g. 10.8.0.5)"
    )
    client_cert = models.TextField(blank=True, help_text="X.509 Client Certificate (PEM format)")
    client_key = models.TextField(blank=True, help_text="Client Private Key (PEM format)")
    ovpn_content = models.TextField(blank=True, help_text="Complete .ovpn file with embedded credentials")
    download_count = models.PositiveIntegerField(default=0)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"VPN Profile: {self.user.username} ({self.virtual_ip or 'Unassigned'})"

    @property
    def filename(self) -> str:
        return f"mel_{self.user.username}.ovpn"


class VpnServerConfig(BaseModel):
    """
    Global OpenVPN Root CA and server configuration settings.
    """
    server_host = models.CharField(
        max_length=255,
        default="127.0.0.1",
        help_text="Public IP or FQDN of the OpenVPN gateway"
    )
    server_port = models.PositiveIntegerField(default=1194)
    protocol = models.CharField(
        max_length=8,
        default="udp",
        choices=[("udp", "UDP"), ("tcp", "TCP")]
    )
    vpn_subnet = models.CharField(max_length=64, default="10.8.0.0/24")
    lab_subnet = models.CharField(max_length=64, default="10.10.0.0/16")
    ca_cert = models.TextField(blank=True, help_text="Root Certificate Authority (CA) PEM")
    ca_key = models.TextField(blank=True, help_text="Root CA Private Key PEM")
    tls_auth_key = models.TextField(blank=True, help_text="Static TLS Auth (ta.key) secret for DoS protection")

    class Meta:
        verbose_name = "VPN Server Configuration"
        verbose_name_plural = "VPN Server Configuration"

    def __str__(self):
        return f"VPN Server Config: {self.server_host}:{self.server_port}/{self.protocol}"
