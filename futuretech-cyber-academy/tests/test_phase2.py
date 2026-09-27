import os
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from apps.accounts.models import User, RoleChoices
from apps.courses.models import Course, CourseModule, Lesson, LessonType, CourseStatus, CourseLevel
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress
from apps.assessments.models import (
    QuestionBank, Quiz, Question, QuestionOption, QuestionType,
    QuizAttempt, QuizAnswer, Assignment, AssignmentSubmission, AssignmentFeedback,
    SubmissionStatus, Exam, ExamType, ExamQuestion, ExamOption, ExamAttempt, ExamAnswer,
    PracticalLabTask, AssessmentWeight
)
from apps.assessments.services import QuizGradingService, ExamTimerService, GradeCalculationService
from apps.learning_paths.models import LearningPath, LearningPathCourse, StudentLearningPath, LearningPathLevel
from apps.certificates.models import Certificate, CertificateTemplate, CertificateStatus
from apps.certificates.services import CertificateGenerationService
from apps.achievements.models import Achievement, StudentAchievement, BadgeType
from apps.achievements.services import AchievementEvaluationService
from apps.courses.completion_service import CourseCompletionService
from apps.core.validators import validate_resource_file


class QuizSystemTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor.mor@futuretech.edu", username="instructor_mor",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="neo@futuretech.edu", username="neo",
            role=RoleChoices.STUDENT
        )
        self.client = Client()
        self.course = Course.objects.create(
            title="Defensive Operations 101", slug="defensive-ops-101",
            level=CourseLevel.BEGINNER, status=CourseStatus.PUBLISHED, created_by=self.instructor
        )
        self.module = CourseModule.objects.create(course=self.course, title="Module 1", slug="mod-1", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Lesson 1", slug="les-1",
            lesson_type=LessonType.ARTICLE, order=1
        )
        self.quiz = Quiz.objects.create(
            course=self.course, lesson=self.lesson,
            title="Fundamentals Quiz", time_limit_minutes=15,
            passing_score=70, max_attempts=2, is_published=True
        )
        # Add 3 questions: Multiple Choice, Multiple Select, True/False
        self.q1 = Question.objects.create(
            quiz=self.quiz, order=1, question_text="What is 2+2?",
            question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('5.00')
        )
        self.q1_opt1 = QuestionOption.objects.create(question=self.q1, option_text="4", is_correct=True, order=1)
        self.q1_opt2 = QuestionOption.objects.create(question=self.q1, option_text="5", is_correct=False, order=2)

        self.q2 = Question.objects.create(
            quiz=self.quiz, order=2, question_text="Select primary colors:",
            question_type=QuestionType.MULTIPLE_SELECT, points=Decimal('5.00')
        )
        self.q2_opt1 = QuestionOption.objects.create(question=self.q2, option_text="Red", is_correct=True, order=1)
        self.q2_opt2 = QuestionOption.objects.create(question=self.q2, option_text="Blue", is_correct=True, order=2)
        self.q2_opt3 = QuestionOption.objects.create(question=self.q2, option_text="Green", is_correct=False, order=3)

        self.q3 = Question.objects.create(
            quiz=self.quiz, order=3, question_text="Zero Trust assumes breach.",
            question_type=QuestionType.TRUE_FALSE, points=Decimal('5.00')
        )
        self.q3_opt1 = QuestionOption.objects.create(question=self.q3, option_text="True", is_correct=True, order=1)
        self.q3_opt2 = QuestionOption.objects.create(question=self.q3, option_text="False", is_correct=False, order=2)

    def test_quiz_properties(self):
        """Verify quiz total points and question count calculations."""
        self.assertEqual(self.quiz.question_count, 3)
        self.assertEqual(self.quiz.total_points, Decimal('15.00'))

    def test_zero_trust_answer_key_secrecy(self):
        """Ensure quiz take interface does not leak is_correct in the HTML form or context."""
        self.client.force_login(self.student)
        url = reverse('assessments:quiz-take', kwargs={'pk': self.quiz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Answer secrecy check: is_correct must never appear in response context or html
        self.assertNotContains(response, 'is_correct')
        self.assertNotIn('is_correct', str(response.context))

    def test_quiz_grading_service_scoring(self):
        """Test server-authoritative automated grading for multiple types."""
        attempt = QuizAttempt.objects.create(student=self.student, quiz=self.quiz, attempt_number=1)

        # Submit answers: Correct Q1, Correct Q2 (both options), Incorrect Q3
        submitted_data = {
            str(self.q1.id): str(self.q1_opt1.id),
            str(self.q2.id): [str(self.q2_opt1.id), str(self.q2_opt2.id)],
            str(self.q3.id): str(self.q3_opt2.id),  # False is incorrect
        }

        updated_attempt = QuizGradingService.grade_attempt(attempt, submitted_data)
        self.assertTrue(updated_attempt.is_completed)
        self.assertEqual(updated_attempt.score, Decimal('10.00'))
        # 10 / 15 = 66.67%
        self.assertEqual(updated_attempt.percentage, Decimal('66.67'))
        # Passing score is 70% -> should fail
        self.assertFalse(updated_attempt.passed)

        # 2nd attempt with all correct
        attempt2 = QuizAttempt.objects.create(student=self.student, quiz=self.quiz, attempt_number=2)
        perfect_data = {
            str(self.q1.id): str(self.q1_opt1.id),
            str(self.q2.id): [str(self.q2_opt1.id), str(self.q2_opt2.id)],
            str(self.q3.id): str(self.q3_opt1.id),
        }
        updated_attempt2 = QuizGradingService.grade_attempt(attempt2, perfect_data)
        self.assertTrue(updated_attempt2.passed)
        self.assertEqual(updated_attempt2.percentage, Decimal('100.00'))


class AssignmentSystemTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="ins.mor@futuretech.edu", username="ins_mor",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="student.alice@futuretech.edu", username="alice",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="Cloud Security Architecture", slug="cloud-sec-arch",
            level=CourseLevel.INTERMEDIATE, status=CourseStatus.PUBLISHED, created_by=self.instructor
        )
        self.assignment = Assignment.objects.create(
            course=self.course, title="AWS IAM Hardening Audit",
            description="Audit IAM policies", instructions="Submit PDF report",
            max_score=Decimal('100.00'), allowed_file_types=['pdf', 'zip'], max_file_size_mb=10
        )
        self.client = Client()

    def test_file_extension_security_validation(self):
        """Ensure dangerous executables/scripts are rejected while valid PDFs are permitted."""
        valid_pdf = SimpleUploadedFile("audit.pdf", b"%PDF-1.4 header content", content_type="application/pdf")
        malicious_exe = SimpleUploadedFile("exploit.exe", b"MZ\x90\x00\x03\x00\x00\x00", content_type="application/x-dosexec")
        malicious_sh = SimpleUploadedFile("backdoor.sh", b"#!/bin/bash\nrm -rf /", content_type="text/x-shellscript")

        # validate_resource_file should allow PDF
        try:
            validate_resource_file(valid_pdf)
        except ValidationError:
            self.fail("validate_resource_file incorrectly rejected valid PDF")

        # validate_resource_file must reject .exe and .sh
        with self.assertRaises(ValidationError):
            validate_resource_file(malicious_exe)
        with self.assertRaises(ValidationError):
            validate_resource_file(malicious_sh)

    def test_assignment_submission_and_grading_workflow(self):
        """Test submission creation, resubmission versioning, and instructor grading feedback."""
        self.client.force_login(self.student)
        submit_url = reverse('assessments:assignment-submit', kwargs={'pk': self.assignment.id})

        # Submit as student
        response = self.client.post(submit_url, {
            'submission_text': 'Completed IAM policy audit with zero wildcard permissions.'
        })
        self.assertEqual(response.status_code, 302)

        submission = AssignmentSubmission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(submission.status, SubmissionStatus.SUBMITTED)
        self.assertEqual(submission.version, 1)

        # Instructor grades submission
        self.client.force_login(self.instructor)
        grade_url = reverse('assessments:instructor-grade-submission', kwargs={'pk': submission.id})
        grade_resp = self.client.post(grade_url, {
            'score': '92.50',
            'feedback': 'Excellent least-privilege analysis!'
        })
        self.assertEqual(grade_resp.status_code, 302)

        submission.refresh_from_db()
        self.assertEqual(submission.status, SubmissionStatus.GRADED)
        self.assertEqual(submission.latest_feedback.score, Decimal('92.50'))
        self.assertEqual(submission.latest_feedback.instructor, self.instructor)


class ExamSystemTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="exam.lead@futuretech.edu", username="exam_lead",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="student.bob@futuretech.edu", username="bob",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="Enterprise Threat Hunting", slug="enterprise-threat-hunting",
            level=CourseLevel.ADVANCED, status=CourseStatus.PUBLISHED, created_by=self.instructor
        )
        self.exam = Exam.objects.create(
            course=self.course, title="Comprehensive Final Exam",
            exam_type=ExamType.FINAL, duration_minutes=60,
            passing_score=75, max_attempts=1, is_published=True
        )
        self.eq1 = ExamQuestion.objects.create(
            exam=self.exam, order=1, question_text="What does SIEM stand for?",
            question_type=QuestionType.MULTIPLE_CHOICE, points=Decimal('10.00')
        )
        self.eo1 = ExamOption.objects.create(
            question=self.eq1, option_text="Security Information and Event Management",
            is_correct=True, order=1
        )
        self.eo2 = ExamOption.objects.create(
            question=self.eq1, option_text="System Internet Email Monitor",
            is_correct=False, order=2
        )

        # Practical lab task placeholder for Phase 3 Docker integration
        self.lab_task = PracticalLabTask.objects.create(
            exam=self.exam, title="Isolate Rogue Process",
            instructions="Identify and kill rogue reverse shell",
            docker_template_id="cyber-range/linux-sec-lab",
            points=Decimal('25.00')
        )

    def test_exam_server_authoritative_timer(self):
        """Verify exam countdown timer calculates expires_at and detects expiration."""
        attempt = ExamTimerService.start_exam_attempt(self.student, self.exam)
        self.assertIsNotNone(attempt.expires_at)
        expected_expiry = attempt.started_at + timezone.timedelta(minutes=60)
        self.assertAlmostEqual(
            attempt.expires_at.timestamp(), expected_expiry.timestamp(), delta=5
        )
        self.assertFalse(attempt.is_expired)

        # Simulate expired attempt beyond grace period
        attempt.expires_at = timezone.now() - timezone.timedelta(minutes=5)
        attempt.save()
        self.assertTrue(attempt.is_expired)

    def test_practical_lab_task_interface_ready_for_phase3(self):
        """Ensure PracticalLabTask model adheres to Docker lab specifications for Phase 3."""
        self.assertEqual(self.exam.lab_tasks.count(), 1)
        task = self.exam.lab_tasks.first()
        self.assertEqual(task.docker_template_id, "cyber-range/linux-sec-lab")
        self.assertEqual(task.verification_method, "AUTOMATED_FLAG")


class LearningPathTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="path.lead@futuretech.edu", username="path_lead",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="student.path@futuretech.edu", username="stu_path",
            role=RoleChoices.STUDENT
        )
        self.c1 = Course.objects.create(
            title="Course 1", slug="c1", created_by=self.instructor,
            status=CourseStatus.PUBLISHED
        )
        self.c2 = Course.objects.create(
            title="Course 2", slug="c2", created_by=self.instructor,
            status=CourseStatus.PUBLISHED
        )
        self.path = LearningPath.objects.create(
            title="SOC Analyst Career Path", slug="soc-analyst-career-path",
            estimated_months=6, level=LearningPathLevel.INTERMEDIATE
        )
        LearningPathCourse.objects.create(learning_path=self.path, course=self.c1, order=1)
        LearningPathCourse.objects.create(learning_path=self.path, course=self.c2, order=2)

    def test_learning_path_progress_recalculation(self):
        """Test cumulative progress calculation across enrolled courses."""
        enr1 = Enrollment.objects.create(
            student=self.student, course=self.c1, progress_percentage=Decimal('100.00'),
            status=EnrollmentStatus.COMPLETED
        )
        enr2 = Enrollment.objects.create(
            student=self.student, course=self.c2, progress_percentage=Decimal('50.00'),
            status=EnrollmentStatus.ACTIVE
        )

        stu_path = StudentLearningPath.objects.create(
            student=self.student, learning_path=self.path
        )
        progress = stu_path.recalculate_progress()
        # (100 + 50) / 2 = 75.00%
        self.assertEqual(progress, Decimal('75.00'))
        self.assertEqual(stu_path.status, "ACTIVE")

        # Now complete Course 2
        enr2.progress_percentage = Decimal('100.00')
        enr2.status = EnrollmentStatus.COMPLETED
        enr2.save()

        progress2 = stu_path.recalculate_progress()
        self.assertEqual(progress2, Decimal('100.00'))
        self.assertEqual(stu_path.status, "COMPLETED")


class CertificateAndVerificationTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="dean@futuretech.edu", username="dean_mor",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="thomas.anderson@futuretech.edu", username="thomas_a",
            role=RoleChoices.STUDENT, first_name="Thomas", last_name="Anderson"
        )
        self.course = Course.objects.create(
            title="Certificate in Advanced Penetration Testing", slug="cert-adv-pentest",
            created_by=self.instructor, status=CourseStatus.PUBLISHED
        )
        self.client = Client()

    def test_certificate_generation_and_vector_qr(self):
        """Test certificate issuance, format, and pure-vector SVG QR generation."""
        cert = CertificateGenerationService.issue_certificate(self.student, self.course)
        self.assertIsNotNone(cert)
        self.assertTrue(cert.certificate_number.startswith("FTCSA-"))
        self.assertIsNotNone(cert.verification_token)
        self.assertEqual(cert.status, CertificateStatus.ISSUED)
        # Vector QR SVG check
        self.assertTrue(cert.qr_code_svg.startswith("<svg"))
        self.assertIn("</svg>", cert.qr_code_svg)

        # Prevent duplicate certificates for same student and course
        cert2 = CertificateGenerationService.issue_certificate(self.student, self.course)
        self.assertEqual(cert.id, cert2.id)

    def test_public_verification_gateway_pii_shield(self):
        """Anonymous verification endpoint must verify validity while protecting student PII."""
        cert = CertificateGenerationService.issue_certificate(self.student, self.course)
        verify_url = reverse('certificates:public-verify', kwargs={'certificate_number': cert.certificate_number})

        # Anonymous client accesses verification portal
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cert.certificate_number)
        self.assertContains(response, self.course.title)
        self.assertContains(response, "Thomas Anderson")
        # PII Shield: Student email must NEVER be exposed publicly
        self.assertNotContains(response, "thomas.anderson@futuretech.edu")


class GradebookAndCompletionTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor.grade@futuretech.edu", username="ins_grade",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="neo.grades@futuretech.edu", username="neo_grades",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="Certified Cyber Architect", slug="cert-cyber-arch",
            created_by=self.instructor, status=CourseStatus.PUBLISHED
        )
        self.weights = AssessmentWeight.objects.create(
            course=self.course,
            assignments_weight=Decimal('20.00'),
            quizzes_weight=Decimal('20.00'),
            labs_weight=Decimal('20.00'),
            module_exams_weight=Decimal('20.00'),
            practical_exam_weight=Decimal('10.00'),
            final_project_weight=Decimal('10.00')
        )

    def test_weighted_gradebook_and_letter_grade(self):
        """Verify weighted composite grade and letter grade calculation."""
        # Quiz: 90%
        quiz = Quiz.objects.create(course=self.course, title="Q1", is_published=True)
        QuizAttempt.objects.create(
            student=self.student, quiz=quiz, score=Decimal('9.00'),
            percentage=Decimal('90.00'), passed=True, is_completed=True
        )

        # Assignment: 80%
        assign = Assignment.objects.create(
            course=self.course, title="A1", max_score=Decimal('100.00')
        )
        sub = AssignmentSubmission.objects.create(
            assignment=assign, student=self.student, status=SubmissionStatus.GRADED
        )
        AssignmentFeedback.objects.create(
            submission=sub, instructor=self.instructor, score=Decimal('80.00'), feedback="Well done"
        )

        grade_data = GradeCalculationService.calculate_student_grade(self.student, self.course)
        self.assertIn('final_grade', grade_data)
        self.assertIn('letter_grade', grade_data)
        # Assignment (20% * 80% = 16) + Quiz (20% * 90% = 18) + Default Lab (20% * 100% = 20) = 54.00%
        self.assertEqual(grade_data['final_grade'], 54.00)
        self.assertEqual(grade_data['letter_grade'], 'F')

    def test_course_completion_triggers_certificate_and_achievements(self):
        """Verify full completion pipeline: lessons + quiz + assignment + exam -> Certificate & Badge."""
        # Ensure template exists
        CertificateTemplate.objects.get_or_create(
            title="Certificate in Cyber Security",
            defaults={'is_default': True}
        )
        # Ensure badge exists
        Achievement.objects.get_or_create(
            code='COURSE_COMPLETER',
            defaults={
                'title': 'Course Graduate', 'description': 'Completed 100% of coursework',
                'badge_type': BadgeType.PLATINUM, 'points': 100
            }
        )

        enrollment = Enrollment.objects.create(
            student=self.student, course=self.course, progress_percentage=Decimal('0.00')
        )
        module = CourseModule.objects.create(course=self.course, title="M1", order=1)
        lesson = Lesson.objects.create(module=module, title="L1", lesson_type=LessonType.ARTICLE, order=1)

        # 1. Complete Lesson
        LessonProgress.objects.create(student=self.student, lesson=lesson, completed=True)

        # 2. Pass Quiz
        quiz = Quiz.objects.create(course=self.course, title="Q1", passing_score=70, is_published=True)
        QuizAttempt.objects.create(student=self.student, quiz=quiz, score=Decimal('10.00'), percentage=Decimal('100.00'), passed=True, is_completed=True)

        # 3. Submit Assignment
        assign = Assignment.objects.create(course=self.course, title="A1", status='PUBLISHED')
        AssignmentSubmission.objects.create(assignment=assign, student=self.student, status=SubmissionStatus.SUBMITTED)

        # 4. Pass Exam
        exam = Exam.objects.create(course=self.course, title="E1", passing_score=70, is_published=True)
        ExamAttempt.objects.create(student=self.student, exam=exam, percentage=Decimal('85.00'), passed=True, is_completed=True)

        result = CourseCompletionService.check_and_complete_course(self.student, self.course)
        self.assertTrue(result['eligible'])
        self.assertTrue(result['completed'])

        # Verify enrollment updated
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, EnrollmentStatus.COMPLETED)
        self.assertEqual(enrollment.progress_percentage, Decimal('100.00'))

        # Verify certificate issued
        cert = Certificate.objects.filter(student=self.student, course=self.course).first()
        self.assertIsNotNone(cert)
        self.assertTrue(cert.certificate_number.startswith("FTCSA-"))

        # Verify achievement awarded
        has_badge = StudentAchievement.objects.filter(
            student=self.student, achievement__code='COURSE_COMPLETER'
        ).exists()
        self.assertTrue(has_badge)


