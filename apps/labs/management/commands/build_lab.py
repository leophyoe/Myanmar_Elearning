from django.core.management.base import BaseCommand, CommandError
from apps.labs.models import LabTemplate, Lab
from apps.labs.builder import build_template_image


class Command(BaseCommand):
    help = "Build Docker image from uploaded lab bundle (Dockerfile in cyber/labs/...)"

    def add_arguments(self, parser):
        parser.add_argument(
            'slug',
            nargs='?',
            type=str,
            help="Slug of the Lab or LabTemplate (or use --all)",
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help="Build Docker images for all lab templates that have bundles",
        )
        parser.add_argument(
            '--tag',
            type=str,
            help="Custom Docker image tag to assign",
        )

    def handle(self, *args, **options):
        build_all = options['all']
        slug = options.get('slug')
        tag = options.get('tag')

        if not slug and not build_all:
            raise CommandError("Please provide a lab template slug or specify --all")

        if build_all:
            templates = LabTemplate.objects.all()
            if not templates.exists():
                self.stdout.write(self.style.WARNING("No lab templates found."))
                return

            self.stdout.write(f"Building images for {templates.count()} templates...")
            success_count = 0
            for t in templates:
                ok, msg = build_template_image(t, tag=tag)
                if ok:
                    self.stdout.write(self.style.SUCCESS(f"  [OK] {t.name}: {msg}"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f"  [FAIL] {t.name}: {msg}"))

            self.stdout.write(self.style.SUCCESS(f"\nDone: {success_count}/{templates.count()} built successfully."))
            return

        # Find template by slug or lab slug
        template = LabTemplate.objects.filter(slug=slug).first()
        if not template:
            lab = Lab.objects.filter(slug=slug).select_related('template').first()
            if lab and lab.template:
                template = lab.template

        if not template:
            raise CommandError(f"No LabTemplate or Lab found with slug '{slug}'")

        self.stdout.write(f"Building Docker image for '{template.name}' ({template.slug})...")
        ok, msg = build_template_image(template, tag=tag)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Success: {msg}"))
        else:
            raise CommandError(msg)
