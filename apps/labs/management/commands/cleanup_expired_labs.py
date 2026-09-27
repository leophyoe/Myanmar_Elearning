from django.core.management.base import BaseCommand
from apps.labs.tasks import reap_expired_labs


class Command(BaseCommand):
    help = "Reap all expired student lab instances and release Docker containers and networks"

    def handle(self, *args, **options):
        result = reap_expired_labs()
        self.stdout.write(self.style.SUCCESS(f"Reaper completed: {result}"))
