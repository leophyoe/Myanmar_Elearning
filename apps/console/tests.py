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


class UserDeletionAndMMQRTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.timezone = timezone

        self.admin = User.objects.create_superuser(
            username='admin_main', email='admin_main@mel.edu.mm', password='Password123!'
        )
        self.admin.role = UserRole.ADMIN
        self.admin.save()
        AdminProfile.objects.get_or_create(user=self.admin)

        self.secondary_admin = User.objects.create_user(
            username='admin_second', email='admin_second@mel.edu.mm', password='Password123!'
        )
        self.secondary_admin.role = UserRole.ADMIN
        self.secondary_admin.save()
        AdminProfile.objects.get_or_create(user=self.secondary_admin)

        self.student = User.objects.create_user(
            username='regular_student', email='student@mel.edu.mm', password='Password123!'
        )
        self.student.role = UserRole.STUDENT
        self.student.save()
        StudentProfile.objects.get_or_create(user=self.student)

        self.client = Client()
        self.client.login(username='admin_main', password='Password123!')

    def test_admin_account_model_deletion_protection(self):
        """Admin accounts cannot be scheduled for deletion via model method."""
        with self.assertRaises(ValueError) as ctx:
            self.secondary_admin.schedule_deletion(requested_by=self.admin)
        self.assertIn("Administrator accounts cannot be deleted", str(ctx.exception))

    def test_admin_account_view_deletion_blocked(self):
        """Admin accounts cannot be deleted via console delete view."""
        # GET page indicates restricted
        resp = self.client.get(reverse('console-user-delete', kwargs={'user_id': self.secondary_admin.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Deletion Strictly Restricted")
        self.assertContains(resp, "Protected")

        # POST attempt is blocked
        post_resp = self.client.post(
            reverse('console-user-delete', kwargs={'user_id': self.secondary_admin.pk}),
            {'reason': 'Malicious attempt'}
        )
        self.secondary_admin.refresh_from_db()
        self.assertFalse(self.secondary_admin.is_pending_deletion)
        self.assertTrue(self.secondary_admin.is_active)

    def test_admin_self_deletion_blocked(self):
        """Admin cannot delete their own account."""
        resp = self.client.get(reverse('console-user-delete', kwargs={'user_id': self.admin.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Deletion Strictly Restricted")

        post_resp = self.client.post(
            reverse('console-user-delete', kwargs={'user_id': self.admin.pk}),
            {'reason': 'Self deletion attempt'}
        )
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_pending_deletion)
        self.assertTrue(self.admin.is_active)

    def test_standard_user_scheduled_for_deletion_48_hours(self):
        """Standard users are deactivated immediately and queued with 48h cooling-off."""
        resp = self.client.post(
            reverse('console-user-delete', kwargs={'user_id': self.student.pk}),
            {'reason': 'Requested account closure'}
        )
        self.student.refresh_from_db()

        self.assertTrue(self.student.is_pending_deletion)
        self.assertFalse(self.student.is_active)  # deactivated immediately
        self.assertEqual(self.student.deletion_requested_by, self.admin)
        self.assertEqual(self.student.deletion_reason, 'Requested account closure')
        self.assertIsNotNone(self.student.deletion_due_at)

        # Verify due time is ~48 hours ahead
        diff = self.student.deletion_due_at - self.timezone.now()
        self.assertGreaterEqual(diff.total_seconds(), 47 * 3600)
        self.assertLessEqual(diff.total_seconds(), 48 * 3600 + 60)
        self.assertFalse(self.student.is_deletion_due)

    def test_cancel_deletion_restores_user_account(self):
        """Admins can cancel scheduled deletion within 48h, restoring account to active."""
        self.student.schedule_deletion(requested_by=self.admin, reason='Accidental')
        self.assertTrue(self.student.is_pending_deletion)
        self.assertFalse(self.student.is_active)

        cancel_resp = self.client.post(
            reverse('console-user-cancel-deletion', kwargs={'user_id': self.student.pk})
        )
        self.student.refresh_from_db()

        self.assertFalse(self.student.is_pending_deletion)
        self.assertTrue(self.student.is_active)
        self.assertIsNone(self.student.deletion_scheduled_at)
        self.assertIsNone(self.student.deletion_due_at)

    def test_purge_blocked_before_48_hours(self):
        """Permanent purge is refused if 48h cooling-off period has not expired."""
        self.student.schedule_deletion(requested_by=self.admin)
        purge_resp = self.client.post(
            reverse('console-user-purge', kwargs={'user_id': self.student.pk})
        )
        # Student should still exist
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())

    def test_purge_allowed_after_48_hours_expire(self):
        """Permanent purge succeeds once 48h cooling-off period has expired."""
        import datetime
        self.student.schedule_deletion(requested_by=self.admin)
        # Fast-forward deletion_due_at to the past
        self.student.deletion_due_at = self.timezone.now() - datetime.timedelta(minutes=5)
        self.student.save()

        self.assertTrue(self.student.is_deletion_due)
        purge_resp = self.client.post(
            reverse('console-user-purge', kwargs={'user_id': self.student.pk})
        )
        self.assertFalse(User.objects.filter(pk=self.student.pk).exists())

    def test_admin_cannot_be_purged(self):
        """Admin accounts cannot be purged even via purge endpoint."""
        purge_resp = self.client.post(
            reverse('console-user-purge', kwargs={'user_id': self.secondary_admin.pk})
        )
        self.assertTrue(User.objects.filter(pk=self.secondary_admin.pk).exists())

    def test_mmqr_navigation_discovery_points(self):
        """MMQR payment settings are discoverable in console and accessible to admins."""
        # Billing payment settings URL
        resp_billing = self.client.get(reverse('billing:payment-settings'))
        self.assertEqual(resp_billing.status_code, 200)

        # Console payment settings URL
        resp_console = self.client.get(reverse('console-payment-settings'))
        self.assertEqual(resp_console.status_code, 200)

        # Console overview page displays MMQR gateway card and quick action
        resp_home = self.client.get(reverse('console-home'))
        self.assertEqual(resp_home.status_code, 200)
        self.assertContains(resp_home, "MMQR")

