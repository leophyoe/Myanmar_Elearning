import tempfile
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.users.models import User
from apps.courses.models import Course, Enrollment, Quiz, QuizAttempt
from apps.certificates.models import Certificate, CertificateTemplate
from apps.certificates.services import (
    issue_certificate_for_enrollment,
    issue_certificate_for_exam,
)


def create_dummy_image(name='template.png'):
    file = BytesIO()
    image = Image.new('RGB', (1000, 700), color=(30, 41, 59))
    image.save(file, 'PNG')
    file.seek(0)
    return SimpleUploadedFile(name, file.read(), content_type='image/png')


class CustomCertificateTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            username='leadinstructor',
            email='instructor@example.com',
            password='Password123!',
            first_name='Ko',
            last_name='Zaw',
            role='instructor',
        )
        self.student = User.objects.create_user(
            username='studenttest',
            email='student@example.com',
            password='Password123!',
            first_name='Min',
            last_name='Thu',
            role='student',
        )

    def test_create_builtin_theme_template(self):
        tpl = CertificateTemplate.objects.create(
            title="Advanced Cyber Diploma Theme",
            created_by=self.instructor,
            design_mode=CertificateTemplate.DesignMode.BUILTIN,
            theme_style=CertificateTemplate.ThemeStyle.CYBER_TECH,
            font_choice=CertificateTemplate.FontChoice.CINZEL,
            institution_name="THUTA CYBER DEFENSE ACADEMY",
            header_title="CERTIFIED ETHICAL DEFENDER",
            primary_color="#06B6D4",
            accent_color="#0F172A",
        )
        self.assertEqual(tpl.theme_style, 'cyber_tech')
        self.assertEqual(tpl.font_choice, 'cinzel')
        self.assertEqual(tpl.header_title, "CERTIFIED ETHICAL DEFENDER")

    def test_create_custom_upload_template_with_image_and_coordinates(self):
        bg_image = create_dummy_image('my_custom_cert.png')
        tpl = CertificateTemplate.objects.create(
            title="My Institution Custom Canva Template",
            created_by=self.instructor,
            design_mode=CertificateTemplate.DesignMode.CUSTOM_UPLOAD,
            background_image=bg_image,
            name_pos_top=48,
            name_color="#1E293B",
            name_font_size=36,
            title_pos_top=60,
            date_pos_top=80,
            date_pos_left=25,
            qr_pos_top=75,
            qr_pos_left=50,
            serial_pos_top=90,
            serial_pos_left=50,
        )
        self.assertEqual(tpl.design_mode, 'custom_upload')
        self.assertTrue(bool(tpl.background_image))
        self.assertEqual(tpl.name_pos_top, 48)

    def test_course_issuance_uses_assigned_template(self):
        tpl = CertificateTemplate.objects.create(
            title="Specialized Python Diploma",
            created_by=self.instructor,
            design_mode=CertificateTemplate.DesignMode.BUILTIN,
            theme_style=CertificateTemplate.ThemeStyle.ACADEMIC_EMERALD,
        )
        course = Course.objects.create(
            title="Python Masterclass",
            slug="python-masterclass",
            description="Complete Python Guide",
            certificate_eligible=True,
            certificate_template=tpl,
        )
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=course,
            status=Enrollment.Status.COMPLETED,
            progress_pct=100,
        )
        cert = issue_certificate_for_enrollment(enrollment)
        self.assertIsNotNone(cert)
        self.assertEqual(cert.template, tpl)
        self.assertEqual(cert.effective_template, tpl)

    def test_exam_issuance_uses_assigned_template(self):
        tpl = CertificateTemplate.objects.create(
            title="Certified Practitioner Diploma",
            created_by=self.instructor,
            design_mode=CertificateTemplate.DesignMode.BUILTIN,
            theme_style=CertificateTemplate.ThemeStyle.CLASSIC_GOLD,
        )
        exam = Quiz.objects.create(
            title="Practical Security Examination",
            certificate_template=tpl,
            certificate_type='exam_verified',
            passing_percentage=70,
        )
        attempt = QuizAttempt.objects.create(
            quiz=exam,
            student=self.student,
            score_percentage=85,
            passed=True,
        )
        cert = issue_certificate_for_exam(attempt, verified_by=self.instructor)
        self.assertIsNotNone(cert)
        self.assertEqual(cert.template, tpl)
        self.assertEqual(cert.effective_template, tpl)

    def test_verification_page_renders_diploma_and_preserves_privacy(self):
        bg_image = create_dummy_image('uploaded_template.png')
        tpl = CertificateTemplate.objects.create(
            title="Custom Upload Background Diploma",
            created_by=self.instructor,
            design_mode=CertificateTemplate.DesignMode.CUSTOM_UPLOAD,
            background_image=bg_image,
            name_pos_top=45,
            title_pos_top=55,
        )
        course = Course.objects.create(
            title="Executive Cyber Defense",
            slug="executive-cyber-defense",
            certificate_template=tpl,
            certificate_eligible=True,
        )
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=course,
            status=Enrollment.Status.COMPLETED,
            progress_pct=100,
        )
        cert = issue_certificate_for_enrollment(enrollment)

        verify_url = reverse('canonical-verify', kwargs={'code': cert.certificate_code})
        resp = self.client.get(verify_url)
        self.assertEqual(resp.status_code, 200)

        # Confirm certificate credentials are shown
        self.assertContains(resp, cert.certificate_code)
        self.assertContains(resp, cert.student_name)
        self.assertContains(resp, cert.program_title)
        self.assertContains(resp, "Print / Save PDF")
        self.assertContains(resp, "Download PNG")

        # Confirm student private email is NOT exposed
        self.assertNotContains(resp, self.student.email)

    def test_certificate_template_studio_views(self):
        self.client.force_login(self.instructor)

        # 1. Template List View
        resp_list = self.client.get(reverse('certificate-template-list'))
        self.assertEqual(resp_list.status_code, 200)

        # 2. Template Create View (GET)
        resp_create = self.client.get(reverse('certificate-template-create'))
        self.assertEqual(resp_create.status_code, 200)

        # 3. Template Create View (POST)
        post_data = {
            'title': 'New Test Template',
            'design_mode': 'builtin',
            'theme_style': 'cyber_tech',
            'font_choice': 'inter',
            'institution_name': 'TEST ACADEMY',
            'header_title': 'CERTIFICATE OF ACHIEVEMENT',
            'subtitle': 'Presented to',
            'body_text': 'for completing',
            'primary_color': '#06B6D4',
            'accent_color': '#0F172A',
            'name_pos_top': 44,
            'name_color': '#1E293B',
            'name_font_size': 34,
            'title_pos_top': 58,
            'title_color': '#0F172A',
            'title_font_size': 22,
            'date_pos_top': 78,
            'date_pos_left': 22,
            'qr_pos_top': 76,
            'qr_pos_left': 50,
            'serial_pos_top': 88,
            'serial_pos_left': 50,
            'show_qr_code': True,
            'show_seal': True,
            'is_active': True,
        }
        resp_post = self.client.post(reverse('certificate-template-create'), post_data)
        self.assertEqual(resp_post.status_code, 302)
        created_tpl = CertificateTemplate.objects.filter(title='New Test Template').first()
        self.assertIsNotNone(created_tpl)
        self.assertEqual(created_tpl.created_by, self.instructor)

        # 4. Template Preview View
        resp_prev = self.client.get(reverse('certificate-template-preview', kwargs={'pk': created_tpl.pk}))
        self.assertEqual(resp_prev.status_code, 200)
        self.assertContains(resp_prev, 'New Test Template')
        self.assertContains(resp_prev, 'Mg Aung Kyaw Moe')

        # 5. Template Duplicate View (POST)
        resp_dup = self.client.post(reverse('certificate-template-duplicate', kwargs={'pk': created_tpl.pk}))
        self.assertEqual(resp_dup.status_code, 302)
        duplicated = CertificateTemplate.objects.filter(title='New Test Template (Copy)').first()
        self.assertIsNotNone(duplicated)
        self.assertEqual(duplicated.created_by, self.instructor)
        self.assertEqual(duplicated.theme_style, 'cyber_tech')
        self.assertEqual(duplicated.primary_color, '#06B6D4')
        self.assertFalse(duplicated.is_default)

