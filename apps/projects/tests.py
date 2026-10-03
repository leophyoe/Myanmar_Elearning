from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import FinalProject, ProjectSubmission

User = get_user_model()


class CapstoneProjectTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='capstone_student', email='student@mel.edu.mm', password='password123'
        )
        self.instructor = User.objects.create_user(
            username='capstone_evaluator', email='eval@mel.edu.mm', password='password123'
        )
        self.project = FinalProject.objects.create(
            title="Enterprise Cloud SOC Capstone",
            slug="enterprise-cloud-soc-capstone",
            description="Build a production security monitoring infrastructure.",
            rubric={"proposal": 15, "lab": 20, "assessment": 25, "report": 20, "viva": 20},
            is_active=True,
        )
        self.client = Client()

    def test_project_list_view(self):
        self.client.login(username='capstone_student', password='password123')
        resp = self.client.get(reverse('project-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Enterprise Cloud SOC Capstone")

    def test_proposal_submission_flow(self):
        self.client.login(username='capstone_student', password='password123')
        submit_url = reverse('project-submit-proposal', kwargs={'slug': self.project.slug})
        resp = self.client.post(submit_url, {
            'proposal_text': 'This is my comprehensive capstone architecture proposal.',
            'github_repo_url': 'https://github.com/capstone/soc-capstone',
        })
        self.assertEqual(resp.status_code, 302)

        sub = ProjectSubmission.objects.get(project=self.project, student=self.student)
        self.assertEqual(sub.status, ProjectSubmission.Status.SUBMITTED)
        self.assertEqual(sub.github_repo_url, 'https://github.com/capstone/soc-capstone')

    def test_project_submission_detail_view(self):
        sub = ProjectSubmission.objects.create(
            project=self.project,
            student=self.student,
            status=ProjectSubmission.Status.APPROVED,
            proposal_text="Approved proposal text.",
        )
        self.client.login(username='capstone_student', password='password123')
        detail_url = reverse('project-submission-detail', kwargs={'slug': self.project.slug})
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Approved proposal text.")
