from django.core.management.base import BaseCommand
from apps.labs.docker_service import docker_service


class Command(BaseCommand):
    help = "Reaps and terminates all expired Cyber Range lab instances and containers."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Sweeping expired Cyber Range lab instances..."))
        count = docker_service.cleanup_expired_instances()
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"Successfully cleaned up {count} expired lab instance(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("Zero expired instances detected."))

