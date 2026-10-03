from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.users.models import UserRole, AdminProfile, StudentProfile, TeacherProfile
from apps.console.views import ensure_role_profile

User = get_user_model()


class AdminConsoleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='super_admin', email='admin@mel.edu.mm', password='password123'
        )
        self.admin.role = UserRole.ADMIN
        self.admin.save()
        AdminProfile.objects.get_or_create(user=self.admin)

        self.student = User.objects.create_user(
            username='test_student', email='student@mel.edu.mm', password='password123'
        )
        self.client = Client()

    def test_anonymous_redirected(self):
        resp = self.client.get(reverse('console-home'))
        self.assertEqual(resp.status_code, 302)

    def test_student_forbidden(self):
        self.client.login(username='test_student', password='password123')
        resp = self.client.get(reverse('console-home'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_access_allowed(self):
        self.client.login(username='super_admin', password='password123')
        resp = self.client.get(reverse('console-home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Console")

    def test_console_user_list(self):
        self.client.login(username='super_admin', password='password123')
        resp = self.client.get(reverse('console-user-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "test_student")

    def test_ensure_role_profile_transitions(self):
        user = User.objects.create_user(
            username='role_shifter', email='shifter@mel.edu.mm', password='password123'
        )
        user.role = UserRole.TEACHER
        user.save()
        ensure_role_profile(user)
        self.assertTrue(TeacherProfile.objects.filter(user=user).exists())

        user.role = UserRole.ADMIN
        user.save()
        ensure_role_profile(user)
        self.assertTrue(AdminProfile.objects.filter(user=user).exists())
