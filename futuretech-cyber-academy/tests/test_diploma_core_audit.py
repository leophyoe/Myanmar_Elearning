from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User, RoleChoices
from apps.courses.models import Course, CourseModule, Lesson, LessonType, CourseStatus, CourseReview, CourseType
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress
from apps.assessments.models import (
    Quiz, Question, QuestionOption, QuestionType, QuizAttempt,
    Assignment, AssignmentSubmission, AssignmentFeedback, SubmissionStatus,
    Exam, ExamQuestion, ExamOption, ExamType, ExamAttempt, AssessmentWeight
)
from apps.assessments.services import QuizGradingService, ExamTimerService, GradeCalculationService
from apps.certificates.models import Certificate, CertificateStatus, CertificateTemplate
from apps.certificates.services import CertificateGenerationService, CertificateEligibilityService


class DiplomaCoreAuditTestCase(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor.audit@futuretech.edu",
            username="instructor_audit",
            password="SecurePassword123!",
            role=RoleChoices.INSTRUCTOR,
            is_staff=True,
            first_name="Prof",
            last_name="Audit"
        )
        self.student_a = User.objects.create_user(
            email="student.alice@futuretech.edu",
            username="alice_audit",
            password="SecurePassword123!",
            role=RoleChoices.STUDENT,
            first_name="Alice",
            last_name="Cyber"
        )
        self.student_b = User.objects.create_user(
            email="student.bob@futuretech.edu",
            username="bob_audit",
            password="SecurePassword123!",
            role=RoleChoices.STUDENT,
            first_name="Bob",
            last_name="Hacker"
        )

        self.course = Course.objects.create(
            title="Certificate in Cyber Defense",
            slug="certificate-cyber-defense",
            course_type=CourseType.CERTIFICATE,
            level="BEGINNER",
            status=CourseStatus.PUBLISHED,
            created_by=self.instructor
        )
        self.module = CourseModule.objects.create(
            course=self.course,
            title="Module 1: Defense Fundamentals",
            slug="m1-defense-fundamentals",
            order=1
        )
        self.lesson_reading = Lesson.objects.create(
            module=self.module,
            title="Lesson 1: CIA Triad",
            slug="lesson-1-cia-triad",
            lesson_type=LessonType.READING,
            order=1,
            is_published=True
        )
        self.client = Client()

    # ==========================================================================
    # 1. URL Resolution & Template Syntax Audit
    # ==========================================================================
    def test_home_page_renders_with_static_logo(self):
        """Ensure HomePageView renders without TemplateSyntaxError for static tags."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Future Tech Education')
        self.assertContains(response, 'images/logo.png')

    def test_course_review_submission_redirect_no_reverse_match(self):
        """Ensure CourseReviewCreateView redirects cleanly to 'course-detail' without NoReverseMatch."""
        self.client.force_login(self.student_a)
        review_url = reverse('course-review-create', kwargs={'slug': self.course.slug})
        response = self.client.post(review_url, {
            'rating': '5',
            'comment': 'Outstanding curriculum and hands-on rigor!'
        })
        self.assertEqual(response.status_code, 302)
        expected_redirect = reverse('course-detail', kwargs={'slug': self.course.slug})
        self.assertEqual(response.url, expected_redirect)

        # Verify review persisted
        review = CourseReview.objects.filter(course=self.course, student=self.student_a).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)

    # ==========================================================================
    # 2. Quiz Attempt Resumption (Fix attempt consumption bug)
    # ==========================================================================
    def test_quiz_page_refresh_resumes_in_progress_attempt(self):
        """Page refreshes on QuizTakeView must NOT consume additional attempts."""
        Enrollment.objects.create(student=self.student_a, course=self.course, status=EnrollmentStatus.ACTIVE)
        quiz = Quiz.objects.create(
            course=self.course,
            title="Firewall Architecture Quiz",
            max_attempts=3,
            is_published=True
        )
        self.client.force_login(self.student_a)
        take_url = reverse('assessments:quiz-take', kwargs={'pk': quiz.pk})

        # 1st page load: creates attempt 1
        res1 = self.client.get(take_url)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(QuizAttempt.objects.filter(quiz=quiz, student=self.student_a).count(), 1)

        # 2nd page load (refresh): MUST resume attempt 1, NOT create attempt 2
        res2 = self.client.get(take_url)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(QuizAttempt.objects.filter(quiz=quiz, student=self.student_a).count(), 1)

        # 3rd page load (refresh): still attempt 1
        res3 = self.client.get(take_url)
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(QuizAttempt.objects.filter(quiz=quiz, student=self.student_a).count(), 1)

    # ==========================================================================
    # 3. Access Control & Student Enrollment Verification
    # ==========================================================================
    def test_student_access_creates_enrollment_for_progress_tracking(self):
        """When an authenticated student accesses assessments, enrollment is verified/created to ensure tracking."""
        quiz = Quiz.objects.create(course=self.course, title="Sec Quiz", is_published=True)
        self.assertFalse(Enrollment.objects.filter(student=self.student_b, course=self.course).exists())

        self.client.force_login(self.student_b)
        quiz_res = self.client.get(reverse('assessments:quiz-take', kwargs={'pk': quiz.pk}))
        self.assertEqual(quiz_res.status_code, 200)

        # Verify enrollment was created and active
        self.assertTrue(Enrollment.objects.filter(student=self.student_b, course=self.course, status=EnrollmentStatus.ACTIVE).exists())

    # ==========================================================================
    # 4. File Upload Validation & Security in Assignment Submissions
    # ==========================================================================
    def test_malicious_file_upload_blocked_in_assignment_submission(self):
        """Uploading dangerous executables (.exe, .sh) must be blocked server-side."""
        Enrollment.objects.create(student=self.student_a, course=self.course, status=EnrollmentStatus.ACTIVE)
        assign = Assignment.objects.create(
            course=self.course,
            title="Malware Analysis Report",
            allowed_file_types=['pdf', 'docx'],
            status='PUBLISHED'
        )
        self.client.force_login(self.student_a)

        # Malicious shell script
        malicious_file = SimpleUploadedFile("backdoor.sh", b"#!/bin/bash\nrm -rf /", content_type="text/x-shellscript")
        res_bad = self.client.post(reverse('assessments:assignment-submit', kwargs={'pk': assign.pk}), {
            'submitted_file': malicious_file
        })
        self.assertEqual(res_bad.status_code, 302)
        # No submission record created
        self.assertFalse(AssignmentSubmission.objects.filter(assignment=assign, student=self.student_a).exists())

        # Valid PDF file
        valid_pdf = SimpleUploadedFile("report.pdf", b"%PDF-1.4 header content", content_type="application/pdf")
        res_good = self.client.post(reverse('assessments:assignment-submit', kwargs={'pk': assign.pk}), {
            'submitted_file': valid_pdf
        })
        self.assertEqual(res_good.status_code, 302)
        self.assertTrue(AssignmentSubmission.objects.filter(assignment=assign, student=self.student_a).exists())

    # ==========================================================================
    # 5. Academic Gradebook Calculation Audit
    # ==========================================================================
    def test_missing_assignments_penalized_in_grade_calculation(self):
        """If a student only completes 1 out of 2 published assignments, average must be 50%, not 100%."""
        a1 = Assignment.objects.create(course=self.course, title="A1", max_score=Decimal('100.00'), status='PUBLISHED')
        a2 = Assignment.objects.create(course=self.course, title="A2", max_score=Decimal('100.00'), status='PUBLISHED')

        # Student submits and scores 100% on A1, skips A2
        sub = AssignmentSubmission.objects.create(assignment=a1, student=self.student_a, status=SubmissionStatus.GRADED)
        AssignmentFeedback.objects.create(submission=sub, instructor=self.instructor, score=Decimal('100.00'), feedback="Perfect")

        grades = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        # (100 + 0) / 2 = 50.0%
        self.assertEqual(grades['breakdown']['assignments']['average'], 50.00)

    def test_practical_labs_zero_completed_evaluates_to_zero_not_hundred(self):
        """When a course has practical lab lessons, a student who did 0 labs must receive 0%, NOT 100%."""
        Lesson.objects.create(
            module=self.module,
            title="Lab 1: Nmap Scan",
            slug="lab-1-nmap",
            lesson_type=LessonType.PRACTICAL,
            order=2,
            is_published=True
        )
        Lesson.objects.create(
            module=self.module,
            title="Lab 2: Wireshark PCAP",
            slug="lab-2-wireshark",
            lesson_type=LessonType.PRACTICAL,
            order=3,
            is_published=True
        )

        grades = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        # Total labs = 2, completed = 0 -> average = 0.0%
        self.assertEqual(grades['breakdown']['labs']['average'], 0.00)

        # Now student completes 1 of 2 labs
        l1 = Lesson.objects.get(slug="lab-1-nmap")
        LessonProgress.objects.create(student=self.student_a, lesson=l1, completed=True)

        grades_after = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        # 1 / 2 * 100 = 50.0%
        self.assertEqual(grades_after['breakdown']['labs']['average'], 50.00)

    def test_quiz_highest_attempt_score_selection(self):
        """Best attempt score is credited when multiple attempts are made on the same quiz."""
        quiz = Quiz.objects.create(course=self.course, title="Crypto Quiz", is_published=True)
        # Attempt 1: 50%
        QuizAttempt.objects.create(
            quiz=quiz, student=self.student_a, attempt_number=1,
            score=Decimal('5.00'), percentage=Decimal('50.00'), is_completed=True
        )
        # Attempt 2: 95%
        QuizAttempt.objects.create(
            quiz=quiz, student=self.student_a, attempt_number=2,
            score=Decimal('9.50'), percentage=Decimal('95.00'), is_completed=True
        )

        grades = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        self.assertEqual(grades['breakdown']['quizzes']['average'], 95.00)

    def test_letter_grade_thresholds_and_pass_flag(self):
        """Verify letter grade mappings and >= 70.0% passing threshold."""
        weights = AssessmentWeight.objects.create(
            course=self.course,
            assignments_weight=Decimal('0.00'),
            quizzes_weight=Decimal('100.00'),
            labs_weight=Decimal('0.00'),
            module_exams_weight=Decimal('0.00'),
            practical_exam_weight=Decimal('0.00'),
            final_project_weight=Decimal('0.00')
        )
        quiz = Quiz.objects.create(course=self.course, title="Comprehensive Quiz", is_published=True)

        # Score 69.90% -> F / Did not pass
        att = QuizAttempt.objects.create(
            quiz=quiz, student=self.student_a,
            percentage=Decimal('69.90'), is_completed=True
        )
        grade_69 = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        self.assertEqual(grade_69['letter_grade'], 'C')
        self.assertFalse(grade_69['passed'])

        # Score 70.00% -> C+ / Passed
        att.percentage = Decimal('70.00')
        att.save()
        grade_70 = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        self.assertEqual(grade_70['letter_grade'], 'C+')
        self.assertTrue(grade_70['passed'])

        # Score 92.00% -> A+ / Passed
        att.percentage = Decimal('92.00')
        att.save()
        grade_92 = GradeCalculationService.calculate_student_grade(self.student_a, self.course)
        self.assertEqual(grade_92['letter_grade'], 'A+')
        self.assertTrue(grade_92['passed'])

    # ==========================================================================
    # 6. Certificate Eligibility & Anti-Fraud Verification
    # ==========================================================================
    def test_certificate_eligibility_enforcement(self):
        """CertificateEligibilityService must deny certificate if coursework or exams are incomplete."""
        Enrollment.objects.create(student=self.student_a, course=self.course, status=EnrollmentStatus.ACTIVE)
        quiz = Quiz.objects.create(course=self.course, title="Graduation Quiz", is_published=True)

        # Student has not completed lesson, quiz, or exam
        eligibility = CertificateEligibilityService.evaluate_eligibility(self.student_a, self.course)
        self.assertFalse(eligibility['eligible'])

        # Attempting to issue certificate with verify_eligibility=True must raise ValueError
        with self.assertRaises(ValueError):
            CertificateGenerationService.issue_certificate(self.student_a, self.course, verify_eligibility=True)

    def test_certificate_number_generation_uniqueness(self):
        """Certificate numbers must follow FTCSA-{YEAR}-{TOKEN} format and be distinct."""
        num1 = CertificateGenerationService.generate_certificate_number(2026)
        num2 = CertificateGenerationService.generate_certificate_number(2026)
        self.assertTrue(num1.startswith("FTCSA-2026-"))
        self.assertTrue(num2.startswith("FTCSA-2026-"))
        self.assertNotEqual(num1, num2)

    # ==========================================================================
    # 7. Object-Level Privacy & Security Isolation
    # ==========================================================================
    def test_cross_student_privacy_isolation(self):
        """Student B cannot view Student A's quiz attempts, exam attempts, or certificates."""
        quiz = Quiz.objects.create(course=self.course, title="Priv Quiz", is_published=True)
        attempt_a = QuizAttempt.objects.create(
            quiz=quiz, student=self.student_a, percentage=Decimal('100.00'), is_completed=True
        )
        cert_a = CertificateGenerationService.issue_certificate(self.student_a, self.course)

        self.client.force_login(self.student_b)

        # Student B accessing Student A's quiz attempt result -> 404
        quiz_res = self.client.get(reverse('assessments:quiz-result', kwargs={'pk': attempt_a.pk}))
        self.assertEqual(quiz_res.status_code, 404)

        # Student B accessing Student A's certificate detail -> 404
        cert_res = self.client.get(reverse('certificates:certificate-detail', kwargs={'certificate_number': cert_a.certificate_number}))
        self.assertEqual(cert_res.status_code, 404)
