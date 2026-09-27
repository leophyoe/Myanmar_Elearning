from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, RoleChoices
from apps.courses.models import (
    Course, CourseModule, Lesson, LessonType, CourseStatus,
    CourseType, LearningObjective
)
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress, ModuleProgress
from apps.progress.services import ProgressCalculationService
from apps.assessments.models import (
    Quiz, Question, QuestionOption, QuestionType, QuizAttempt,
    Assignment, AssignmentSubmission, AssignmentFeedback, SubmissionStatus,
    Exam, ExamQuestion, ExamOption, ExamType, ExamAttempt,
    FinalProject, ProjectSubmission, ProjectStatus, AssessmentWeight
)
from apps.assessments.services import QuizGradingService, ExamTimerService, GradeCalculationService
from apps.certificates.models import Certificate, CertificateStatus, CertificateTemplate
from apps.certificates.services import CertificateGenerationService, CertificateEligibilityService


class DiplomaLearningSystemTestCase(TestCase):
    """
    Comprehensive tests for the Diploma in Cyber Security and Generic Multi-Course LMS.
    Verifies:
    1. Generic course creation, types, passing percentages, and bilingual getters.
    2. Learning objectives with bilingual support.
    3. Lesson progress tracking and strict student isolation.
    4. Quiz taking, server-side scoring, attempt enforcement, and no answer leakage.
    5. Assignment submission and instructor grading workflow.
    6. Module exam time tracking and auto-scoring.
    7. Final capstone project submission, instructor grading, and presentation/viva scores.
    8. Module progress calculation weighting (Lessons 30%, Quizzes 15%, Assignments 15%, Practical 25%, Exam 15%).
    9. Course grade calculation and configurable passing percentage.
    10. Certificate eligibility and atomic issuance.
    11. Public certificate verification and PII data privacy protection.
    """

    def setUp(self):
        self.client = Client()

        # Users
        self.instructor = User.objects.create_user(
            email="prof.cyber@futuretech.edu",
            username="prof_cyber",
            password="SecurePassword123!",
            role=RoleChoices.INSTRUCTOR,
            is_staff=True,
            first_name="Alan",
            last_name="Turing"
        )
        self.student_a = User.objects.create_user(
            email="alice.student@futuretech.edu",
            username="alice_cyber",
            password="SecurePassword123!",
            role=RoleChoices.STUDENT,
            first_name="Alice",
            last_name="Lovell",
            preferred_language="en"
        )
        self.student_b = User.objects.create_user(
            email="bob.student@futuretech.edu",
            username="bob_cyber",
            password="SecurePassword123!",
            role=RoleChoices.STUDENT,
            first_name="Bob",
            last_name="Shannon",
            preferred_language="my"
        )

        # Generic Course
        self.course = Course.objects.create(
            title="Certificate in Cyber Security",
            title_en="Certificate in Cyber Security",
            title_my="ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း",
            slug="certificate-cyber-security",
            course_type=CourseType.CERTIFICATE,
            short_description="Comprehensive 10-month enterprise cybersecurity certificate program.",
            description="Complete professional cybersecurity curriculum.",
            description_en="Complete professional cybersecurity curriculum.",
            description_my="ပြည့်စုံသော ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း သင်ရိုးညွှန်းတမ်း။",
            passing_percentage=Decimal('70.00'),
            certificate_enabled=True,
            level="INTERMEDIATE",
            status=CourseStatus.PUBLISHED,
            created_by=self.instructor
        )

        # Module 1
        self.module1 = CourseModule.objects.create(
            course=self.course,
            title="Module 1: Network & Linux Security",
            title_en="Module 1: Network & Linux Security",
            title_my="မော်ဂျူး ၁ - ကွန်ရက်နှင့် လင်းနပ်စ် လုံခြုံရေး",
            slug="m1-network-linux-security",
            order=1,
            is_published=True
        )

        # Learning Objectives
        self.obj1 = LearningObjective.objects.create(
            module=self.module1,
            title_en="Foundational networking & Linux security",
            title_my="ကွန်ရက်နှင့် လင်းနပ်စ် လုံခြုံရေး အခြေခံ",
            description_en="Understand foundational networking and Linux security protocols.",
            description_my="ကွန်ရက်နှင့် လင်းနပ်စ် လုံခြုံရေး အခြေခံ သဘောတရားများကို နားလည်စေရန်။",
            order=1
        )
        self.obj2 = LearningObjective.objects.create(
            module=self.module1,
            title_en="Web Security Analysis",
            description_en="Perform web application penetration testing and vulnerability analysis.",
            description_my="",  # Empty Myanmar to test fallback
            order=2
        )

        # Lessons for Module 1
        self.lesson1 = Lesson.objects.create(
            module=self.module1,
            title="Linux Security Fundamentals",
            title_en="Linux Security Fundamentals",
            title_my="လင်းနပ်စ် လုံခြုံရေး အခြေခံများ",
            slug="linux-security-fundamentals",
            lesson_type=LessonType.THEORY,
            content="Core Linux security and access controls.",
            content_en="Core Linux security and access controls.",
            content_my="လင်းနပ်စ် လုံခြုံရေးနှင့် ခွင့်ပြုချက် စီမံခန့်ခွဲမှု အခြေခံများ။",
            order=1,
            is_published=True,
            is_required=True
        )

        self.lesson2 = Lesson.objects.create(
            module=self.module1,
            title="Network Packet Analysis Lab",
            title_en="Network Packet Analysis Lab",
            title_my="ကွန်ရက် ပက်ကက် စစ်ဆေးခြင်း လက်တွေ့လေ့ကျင့်ခန်း",
            slug="network-packet-analysis-lab",
            lesson_type=LessonType.PRACTICAL,
            content="Wireshark packet capture analysis guide.",
            order=2,
            is_published=True,
            is_required=True
        )

        # Enrollments
        self.enrollment_a = Enrollment.objects.create(
            student=self.student_a,
            course=self.course,
            status=EnrollmentStatus.ACTIVE
        )
        self.enrollment_b = Enrollment.objects.create(
            student=self.student_b,
            course=self.course,
            status=EnrollmentStatus.ACTIVE
        )

    # ==============================================================================
    # 1. Course Creation & Bilingual Model Tests
    # ==============================================================================
    def test_generic_course_types_and_bilingual_fallbacks(self):
        """Verify Course supports generic course types, passing score, and bilingual fallbacks."""
        # Generic types test
        python_course = Course.objects.create(
            title="Python for Security Automation",
            course_type=CourseType.SHORT_COURSE,
            passing_percentage=Decimal('60.00'),
            created_by=self.instructor
        )
        self.assertEqual(python_course.course_type, CourseType.SHORT_COURSE)
        self.assertEqual(python_course.passing_percentage, Decimal('60.00'))

        # Bilingual title getters
        self.assertEqual(self.course.get_title('en'), "Certificate in Cyber Security")
        self.assertEqual(self.course.get_title('my'), "ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း")

        # Bilingual description fallback when translation exists
        self.assertEqual(self.course.get_description('my'), "ပြည့်စုံသော ဆိုက်ဘာလုံခြုံရေး လက်မှတ်သင်တန်း သင်ရိုးညွှန်းတမ်း။")

        # Fallback when translation is missing
        self.assertEqual(self.obj2.get_description('my'), "Perform web application penetration testing and vulnerability analysis.")

    def test_set_language_view(self):
        """Verify language switcher endpoint updates session and user preferred_language."""
        self.client.force_login(self.student_a)
        url = reverse('set-language')
        response = self.client.post(url, {'language': 'my', 'next': '/'}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.student_a.refresh_from_db()
        self.assertEqual(self.student_a.preferred_language, 'my')

    # ==============================================================================
    # 2. Student Progress Tracking & Isolation
    # ==============================================================================
    def test_lesson_progress_tracking_and_isolation(self):
        """Verify lesson progress tracking is isolated per student and properly updates enrollment."""
        # Alice completes lesson 1
        alice_lp, _ = LessonProgress.objects.get_or_create(student=self.student_a, lesson=self.lesson1)
        alice_lp.mark_completed()

        self.assertTrue(alice_lp.completed)
        self.assertIsNotNone(alice_lp.completed_at)

        # Verify Bob's progress is 0% and untouched
        bob_lp = LessonProgress.objects.filter(student=self.student_b, lesson=self.lesson1).first()
        self.assertTrue(bob_lp is None or not bob_lp.completed)

        # Recalculate enrollment progress
        enrollment_a_prog = ProgressCalculationService.update_course_progress(self.student_a, self.course)
        self.assertEqual(enrollment_a_prog, Decimal('50.00'))  # 1 of 2 lessons completed

        enrollment_b_prog = ProgressCalculationService.update_course_progress(self.student_b, self.course)
        self.assertEqual(enrollment_b_prog, Decimal('0.00'))

        # Idempotency check: mark_completed called again preserves original timestamp
        orig_completed_at = alice_lp.completed_at
        alice_lp.mark_completed()
        self.assertEqual(alice_lp.completed_at, orig_completed_at)

    # ==============================================================================
    # 3. Quiz Taking & Server-Side Scoring
    # ==============================================================================
    def test_quiz_server_side_scoring_and_integrity(self):
        """Verify quiz evaluation happens server-side, counts attempts, and enforces score threshold."""
        quiz = Quiz.objects.create(
            course=self.course,
            module=self.module1,
            title="Module 1 Checkpoint Quiz",
            passing_score=Decimal('70.00'),
            max_attempts=2,
            is_published=True
        )

        q1 = Question.objects.create(
            quiz=quiz,
            question_text="Which tool is used for network packet sniffing?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            points=10,
            order=1
        )
        opt_correct = QuestionOption.objects.create(question=q1, option_text="Wireshark", is_correct=True, order=1)
        opt_wrong = QuestionOption.objects.create(question=q1, option_text="Vim", is_correct=False, order=2)

        attempt = QuizAttempt.objects.create(quiz=quiz, student=self.student_a, attempt_number=1)

        # Submit correct answer
        raw_answers = {str(q1.id): str(opt_correct.id)}
        completed_attempt = QuizGradingService.grade_attempt(attempt, raw_answers)

        self.assertTrue(completed_attempt.is_completed)
        self.assertEqual(completed_attempt.percentage, Decimal('100.00'))
        self.assertTrue(completed_attempt.passed)

        # Attempt limit verification
        can_attempt, remaining = QuizGradingService.can_attempt(quiz, self.student_a)
        self.assertTrue(can_attempt)
        self.assertEqual(remaining, 1)

        # Submit second attempt
        attempt2 = QuizAttempt.objects.create(quiz=quiz, student=self.student_a, attempt_number=2)
        QuizGradingService.grade_attempt(attempt2, {str(q1.id): str(opt_wrong.id)})

        can_attempt_3, remaining_3 = QuizGradingService.can_attempt(quiz, self.student_a)
        self.assertFalse(can_attempt_3)
        self.assertEqual(remaining_3, 0)

    # ==============================================================================
    # 4. Assignment Submission & Instructor Grading
    # ==============================================================================
    def test_assignment_submission_and_instructor_grading(self):
        """Verify student submission, status transitions, and instructor evaluation."""
        assignment = Assignment.objects.create(
            course=self.course,
            module=self.module1,
            title="Firewall Configuration Task",
            max_score=Decimal('100.00'),
            passing_score=Decimal('70.00'),
            status='PUBLISHED'
        )

        # Alice submits assignment
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student_a,
            submission_text="Configured iptables and ufw rules to block unauthorized inbound connections.",
            status=SubmissionStatus.SUBMITTED
        )
        self.assertEqual(submission.status, SubmissionStatus.SUBMITTED)

        # Instructor grades assignment
        feedback = AssignmentFeedback.objects.create(
            submission=submission,
            instructor=self.instructor,
            score=Decimal('88.50'),
            feedback="Excellent firewall configuration and documentation."
        )
        submission.status = SubmissionStatus.GRADED
        submission.save()

        submission.refresh_from_db()
        self.assertEqual(submission.status, SubmissionStatus.GRADED)
        self.assertEqual(submission.latest_feedback.score, Decimal('88.50'))

    # ==============================================================================
    # 5. Module Exam & Time Limit
    # ==============================================================================
    def test_module_exam_timer_and_grading(self):
        """Verify module examination auto-grading and time limit enforcement."""
        exam = Exam.objects.create(
            course=self.course,
            module=self.module1,
            title="Module 1 Formal Examination",
            exam_type=ExamType.MODULE_EXAM,
            duration_minutes=60,
            passing_score=Decimal('70.00'),
            max_attempts=1,
            is_published=True
        )

        q = ExamQuestion.objects.create(
            exam=exam,
            question_text="What is the default port for SSH?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            points=20,
            order=1
        )
        opt_correct = ExamOption.objects.create(question=q, option_text="22", is_correct=True, order=1)

        attempt = ExamTimerService.start_exam_attempt(self.student_a, exam)

        # Check timer
        self.assertFalse(attempt.is_expired)
        self.assertGreater(attempt.expires_at, timezone.now())

        # Submit answers
        raw_answers = {str(q.id): str(opt_correct.id)}
        completed_attempt = ExamTimerService.submit_exam_attempt(attempt, raw_answers)

        self.assertTrue(completed_attempt.is_completed)
        self.assertEqual(completed_attempt.percentage, Decimal('100.00'))
        self.assertTrue(completed_attempt.passed)

    # ==============================================================================
    # 6. Final Capstone Project & Presentation Viva Grading
    # ==============================================================================
    def test_final_capstone_project_workflow(self):
        """Verify capstone project submission, presentation viva evaluation, and weighted score."""
        project = FinalProject.objects.create(
            course=self.course,
            title="Enterprise Threat Modeling & Defense Capstone",
            requirements="Detailed threat model report and mitigation plan.",
            max_score=Decimal('100.00'),
            passing_score=Decimal('70.00')
        )

        # Student submits project
        proj_sub = ProjectSubmission.objects.create(
            project=project,
            student=self.student_a,
            title="Alice Capstone Submission",
            description="Complete threat model report using STRIDE methodology.",
            repository_url="https://github.com/alice/capstone-defense",
            status=ProjectStatus.SUBMITTED
        )

        # Instructor evaluates report (85) and viva/presentation (95)
        proj_sub.score = Decimal('88.00')
        proj_sub.presentation_score = Decimal('95.00')
        proj_sub.status = ProjectStatus.GRADED
        proj_sub.graded_by = self.instructor
        proj_sub.graded_at = timezone.now()
        proj_sub.save()

        self.assertEqual(proj_sub.status, ProjectStatus.GRADED)
        self.assertTrue(proj_sub.passed)

    # ==============================================================================
    # 7. Module Progress Calculation Weighting
    # ==============================================================================
    def test_module_progress_weighted_formula(self):
        """
        Verify module progress follows the 30/15/15/25/15 formula:
        Lessons (30%), Quizzes (15%), Assignments (15%), Practical (25%), Module Exam (15%).
        """
        # Create full suite for module 1:
        quiz = Quiz.objects.create(course=self.course, module=self.module1, title="M1 Quiz", passing_score=Decimal('70.00'), is_published=True)
        assignment = Assignment.objects.create(course=self.course, module=self.module1, title="M1 Task", max_score=Decimal('100.00'), status='PUBLISHED')
        exam = Exam.objects.create(course=self.course, module=self.module1, title="M1 Exam", duration_minutes=45, passing_score=Decimal('70.00'), is_published=True)

        # Student completes only Lesson 1 (theory lesson = 50% of lessons)
        LessonProgress.objects.create(student=self.student_a, lesson=self.lesson1, completed=True)

        mod_prog = ProgressCalculationService.update_module_progress(self.student_a, self.module1)
        # Lessons completion = 50% * 30% weight = 15.00%
        # Everything else 0%
        self.assertEqual(mod_prog.overall_progress, Decimal('15.00'))

        # Now complete practical lesson (practical lesson = 100% of practical activities = 25% weight, and brings lessons to 100% = 30% weight)
        LessonProgress.objects.create(student=self.student_a, lesson=self.lesson2, completed=True)
        mod_prog = ProgressCalculationService.update_module_progress(self.student_a, self.module1)
        # Lessons (30%) + Practical (25%) = 55%
        self.assertEqual(mod_prog.overall_progress, Decimal('55.00'))

        # Complete quiz (+15%)
        QuizAttempt.objects.create(quiz=quiz, student=self.student_a, is_completed=True, passed=True, score=Decimal('90.00'))
        # Submit assignment (+15%)
        sub = AssignmentSubmission.objects.create(assignment=assignment, student=self.student_a, status=SubmissionStatus.GRADED)
        AssignmentFeedback.objects.create(submission=sub, instructor=self.instructor, score=Decimal('85.00'), feedback="Good")
        # Pass exam (+15%)
        ExamAttempt.objects.create(exam=exam, student=self.student_a, is_completed=True, passed=True, score=Decimal('80.00'))

        mod_prog = ProgressCalculationService.update_module_progress(self.student_a, self.module1)
        # 30 + 25 + 15 + 15 + 15 = 100%
        self.assertEqual(mod_prog.overall_progress, Decimal('100.00'))
        self.assertTrue(mod_prog.is_completed)

    # ==============================================================================
    # 8. Gradebook Calculation & Configurable Passing Threshold
    # ==============================================================================
    def test_gradebook_weighted_calculation_and_letter_grade(self):
        """Verify course grade calculation aggregates all categories and assigns correct letter grade."""
        # Quiz: 90%
        quiz = Quiz.objects.create(course=self.course, module=self.module1, title="Q1", passing_score=Decimal('70.00'), is_published=True)
        QuizAttempt.objects.create(quiz=quiz, student=self.student_a, is_completed=True, percentage=Decimal('90.00'))

        # Assignment: 80%
        assignment = Assignment.objects.create(course=self.course, module=self.module1, title="A1", max_score=Decimal('100.00'), status='PUBLISHED')
        sub = AssignmentSubmission.objects.create(assignment=assignment, student=self.student_a, status=SubmissionStatus.GRADED)
        AssignmentFeedback.objects.create(submission=sub, instructor=self.instructor, score=Decimal('80.00'), feedback="Well done")

        # Exam: 85%
        exam = Exam.objects.create(course=self.course, module=self.module1, title="E1", exam_type=ExamType.MODULE_EXAM, duration_minutes=60, passing_score=Decimal('70.00'), is_published=True)
        ExamAttempt.objects.create(exam=exam, student=self.student_a, is_completed=True, percentage=Decimal('85.00'))

        # Final Project: 92%
        proj = FinalProject.objects.create(course=self.course, title="Capstone", max_score=Decimal('100.00'), passing_score=Decimal('70.00'))
        ProjectSubmission.objects.create(project=proj, student=self.student_a, title="Capstone", status=ProjectStatus.GRADED, score=Decimal('92.00'), presentation_score=Decimal('92.00'))

        # Set custom assessment weights (Quizzes 20%, Assignments 25%, Module Exams 35%, Final Project 20%)
        AssessmentWeight.objects.update_or_create(
            course=self.course,
            defaults={
                'quizzes_weight': Decimal('20.00'),
                'assignments_weight': Decimal('25.00'),
                'module_exams_weight': Decimal('35.00'),
                'final_project_weight': Decimal('20.00'),
                'labs_weight': Decimal('0.00'),
                'practical_exam_weight': Decimal('0.00'),
            }
        )

        summary = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        # (90 * 0.20) + (80 * 0.25) + (85 * 0.35) + (92 * 0.20) = 18 + 20 + 29.75 + 18.4 = 86.15%
        self.assertAlmostEqual(float(summary['final_grade']), 86.15, places=1)
        self.assertTrue(summary['passed'])
        self.assertIn(summary['final_letter_grade'], ['A', 'A+', 'B+', 'B'])

    # ==============================================================================
    # 9. Certificate Eligibility & Atomic Issuance
    # ==============================================================================
    def test_certificate_eligibility_and_atomic_issuance(self):
        """Verify certificate eligibility checks all components and issues certificate idempotently."""
        # Initial state: student has completed nothing -> NOT eligible
        eval_result = CertificateEligibilityService.evaluate_eligibility(self.student_a, self.course)
        self.assertFalse(eval_result['eligible'])

        # Complete lessons
        LessonProgress.objects.create(student=self.student_a, lesson=self.lesson1, completed=True)
        LessonProgress.objects.create(student=self.student_a, lesson=self.lesson2, completed=True)

        # Quizzes
        quiz = Quiz.objects.create(course=self.course, module=self.module1, title="Q1", passing_score=Decimal('70.00'), is_published=True, is_required=True)
        QuizAttempt.objects.create(quiz=quiz, student=self.student_a, is_completed=True, passed=True, percentage=Decimal('85.00'), score=Decimal('85.00'))

        # Assignments
        assignment = Assignment.objects.create(course=self.course, module=self.module1, title="A1", max_score=Decimal('100.00'), status='PUBLISHED', is_required=True)
        sub = AssignmentSubmission.objects.create(assignment=assignment, student=self.student_a, status=SubmissionStatus.GRADED)
        AssignmentFeedback.objects.create(submission=sub, instructor=self.instructor, score=Decimal('80.00'), feedback="Passed")

        # Exam
        exam = Exam.objects.create(course=self.course, module=self.module1, title="E1", exam_type=ExamType.MODULE_EXAM, duration_minutes=60, passing_score=Decimal('70.00'), is_published=True, is_required=True)
        ExamAttempt.objects.create(exam=exam, student=self.student_a, is_completed=True, passed=True, percentage=Decimal('85.00'), score=Decimal('85.00'))

        # Final Capstone Project
        proj = FinalProject.objects.create(course=self.course, title="Capstone", max_score=Decimal('100.00'), passing_score=Decimal('70.00'), is_required=True)
        ProjectSubmission.objects.create(project=proj, student=self.student_a, title="Capstone", status=ProjectStatus.GRADED, score=Decimal('90.00'), presentation_score=Decimal('90.00'))

        # Check eligibility now
        eval_result = CertificateEligibilityService.evaluate_eligibility(self.student_a, self.course)
        self.assertTrue(eval_result['eligible'], f"Eligibility failed unexpectedly: {eval_result}")

        # Issue Certificate
        cert = CertificateGenerationService.issue_certificate(self.student_a, self.course)
        self.assertIsNotNone(cert)
        self.assertEqual(cert.status, CertificateStatus.ISSUED)
        self.assertTrue(cert.certificate_number.startswith("FTCSA-"))
        self.assertIsNotNone(cert.verification_token)
        self.assertGreaterEqual(cert.grade_percentage, Decimal('70.00'))

        # Idempotency check: Re-issuing returns existing certificate
        cert2 = CertificateGenerationService.issue_certificate(self.student_a, self.course)
        self.assertEqual(cert.id, cert2.id)

    # ==============================================================================
    # 10. Public Certificate Verification & PII Protection
    # ==============================================================================
    def test_public_certificate_verification_privacy(self):
        """Verify public verification endpoint displays credentials without leaking PII."""
        cert = Certificate.objects.create(
            certificate_number="FTCSA-2026-TEST999",
            student=self.student_a,
            course=self.course,
            status=CertificateStatus.ISSUED,
            final_grade='A',
            grade_percentage=Decimal('94.50')
        )

        url = reverse('public-verify-root', kwargs={'certificate_number': cert.certificate_number})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        # Public verification details should appear
        self.assertIn("Alice Lovell", content)
        self.assertIn("Certificate in Cyber Security", content)
        self.assertIn(cert.certificate_number, content)

        # STRICT PRIVACY: Student email, password hash, and internal ID must NOT be rendered
        self.assertNotIn(self.student_a.email, content)
        self.assertNotIn(self.student_a.password, content)
        self.assertNotIn(str(self.student_a.id), content)

    # ==============================================================================
    # 11. Course and Module REST API Endpoints
    # ==============================================================================
    def test_course_and_module_api_endpoints(self):
        """Verify GET /api/courses/{id}/modules/ and GET /api/modules/{id}/lessons/"""
        self.client.force_login(self.student_a)

        # Lookup by slug
        url_slug = f"/api/courses/{self.course.slug}/modules/"
        resp_slug = self.client.get(url_slug)
        self.assertEqual(resp_slug.status_code, 200)
        data_slug = resp_slug.json()
        self.assertIsInstance(data_slug, list)
        self.assertGreaterEqual(len(data_slug), 1)
        self.assertEqual(data_slug[0]['slug'], self.module1.slug)

        # Lookup by UUID
        url_uuid = f"/api/courses/{self.course.id}/modules/"
        resp_uuid = self.client.get(url_uuid)
        self.assertEqual(resp_uuid.status_code, 200)
        data_uuid = resp_uuid.json()
        self.assertEqual(len(data_uuid), len(data_slug))

        # Lookup module lessons
        url_mod = f"/api/modules/{self.module1.id}/lessons/"
        resp_mod = self.client.get(url_mod)
        self.assertEqual(resp_mod.status_code, 200)
        lessons_data = resp_mod.json()
        self.assertIsInstance(lessons_data, list)
        self.assertGreaterEqual(len(lessons_data), 2)

    # ==============================================================================
    # 12. Lesson Start & Complete API Endpoints
    # ==============================================================================
    def test_lesson_start_and_complete_api_endpoints(self):
        """Verify POST /api/lessons/{id}/start/ and /complete/"""
        self.client.force_login(self.student_a)

        # Start lesson
        url_start = f"/api/lessons/{self.lesson1.id}/start/"
        resp_start = self.client.post(url_start)
        self.assertEqual(resp_start.status_code, 200)
        data_start = resp_start.json()
        self.assertEqual(data_start['status'], 'started')

        progress = LessonProgress.objects.get(student=self.student_a, lesson=self.lesson1)
        self.assertIsNotNone(progress.started_at)
        self.assertFalse(progress.completed)

        # Complete lesson
        url_complete = f"/api/lessons/{self.lesson1.id}/complete/"
        resp_complete = self.client.post(url_complete)
        self.assertEqual(resp_complete.status_code, 200)
        data_complete = resp_complete.json()
        self.assertEqual(data_complete['status'], 'completed')

        progress.refresh_from_db()
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)

    # ==============================================================================
    # 13. Quiz and Exam API Submission Flow
    # ==============================================================================
    def test_quiz_and_exam_api_submission_flow(self):
        """Verify POST /api/quizzes/{id}/start/ and /submit/, and /api/exams/{id}/start/ and /submit/"""
        self.client.force_login(self.student_a)

        # Setup Quiz
        quiz = Quiz.objects.create(
            course=self.course,
            module=self.module1,
            title="API Network Quiz",
            passing_score=Decimal('70.00'),
            is_published=True
        )
        q1 = Question.objects.create(quiz=quiz, question_text="Port 22?", points=10)
        opt_correct = QuestionOption.objects.create(question=q1, option_text="SSH", is_correct=True)
        opt_wrong = QuestionOption.objects.create(question=q1, option_text="HTTP", is_correct=False)

        # Start Quiz
        resp_qstart = self.client.post(f"/api/quizzes/{quiz.id}/start/")
        self.assertEqual(resp_qstart.status_code, 201)
        qstart_data = resp_qstart.json()
        attempt_id = qstart_data['id']

        # Submit Quiz with correct answer
        resp_qsub = self.client.post(
            f"/api/quizzes/{quiz.id}/submit/",
            data={'attempt_id': attempt_id, 'answers': {str(q1.id): str(opt_correct.id)}},
            content_type="application/json"
        )
        self.assertEqual(resp_qsub.status_code, 200)
        qsub_data = resp_qsub.json()
        self.assertTrue(qsub_data['passed'])
        self.assertEqual(float(qsub_data['percentage']), 100.0)

        # Setup Exam
        exam = Exam.objects.create(
            course=self.course,
            module=self.module1,
            title="API Module Exam",
            exam_type=ExamType.MODULE_EXAM,
            duration_minutes=30,
            passing_score=Decimal('70.00'),
            is_published=True
        )
        eq1 = ExamQuestion.objects.create(exam=exam, question_text="What is IDS?", points=10)
        eopt_correct = ExamOption.objects.create(question=eq1, option_text="Intrusion Detection System", is_correct=True)

        # Start Exam
        resp_estart = self.client.post(f"/api/exams/{exam.id}/start/")
        self.assertEqual(resp_estart.status_code, 201)
        estart_data = resp_estart.json()
        eattempt_id = estart_data['id']

        # Submit Exam
        resp_esub = self.client.post(
            f"/api/exams/{exam.id}/submit/",
            data={'attempt_id': eattempt_id, 'answers': {str(eq1.id): str(eopt_correct.id)}},
            content_type="application/json"
        )
        self.assertEqual(resp_esub.status_code, 200)
        esub_data = resp_esub.json()
        self.assertTrue(esub_data['passed'])
        self.assertEqual(float(esub_data['percentage']), 100.0)

    # ==============================================================================
    # 14. Assignment Submit API Endpoint
    # ==============================================================================
    def test_assignment_submit_api(self):
        """Verify POST /api/assignments/{id}/submit/"""
        self.client.force_login(self.student_a)
        assignment = Assignment.objects.create(
            course=self.course,
            module=self.module1,
            title="API Linux Lab Report",
            max_score=Decimal('100.00'),
            status='PUBLISHED'
        )

        resp = self.client.post(
            f"/api/assignments/{assignment.id}/submit/",
            data={'submission_text': 'Completed bash hardening exercises.'}
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['status'], 'SUBMITTED')
        self.assertEqual(data['student_name'], self.student_a.get_full_name())

    # ==============================================================================
    # 15. Student Learning Portal APIs
    # ==============================================================================
    def test_student_portal_apis(self):
        """Verify student courses, overall progress, course breakdown, grades, and certificate eligibility APIs."""
        self.client.force_login(self.student_a)

        # Existing enrollment from setUp
        self.enrollment_a.status = EnrollmentStatus.ACTIVE
        self.enrollment_a.progress_percentage = Decimal('25.00')
        self.enrollment_a.save()

        # 1. Student Courses
        resp_courses = self.client.get("/api/student/courses/")
        self.assertEqual(resp_courses.status_code, 200)
        data_courses = resp_courses.json()
        self.assertEqual(data_courses['count'], 1)
        self.assertEqual(data_courses['results'][0]['course_title'], self.course.title)

        # 2. Student Overall Progress
        resp_prog = self.client.get("/api/student/progress/")
        self.assertEqual(resp_prog.status_code, 200)
        data_prog = resp_prog.json()
        self.assertEqual(data_prog['total_enrolled_courses'], 1)

        # 3. Student Course Progress Breakdown
        resp_cp = self.client.get(f"/api/student/courses/{self.course.slug}/progress/")
        self.assertEqual(resp_cp.status_code, 200)
        data_cp = resp_cp.json()
        self.assertEqual(data_cp['course_slug'], self.course.slug)
        self.assertIn('modules', data_cp)

        # 4. Student Module Progress
        resp_mp = self.client.get(f"/api/student/modules/{self.module1.id}/progress/")
        self.assertEqual(resp_mp.status_code, 200)
        data_mp = resp_mp.json()
        self.assertEqual(data_mp['module_id'], str(self.module1.id))
        self.assertIn('lesson_progress', data_mp)
        self.assertIn('overall_progress', data_mp)

        # 5. Student Grades API
        resp_grades = self.client.get(f"/api/student/grades/?course_slug={self.course.slug}")
        self.assertEqual(resp_grades.status_code, 200)
        data_grades = resp_grades.json()
        self.assertIn('grades', data_grades)
        self.assertEqual(len(data_grades['grades']), 1)
        self.assertEqual(data_grades['grades'][0]['course_id'], str(self.course.id))

        # 6. Student Certificate Eligibility API
        resp_elig = self.client.get(f"/api/student/certificate-eligibility/?course_slug={self.course.slug}")
        self.assertEqual(resp_elig.status_code, 200)
        data_elig = resp_elig.json()
        self.assertIn('eligibility', data_elig)
        self.assertEqual(len(data_elig['eligibility']), 1)
        self.assertFalse(data_elig['eligibility'][0]['eligible'])

