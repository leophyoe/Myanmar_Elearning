from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.users.models import UserRole
from apps.partner.models import PartnerApplication, Institution

User = get_user_model()


class PartnerApplicationAndShowcaseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin@thuta.edu.mm',
            password='Password123!',
            role=UserRole.ADMIN
        )
        self.applicant = User.objects.create_user(
            username='rector_u_tin',
            email='rector@uit.edu.mm',
            password='Password123!',
            role=UserRole.STUDENT
        )
        self.verified_partner = Institution.objects.create(
            name='University of Information Technology (UIT)',
            slug='uit-yangon',
            institution_type=Institution.InstitutionType.UNIVERSITY,
            contact_person=self.applicant,
            email='contact@uit.edu.mm',
            website='https://uit.edu.mm',
            is_verified=True,
            mou_signed=True
        )

    def test_partner_apply_get_and_post(self):
        self.client.login(username='rector_u_tin', password='Password123!')
        res = self.client.get(reverse('partner-apply'))
        self.assertEqual(res.status_code, 200)

        post_data = {
            'organization_name': 'Yangon City IT Academy',
            'institution_type': 'training_center',
            'country': 'Myanmar',
            'city': 'Yangon',
            'address': 'Hlaing Campus, Yangon',
            'website': 'https://ygnit.edu.mm',
            'contact_person_name': 'Dr. U Kyaw',
            'contact_email': 'contact@ygnit.edu.mm',
            'contact_phone': '+95912345678',
            'registration_number': 'REG-2026-YGN-01',
            'description': 'Academy offering computer engineering and cyber defense cohorts.'
        }
        post_res = self.client.post(reverse('partner-apply'), post_data)
        self.assertRedirects(post_res, reverse('partner-apply-success'))
        self.assertTrue(PartnerApplication.objects.filter(organization_name='Yangon City IT Academy').exists())

    def test_admin_partner_application_list_and_approval(self):
        # Create pending application
        app = PartnerApplication.objects.create(
            applicant=self.applicant,
            organization_name='Mandalay Tech Institute',
            institution_type='university',
            contact_person_name='Daw Hla Hla',
            contact_email='hla@mti.edu.mm',
            contact_phone='+95987654321',
            city='Mandalay',
            description='Technical institute for computing.'
        )
        self.client.login(username='admin_boss', password='Password123!')

        # Check admin application list view
        res = self.client.get(reverse('console-partner-application-list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Mandalay Tech Institute')

        # Approve application
        approve_url = reverse('console-partner-application-action', kwargs={'app_id': app.id, 'action': 'approve'})
        post_res = self.client.post(approve_url)
        self.assertRedirects(post_res, reverse('console-partner-application-list'))

        app.refresh_from_db()
        self.assertEqual(app.status, PartnerApplication.Status.APPROVED)
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.is_partner)

    def test_admin_partner_application_rejection(self):
        app = PartnerApplication.objects.create(
            applicant=self.applicant,
            organization_name='Bogus Organization',
            institution_type='enterprise',
            contact_person_name='Fraudster',
            contact_email='scam@invalid.org',
            contact_phone='+95900000000',
            city='Unknown',
            description='Invalid partner'
        )
        self.client.login(username='admin_boss', password='Password123!')
        reject_url = reverse('console-partner-application-action', kwargs={'app_id': app.id, 'action': 'reject'})
        post_res = self.client.post(reject_url)
        self.assertRedirects(post_res, reverse('console-partner-application-list'))

        app.refresh_from_db()
        self.assertEqual(app.status, PartnerApplication.Status.REJECTED)

    def test_landing_page_and_directory_partner_showcase(self):
        # Public landing page contains verified partner
        res = self.client.get(reverse('landing-page'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('partners', res.context)
        self.assertContains(res, 'University of Information Technology (UIT)')

        # Partner Directory list contains verified partner
        dir_res = self.client.get(reverse('partner-list'))
        self.assertEqual(dir_res.status_code, 200)
        self.assertContains(dir_res, 'University of Information Technology (UIT)')
