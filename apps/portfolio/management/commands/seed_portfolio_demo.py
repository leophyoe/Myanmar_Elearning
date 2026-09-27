from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.portfolio.models import (
    ExternalCertificate, PortfolioEntry, PortfolioLink, PortfolioProject, Skill,
)

User = get_user_model()

SKILLS = [
    ('Python', 'technical', 4),
    ('Django', 'technical', 4),
    ('Tailwind CSS', 'tools', 3),
    ('Penetration testing', 'security', 3),
    ('Technical writing', 'soft', 3),
    ('English', 'language', 4),
]

LINKS = [
    (PortfolioLink.Kind.GITHUB, 'https://github.com/example'),
    (PortfolioLink.Kind.LINKEDIN, 'https://www.linkedin.com/in/example'),
    (PortfolioLink.Kind.UPWORK, 'https://www.upwork.com/freelancers/~example'),
    (PortfolioLink.Kind.WEBSITE, 'https://example.dev'),
]

PROJECTS = [
    {
        'title': 'Clinic booking platform',
        'category': PortfolioProject.Category.DEVELOPMENT,
        'excerpt': 'Appointment booking and staff rota for a 12-doctor clinic.',
        'description': 'Designed the schema, built the booking flow and the SMS '
                       'reminder job. Cut no-shows by a third in the first quarter.',
        'client': 'Sithi Clinic',
        'role': 'Full-stack developer',
        'tools': 'Django, HTMX, Postgres, Celery',
        'completed_on': date(2026, 5, 12),
    },
    {
        'title': 'Company website redesign',
        'category': PortfolioProject.Category.DESIGN,
        'excerpt': 'Static marketing site rebuilt as a fast, mobile-first redesign.',
        'description': 'Rebuilt the information architecture, produced the design '
                       'system in Figma and shipped the front end.',
        'client': 'Ayeyarwady Trading',
        'role': 'Designer & developer',
        'tools': 'Figma, Tailwind, Astro',
        'completed_on': date(2026, 2, 3),
    },
    {
        'title': 'Web application security review',
        'category': PortfolioProject.Category.SECURITY,
        'excerpt': 'Black-box assessment of a logistics portal with a written report.',
        'description': 'Enumerated the attack surface, validated each finding and '
                       'delivered a prioritised remediation plan with retests.',
        'client': 'Confidential',
        'role': 'Security consultant',
        'tools': 'Burp Suite, Nmap, OWASP ASVS',
        'completed_on': date(2025, 11, 20),
    },
]

ENTRIES = [
    {
        'kind': PortfolioEntry.Kind.EDUCATION,
        'institution': 'University of Yangon',
        'title': 'BSc Computer Science',
        'location': 'Yangon',
        'start_on': date(2019, 8, 1),
        'end_on': date(2023, 6, 30),
        'details': 'Final-year project: anomaly detection for campus network traffic.',
    },
    {
        'kind': PortfolioEntry.Kind.EXPERIENCE,
        'institution': 'Freelance',
        'title': 'Web developer',
        'location': 'Remote',
        'start_on': date(2023, 7, 1),
        'is_current': True,
        'details': 'Small-business websites, Django back ends and dashboard work.',
    },
]


class Command(BaseCommand):
    help = 'Fill an empty portfolio with sample skills, links, work samples and CV entries.'

    def add_arguments(self, parser):
        parser.add_argument(
            'username', nargs='?', default=None,
            help='Account to fill. Defaults to every account with an empty portfolio.',
        )

    def handle(self, *args, **options):
        username = options['username']
        if username:
            targets = [User.objects.get(username=username)]
        else:
            targets = [
                user for user in User.objects.filter(is_active=True)
                if not user.skills.exists() and not user.portfolio_projects.exists()
            ]

        if not targets:
            self.stdout.write(self.style.WARNING('No empty portfolio to fill.'))
            return

        for user in targets:
            created = 0
            for name, category, level in SKILLS:
                _, was_created = Skill.objects.get_or_create(
                    owner=user, name=name, defaults={'category': category, 'level': level},
                )
                created += bool(was_created)
            for kind, url in LINKS:
                _, was_created = PortfolioLink.objects.get_or_create(
                    owner=user, kind=kind, url=url,
                )
                created += bool(was_created)
            for data in PROJECTS:
                _, was_created = PortfolioProject.objects.get_or_create(
                    owner=user, title=data['title'], defaults=data,
                )
                created += bool(was_created)
            for data in ENTRIES:
                _, was_created = PortfolioEntry.objects.get_or_create(
                    owner=user, institution=data['institution'],
                    kind=data['kind'], defaults=data,
                )
                created += bool(was_created)
            _, was_created = ExternalCertificate.objects.get_or_create(
                owner=user, title='AWS Certified Cloud Practitioner',
                defaults={
                    'issuer': 'Amazon Web Services',
                    'credential_id': 'AWS-CLF-C01-DEMO',
                    'credential_url': 'https://www.credly.com/badges/demo',
                    'issued_on': date(2025, 9, 1),
                    'is_verified': False,
                },
            )
            created += bool(was_created)

            self.stdout.write(self.style.SUCCESS(
                f'{user.username}: {created} portfolio item(s) added. '
                f'Open /portfolio/{user.username}/'
            ))

        self.stdout.write(
            'Note: the sample AWS credential is pending — approve it at '
            '/console/credentials/ before it appears publicly.'
        )
