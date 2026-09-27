from django.core.management.base import BaseCommand
from apps.vpn.services import VpnCertificateService
from apps.vpn.models import VpnServerConfig


class Command(BaseCommand):
    help = "Initialize or update the OpenVPN Root CA and server configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default=None,
            help="Public IP address or hostname for the OpenVPN gateway.",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="Port for OpenVPN gateway (default: 1194).",
        )
        parser.add_argument(
            "--proto",
            type=str,
            default=None,
            choices=["udp", "tcp"],
            help="Protocol for OpenVPN gateway (udp or tcp).",
        )

    def handle(self, *args, **options):
        config = VpnCertificateService.get_or_create_server_config()

        updated = False
        if options.get("host"):
            config.server_host = options["host"]
            updated = True
        if options.get("port"):
            config.server_port = options["port"]
            updated = True
        if options.get("proto"):
            config.protocol = options["proto"]
            updated = True

        if updated:
            config.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated server config to {config.server_host}:{config.server_port}/{config.protocol}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ OpenVPN PKI / Root CA initialized successfully!\n"
                f"  Host: {config.server_host}:{config.server_port}/{config.protocol}\n"
                f"  Client Subnet: {config.vpn_subnet}\n"
                f"  Lab Subnet: {config.lab_subnet}"
            )
        )