class AdditionalPhase2SecurityTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="ins.sec@futuretech.edu", username="ins_sec",
            role=RoleChoices.INSTRUCTOR, is_staff=True
        )
        self.student = User.objects.create_user(
            email="student.sec@futuretech.edu", username="stu_sec",
            role=RoleChoices.STUDENT
        )
        self.course = Course.objects.create(
            title="Penetration Testing Lab", slug="pen-test-lab",
            created_by=self.instructor, status=CourseStatus.PUBLISHED
        )
        self.exam = Exam.objects.create(
            course=self.course, title="Offensive Security Exam",
            duration_minutes=30, is_published=True
        )

    def test_expired_exam_submission_strictly_rejected(self):
        """Ensure server-authoritative timer rejects submissions after expiration plus grace period."""
        attempt = ExamTimerService.start_exam_attempt(self.student, self.exam)
        # Force expired timestamp: 10 minutes ago
        attempt.expires_at = timezone.now() - timezone.timedelta(minutes=10)
        attempt.save()

        with self.assertRaises(ValueError) as ctx:
            ExamTimerService.submit_exam_attempt(attempt, {})
        self.assertIn("Exam time limit expired", str(ctx.exception))

    def test_achievement_milestone_evaluation(self):
        """Verify gamification engine awards badges for milestones without duplicates."""
        ach_first = Achievement.objects.create(
            code='FIRST_STEP', title='First Step', description='First enrollment',
            badge_type=BadgeType.BRONZE, points=10
        )
        ach_perf = Achievement.objects.create(
            code='PERFECT_SCORE', title='Flawless', description='100% score',
            badge_type=BadgeType.GOLD, points=50
        )

        # Trigger enrollment
        awarded = AchievementEvaluationService.evaluate_student(self.student, event="ENROLLMENT")
        self.assertEqual(len(awarded), 1)
        self.assertEqual(awarded[0].code, 'FIRST_STEP')

        # Trigger duplicate enrollment -> no new badge
        awarded_dup = AchievementEvaluationService.evaluate_student(self.student, event="ENROLLMENT")
        self.assertEqual(len(awarded_dup), 0)

        # Trigger quiz 100% score
        awarded_quiz = AchievementEvaluationService.evaluate_student(
            self.student, event="QUIZ_SUBMITTED", context={'percentage': Decimal('100.00')}
        )
        self.assertTrue(any(a.code == 'PERFECT_SCORE' for a in awarded_quiz))

