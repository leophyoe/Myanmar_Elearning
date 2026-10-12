from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.courses.models import Quiz, Question, Choice, QuizAttempt
from apps.certificates.models import Certificate
from apps.billing.models import Payment, has_paid_standalone_exam
from apps.courses.services.assessment import (
    check_assessment_attempt_eligibility,
    serialize_exam_for_student,
    grade_assessment_attempt,
    manual_grade_attempt,
)

User = get_user_model()


class ExamCenterTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            username='exam_instructor',
            email='instructor@thuta.edu.mm',
            password='Password123!',
            role='instructor',
        )
        self.student = User.objects.create_user(
            username='exam_student',
            email='student@thuta.edu.mm',
            password='Password123!',
            role='student',
        )

        # 1. Free Standalone Practice Exam
        self.free_exam = Quiz.objects.create(
            title='Python Fundamentals Assessment',
            description='Test your core Python syntax and functions.',
            quiz_type=Quiz.AssessmentType.PRACTICE_EXAM,
            status=Quiz.Status.PUBLISHED,
            is_standalone=True,
            price=Decimal('0.00'),
            time_limit_minutes=30,
            passing_percentage=75,
            max_attempts=3,
            owner=self.instructor,
            assigned_instructor=self.instructor,
            certificate_type='none',
        )
        # Questions for free exam
        self.q1 = Question.objects.create(
            quiz=self.free_exam,
            order=1,
            prompt='Which keyword defines a function in Python?',
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=50,
            explanation='def is the keyword to define a function.',
        )
        self.c1_1 = Choice.objects.create(question=self.q1, text='def', is_correct=True)
        self.c1_2 = Choice.objects.create(question=self.q1, text='function', is_correct=False)
        self.c1_3 = Choice.objects.create(question=self.q1, text='fn', is_correct=False)

        self.q2 = Question.objects.create(
            quiz=self.free_exam,
            order=2,
            prompt='Which collection type is mutable?',
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=50,
            explanation='Lists are mutable.',
        )
        self.c2_1 = Choice.objects.create(question=self.q2, text='list', is_correct=True)
        self.c2_2 = Choice.objects.create(question=self.q2, text='tuple', is_correct=False)

        # 2. Paid Verified Certification Exam
        self.verified_exam = Quiz.objects.create(
            title='Certified Cyber Defense Associate (CCDA)',
            description='Professional examination testing network defense.',
            quiz_type=Quiz.AssessmentType.FINAL_EXAM,
            status=Quiz.Status.PUBLISHED,
            is_standalone=True,
            price=Decimal('35000.00'),
            time_limit_minutes=60,
            passing_percentage=80,
            max_attempts=2,
            owner=self.instructor,
            assigned_instructor=self.instructor,
            certificate_type='exam_verified',
            requires_manual_grading=False,
        )
        self.vq1 = Question.objects.create(
            quiz=self.verified_exam,
            order=1,
            prompt='Default SSH port number?',
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            points=100,
            explanation='Port 22 is used by default for SSH.',
        )
        self.vc1_1 = Choice.objects.create(question=self.vq1, text='22', is_correct=True)
        self.vc1_2 = Choice.objects.create(question=self.vq1, text='80', is_correct=False)

    def test_standalone_exam_catalog_view(self):
        resp = self.client.get(reverse('standalone-exam-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Python Fundamentals Assessment')
        self.assertContains(resp, 'Certified Cyber Defense Associate')

    def test_exam_detail_view(self):
        resp = self.client.get(reverse('standalone-exam-detail', kwargs={'exam_id': self.free_exam.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Python Fundamentals Assessment')
        self.assertContains(resp, 'FREE')

    def test_free_exam_eligibility(self):
        eligible, reason = check_assessment_attempt_eligibility(self.student, self.free_exam)
        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_paid_exam_eligibility_enforcement(self):
        # Student has not paid yet
        eligible, reason = check_assessment_attempt_eligibility(self.student, self.verified_exam)
        self.assertFalse(eligible)
        self.assertIn('purchase', reason.lower())

        # Admin or instructor owner is always authorized
        admin_eligible, _ = check_assessment_attempt_eligibility(self.instructor, self.verified_exam)
        self.assertTrue(admin_eligible)

        # Grant access via approved Payment
        payment = Payment.objects.create(
            student=self.student,
            exam=self.verified_exam,
            payment_type=Payment.PaymentType.EXAM_VOUCHER,
            amount=Decimal('35000.00'),
            status=Payment.Status.APPROVED,
        )
        self.assertTrue(has_paid_standalone_exam(self.student, self.verified_exam))
        eligible, reason = check_assessment_attempt_eligibility(self.student, self.verified_exam)
        self.assertTrue(eligible)

    def test_serialize_exam_never_leaks_answer_keys(self):
        payload = serialize_exam_for_student(self.free_exam)
        self.assertEqual(payload['title'], self.free_exam.title)
        self.assertEqual(payload['total_questions'], 2)

        for q in payload['questions']:
            # Critical: No answer keys or explanations in student payload
            self.assertNotIn('is_correct', q)
            self.assertNotIn('correct_text_answer', q)
            self.assertNotIn('explanation', q)
            self.assertNotIn('rubric_criteria', q)
            for c in q['choices']:
                self.assertNotIn('is_correct', c)

    def test_free_exam_submission_and_scoring(self):
        self.client.force_login(self.student)
        submit_data = {
            f'question_{self.q1.id}': str(self.c1_1.id), # Correct (50 pts)
            f'question_{self.q2.id}': str(self.c2_1.id), # Correct (50 pts)
            'time_taken_seconds': 120,
        }
        resp = self.client.post(
            reverse('exam-submit', kwargs={'exam_id': self.free_exam.id}),
            data=submit_data
        )
        self.assertEqual(resp.status_code, 302)

        attempt = QuizAttempt.objects.filter(student=self.student, quiz=self.free_exam).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.score_percentage, 100)
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.status, QuizAttempt.AttemptStatus.GRADED)

    def test_verified_exam_auto_issues_exam_certificate(self):
        # Authorize student
        Payment.objects.create(
            student=self.student,
            exam=self.verified_exam,
            payment_type=Payment.PaymentType.EXAM_VOUCHER,
            amount=Decimal('35000.00'),
            status=Payment.Status.APPROVED,
        )
        self.client.force_login(self.student)

        submit_data = {
            f'question_{self.vq1.id}': str(self.vc1_1.id), # Correct (100 pts)
            'time_taken_seconds': 240,
        }
        resp = self.client.post(
            reverse('exam-submit', kwargs={'exam_id': self.verified_exam.id}),
            data=submit_data
        )
        self.assertEqual(resp.status_code, 302)

        attempt = QuizAttempt.objects.filter(student=self.student, quiz=self.verified_exam).first()
        self.assertIsNotNone(attempt)
        self.assertTrue(attempt.passed)

        # Check issued Certificate
        cert = Certificate.objects.filter(student=self.student, exam=self.verified_exam).first()
        self.assertIsNotNone(cert)
        self.assertEqual(cert.certificate_type, Certificate.CertificateType.EXAM_VERIFIED)
        self.assertTrue(cert.certificate_code.startswith('MEL-EXAM-2026-'))
        self.assertEqual(cert.program_title, self.verified_exam.title)
        self.assertEqual(cert.exam_score, 100)

        # Check public certificate verification lookup
        lookup_resp = self.client.get(reverse('certificate-lookup') + f'?code={cert.certificate_code}')
        self.assertEqual(lookup_resp.status_code, 302)
        self.assertIn(str(cert.pk), lookup_resp.url)

    def test_manual_grading_rubric_workflow(self):
        # Create an exam requiring manual essay grading
        essay_exam = Quiz.objects.create(
            title='Cyber Threat Intelligence Practical Exam',
            status=Quiz.Status.PUBLISHED,
            is_standalone=True,
            price=Decimal('0.00'),
            passing_percentage=70,
            owner=self.instructor,
            assigned_instructor=self.instructor,
            certificate_type='exam_verified',
            requires_manual_grading=True,
        )
        essay_q = Question.objects.create(
            quiz=essay_exam,
            order=1,
            prompt='Explain the MITRE ATT&CK killchain stages in detail.',
            question_type=Question.QuestionType.SHORT_ANSWER,
            points=100,
            rubric_criteria='Clarity, identification of stages, and practical detection techniques.',
        )

        # Student submits essay
        attempt, msg = grade_assessment_attempt(
            assessment=essay_exam,
            user=self.student,
            submitted_answers={f'question_{essay_q.id}': 'Recon, Weaponization, Delivery, Exploitation, Installation, C2, Actions on Objectives.'},
            time_taken_seconds=500,
        )
        self.assertEqual(attempt.status, QuizAttempt.AttemptStatus.PENDING_REVIEW)
        self.assertFalse(attempt.passed)
        self.assertIsNone(attempt.certificate)

        # Instructor opens grading queue
        self.client.force_login(self.instructor)
        queue_resp = self.client.get(reverse('exam-grading-queue'))
        self.assertEqual(queue_resp.status_code, 200)
        self.assertContains(queue_resp, self.student.username)

        # Instructor grades via manual_grade_attempt
        rubric_scores = {
            str(essay_q.id): {
                'points': 90,
                'feedback': 'Excellent and comprehensive breakdown of the threat actor lifecycle.',
                'criteria_level': '3',
            }
        }
        updated = manual_grade_attempt(
            attempt=attempt,
            evaluator=self.instructor,
            rubric_scores=rubric_scores,
            overall_feedback='Outstanding performance. High level of technical competence.',
        )
        self.assertEqual(updated.status, QuizAttempt.AttemptStatus.GRADED)
        self.assertEqual(updated.score_percentage, 90)
        self.assertTrue(updated.passed)
        self.assertIsNotNone(updated.certificate)
        self.assertEqual(updated.certificate.certificate_type, Certificate.CertificateType.EXAM_VERIFIED)
        self.assertTrue(updated.certificate.certificate_code.startswith('MEL-EXAM-2026-'))

