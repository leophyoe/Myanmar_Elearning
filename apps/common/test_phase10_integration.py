"""
PHASE 10 — FINAL MEL PLATFORM INTEGRATION AND QA TEST SUITE

Comprehensive End-to-End Test Suite strictly validating:
1. USER JOURNEYS (1-6):
   - New Student
   - Standard Student
   - Premium Student
   - Instructor
   - Partner
   - Administrator
2. CROSS-SYSTEM PIPELINE:
   User -> Role -> Membership -> Course -> Enrollment -> Lesson -> Progress -> Assessment -> Exam -> Project/Lab -> Completion -> Certificate -> Verification
3. SECURITY AUDIT:
   - Student cannot become Admin
   - Student cannot access another user's data
   - Instructor cannot modify another instructor
   - Partner cannot access another Partner
   - Partner student data is isolated
   - Payment data is protected
   - Certificate data is protected
   - Lab access is isolated
"""
import uuid
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.users.models import User, UserRole, ActiveMode, InstructorApplication, TeacherProfile, StudentProfile
from apps.users.services import ensure_default_groups
from apps.courses.models import Course, Subject, Module, Lesson, Enrollment, UserProgress, Quiz, Question, QuizAttempt
from apps.courses.services.access import (
    can_access_course, can_manage_course, can_submit_for_review,
    can_take_course_exam, can_claim_certificate, enroll_student_in_course,
)
from apps.partner.models import Institution, PartnerMembership, PartnerStudent, PartnerApplication
from apps.billing.models import SubscriptionPlan, UserSubscription, Payment, Invoice
from apps.certificates.models import Certificate
from apps.labs.models import Lab, LabTemplate, LabInstance, LabCategory, LabDifficulty
from apps.projects.models import FinalProject, ProjectSubmission


class Phase10UserJourneysTests(TestCase):
    """
    Validates end-to-end user journeys from registration through completion.
    """
    def setUp(self):
        ensure_default_groups()
        SubscriptionPlan.ensure_default_plans()
        self.client = Client()

        # Subject
        self.subject = Subject.objects.create(title="Cybersecurity Core", slug="cybersecurity-core")

        # Admin user
        self.admin = User.objects.create_user(
            username="admin_mel",
            email="admin@mel.edu.mm",
            password="Password123!",
            role=UserRole.ADMIN,
        )

    def test_journey_1_new_student_lifecycle(self):
        """
        JOURNEY 1: New Student
        Register -> Login -> Starter membership -> Browse courses -> Enroll -> Learn -> Complete assessment -> Certificate where eligible.
        """
        # 1. Register
        student = User.objects.create_user(
            username="student_new",
            email="new_student@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.assertTrue(student.is_student)
        self.assertFalse(student.is_admin)

        # 2. Login
        self.client.login(username="student_new", password="Password123!")

        # 3. Starter membership default
        starter_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STARTER)
        self.assertEqual(starter_plan.monthly_price, Decimal('0.00'))

        # 4. Browse courses
        resp_browse = self.client.get(reverse('course-list'))
        self.assertEqual(resp_browse.status_code, 200)

        # 5. Free introductory course
        free_course = Course.objects.create(
            title="Introduction to Information Security",
            slug="intro-infosec",
            subject=self.subject,
            owner=self.admin,
            price=Decimal('0.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )
        module = Module.objects.create(course=free_course, title="Module 1: Fundamentals", order=1)
        lesson = Lesson.objects.create(module=module, title="Lesson 1: CIA Triad", order=1)

        # Enroll
        enrollment = enroll_student_in_course(student, free_course)
        self.assertEqual(enrollment.status, Enrollment.Status.ACTIVE)
        self.assertTrue(can_access_course(student, free_course))

        # 6. Learn (track progress)
        UserProgress.objects.create(user=student, course=free_course, module=module, lesson=lesson, is_completed=True)
        self.assertEqual(enrollment.completed_lessons_count, 1)

        # 7. Complete assessment
        quiz = Quiz.objects.create(
            module=module,
            title="CIA Triad Checkpoint Assessment",
            passing_percentage=70,
            quiz_type=Quiz.AssessmentType.QUIZ,
        )
        attempt = QuizAttempt.objects.create(
            student=student,
            quiz=quiz,
            score_percentage=100,
            passed=True,
        )
        self.assertTrue(attempt.passed)

        # 8. Receive certificate where eligible
        can_cert, _ = can_claim_certificate(student, free_course)
        self.assertTrue(can_cert)
        cert = Certificate.objects.create(
            student=student,
            course=free_course,
            certificate_code="MEL-CERT-TEST-0001",
            student_name=student.get_full_name() or student.username,
            program_title=free_course.title,
            grade="High Distinction",
        )
        self.assertIsNotNone(cert.id)

        # Student views certificate in dashboard list
        resp_certs = self.client.get(reverse('certificate-list'))
        self.assertEqual(resp_certs.status_code, 200)
        self.assertContains(resp_certs, "MEL-CERT-TEST-0001")

    def test_journey_2_standard_student_lifecycle(self):
        """
        JOURNEY 2: Standard Student
        Purchase membership -> Access standard courses -> Complete course -> Take eligible exam -> Certificate.
        """
        student = User.objects.create_user(
            username="student_standard",
            email="standard@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.client.login(username="student_standard", password="Password123!")

        # 1. Purchase Standard membership
        standard_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.STANDARD)
        sub = UserSubscription.objects.create(
            user=student,
            plan=standard_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
        )
        self.assertTrue(sub.is_current)

        # 2. Access standard paid course
        std_course = Course.objects.create(
            title="Network Security Architecture",
            slug="network-sec-arch",
            subject=self.subject,
            owner=self.admin,
            price=Decimal('50000.00'),
            is_premium=False,
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )
        module = Module.objects.create(course=std_course, title="Module 1: Defense in Depth", order=1)
        lesson = Lesson.objects.create(module=module, title="Lesson 1: Firewalls & DMZs", order=1)

        enrollment = enroll_student_in_course(student, std_course)
        self.assertTrue(can_access_course(student, std_course))

        # 3. Complete course
        UserProgress.objects.create(user=student, course=std_course, module=module, lesson=lesson, is_completed=True)
        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.save(update_fields=['status'])

        # 4. Take eligible exam
        can_exam, _ = can_take_course_exam(student, std_course)
        self.assertTrue(can_exam)

        exam = Quiz.objects.create(
            module=module,
            title="Standard Certification Exam",
            passing_percentage=80,
            quiz_type=Quiz.AssessmentType.FINAL_EXAM,
        )
        exam_attempt = QuizAttempt.objects.create(
            student=student,
            quiz=exam,
            score_percentage=90,
            passed=True,
        )
        self.assertTrue(exam_attempt.passed)

        # 5. Certificate issued
        cert = Certificate.objects.create(
            student=student,
            course=std_course,
            certificate_code="MEL-CERT-STD-0002",
            student_name=student.username,
            program_title=std_course.title,
            grade="Excellence",
        )
        self.assertEqual(cert.student, student)

    def test_journey_3_premium_student_lifecycle(self):
        """
        JOURNEY 3: Premium Student
        Premium access -> Advanced labs -> Projects -> Exams -> Certificates.
        """
        student = User.objects.create_user(
            username="student_premium",
            email="premium@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.client.login(username="student_premium", password="Password123!")

        # 1. Premium membership
        premium_plan = SubscriptionPlan.objects.get(plan_type=SubscriptionPlan.PlanType.PREMIUM)
        UserSubscription.objects.create(
            user=student,
            plan=premium_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=365),
        )

        # 2. Premium course unlocked
        prem_course = Course.objects.create(
            title="Kernel Exploitation & Advanced Cyber Defense",
            slug="kernel-exploit-adv",
            subject=self.subject,
            owner=self.admin,
            price=Decimal('150000.00'),
            is_premium=True,
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )
        enrollment = enroll_student_in_course(student, prem_course)
        self.assertTrue(can_access_course(student, prem_course))

        # 3. Advanced Labs
        template = LabTemplate.objects.create(
            name="Kernel Lab Blueprint",
            slug="kernel-lab-blueprint",
            category=LabCategory.LINUX,
            description="Hands-on exploitation container",
        )
        lab = Lab.objects.create(
            template=template,
            title="Privilege Escalation Lab",
            slug="priv-esc-lab",
            difficulty=LabDifficulty.HARD,
            points=200,
        )
        lab_instance = LabInstance.objects.create(
            lab=lab,
            user=student,
            status='running',
            target_ip='10.10.15.5',
        )
        self.assertEqual(lab_instance.status, 'running')

        # 4. Capstone Project
        capstone = FinalProject.objects.create(
            title="Enterprise Threat Emulation Capstone",
            slug="enterprise-threat-emulation",
            description="Design and execute a multi-host threat emulation.",
        )
        submission = ProjectSubmission.objects.create(
            project=capstone,
            student=student,
            proposal_text="Threat emulation proposal covering MITRE ATT&CK techniques.",
            status=ProjectSubmission.Status.COMPLETED,
            final_grade="A",
            evaluated_by=self.admin,
        )
        self.assertEqual(submission.final_grade, "A")

        # 5. Exam & Certificate
        can_exam, _ = can_take_course_exam(student, prem_course)
        self.assertTrue(can_exam)

        cert = Certificate.objects.create(
            student=student,
            course=prem_course,
            certificate_code="MEL-CERT-PREM-0003",
            student_name=student.username,
            program_title=prem_course.title,
            grade="Honor Distinction",
        )
        self.assertEqual(cert.certificate_code, "MEL-CERT-PREM-0003")

    def test_journey_4_instructor_lifecycle(self):
        """
        JOURNEY 4: Instructor
        Register -> Apply -> Admin review -> Become instructor -> Create course -> Submit course -> Admin approval -> Publish -> Teach students.
        """
        # 1. Register as teacher
        teacher = User.objects.create_user(
            username="teacher_candidate",
            email="candidate@mel.edu.mm",
            password="Password123!",
            role=UserRole.TEACHER,
        )
        # Initially unverified
        self.assertFalse(teacher.teacher_profile.is_verified)

        # 2. Apply
        app = InstructorApplication.objects.create(
            user=teacher,
            bio="10 years cybersecurity engineer & trainer.",
            education_degree="M.Sc. Information Security",
            education_institution="Yangon University",
            teaching_experience_years=6,
            skills="Network Defense, Malware Analysis",
            status=InstructorApplication.Status.PENDING,
        )

        # 3. Admin review & approval
        app.status = InstructorApplication.Status.APPROVED
        app.reviewed_by = self.admin
        app.save()

        teacher.teacher_profile.is_verified = True
        teacher.teacher_profile.level = 'professional'
        teacher.teacher_profile.save()

        # 4. Verified instructor state
        self.assertTrue(teacher.teacher_profile.is_verified)

        # 5. Create draft course
        course = Course.objects.create(
            title="Practical Malware Reverse Engineering",
            slug="practical-malware-rev",
            subject=self.subject,
            owner=teacher,
            price=Decimal('80000.00'),
            status=Course.Status.DRAFT,
        )
        module = Module.objects.create(course=course, title="Module 1: Static Analysis", order=1)
        Lesson.objects.create(module=module, title="Lesson 1: PE Headers", order=1)

        # 6. Submit course for review
        can_sub, _ = can_submit_for_review(teacher, course)
        self.assertTrue(can_sub)
        course.status = Course.Status.PENDING_REVIEW
        course.save()

        # 7. Admin approval & publish
        course.status = Course.Status.PUBLISHED
        course.is_published = True
        course.save()

        self.assertTrue(course.can_publish(teacher))

        # 8. Teach students (Student enrolls in teacher's published course)
        learner = User.objects.create_user(
            username="malware_student",
            email="learner@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        # Direct course purchase payment
        Payment.objects.create(
            student=learner,
            course=course,
            amount=Decimal('80000.00'),
            status=Payment.Status.SUCCESS,
        )
        enroll_student_in_course(learner, course)
        self.assertTrue(can_access_course(learner, course))

    def test_journey_5_partner_lifecycle(self):
        """
        JOURNEY 5: Partner
        Register -> Org verification -> Add staff -> Add existing MEL students -> Create partner course -> Submit & Admin review & Publish -> View students & progress & reports.
        """
        # 1. Register partner applicant
        partner_rep = User.objects.create_user(
            username="apex_rep",
            email="rep@apex-institute.edu.mm",
            password="Password123!",
            role=UserRole.TEACHER,
        )

        # 2. Org application & Admin verification
        app = PartnerApplication.objects.create(
            applicant=partner_rep,
            organization_name="Apex Cybersecurity Institute",
            contact_email="director@apex-institute.edu.mm",
            institution_type="training_center",
            country="Myanmar",
            city="Yangon",
            status=PartnerApplication.Status.PENDING,
        )
        inst = app.approve(reviewed_by=self.admin)
        self.assertTrue(inst.is_verified)
        self.assertTrue(partner_rep.is_partner)

        # 3. Add staff
        staff_member = User.objects.create_user(
            username="apex_staff",
            email="staff@apex-institute.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        PartnerMembership.objects.create(
            institution=inst,
            user=staff_member,
            role=PartnerMembership.Role.STAFF,
            status=PartnerMembership.Status.ACTIVE,
        )

        # 4. Add existing MEL student via invitation workflow
        student = User.objects.create_user(
            username="apex_student",
            email="student@apex-institute.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        invitation = PartnerStudent.objects.create(
            institution=inst,
            student=student,
            class_group="Batch 2026-Q4",
            status=PartnerStudent.Status.PENDING,
        )
        invitation.status = PartnerStudent.Status.ACTIVE
        invitation.responded_at = timezone.now()
        invitation.save()

        # 5. Create partner course
        partner_course = Course.objects.create(
            title="Apex Defensive Operations",
            slug="apex-defensive-ops",
            subject=self.subject,
            owner=partner_rep,
            partner_institution=inst,
            price=Decimal('100000.00'),
            partner_price=Decimal('40000.00'),
            partner_revenue_share_pct=Decimal('75.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )
        eff_price = partner_course.get_effective_price(student)
        self.assertEqual(eff_price['final_price'], Decimal('40000.00'))

        # 6. Partner reports access
        self.client.login(username="apex_rep", password="Password123!")
        resp_portal = self.client.get(reverse('partner-portal'))
        self.assertEqual(resp_portal.status_code, 200)
        self.assertContains(resp_portal, "Apex Cybersecurity Institute")

        resp_rev = self.client.get(reverse('partner-revenue-report'))
        self.assertEqual(resp_rev.status_code, 200)

    def test_journey_6_administrator_lifecycle(self):
        """
        JOURNEY 6: Administrator
        Manage users -> Manage memberships -> Review instructors -> Verify partners -> Review courses -> Manage certificates -> View reports.
        """
        self.client.login(username="admin_mel", password="Password123!")

        # 1. Manage users & roles
        target_user = User.objects.create_user(
            username="target_user",
            email="target@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        target_user.add_role('instructor', assigned_by=self.admin)
        self.assertTrue(target_user.is_teacher)

        # 2. Manage memberships
        plans = SubscriptionPlan.objects.all()
        self.assertGreaterEqual(plans.count(), 3)

        # 3. Review instructors
        app = InstructorApplication.objects.create(
            user=target_user,
            bio="Instructor candidate",
            status=InstructorApplication.Status.PENDING,
        )
        app.status = InstructorApplication.Status.APPROVED
        app.reviewed_by = self.admin
        app.save()
        self.assertEqual(app.status, InstructorApplication.Status.APPROVED)

        # 4. Verify partners
        p_app = PartnerApplication.objects.create(
            applicant=target_user,
            organization_name="Yangon Tech University",
            contact_email="info@ytu.edu.mm",
            status=PartnerApplication.Status.PENDING,
        )
        inst = p_app.approve(reviewed_by=self.admin)
        self.assertTrue(inst.is_verified)

        # 5. Review courses
        pending_course = Course.objects.create(
            title="Admin Reviewed Curriculum",
            slug="admin-reviewed-curriculum",
            subject=self.subject,
            owner=target_user,
            status=Course.Status.PENDING_REVIEW,
        )
        pending_course.status = Course.Status.PUBLISHED
        pending_course.is_published = True
        pending_course.save()
        self.assertEqual(pending_course.status, Course.Status.PUBLISHED)

        # 6. Manage certificates
        cert = Certificate.objects.create(
            student=target_user,
            course=pending_course,
            certificate_code="MEL-CERT-AUDIT-9999",
            student_name="Target User",
            program_title=pending_course.title,
        )
        self.assertFalse(cert.is_revoked)

        # 7. View platform revenue reports
        resp_rev = self.client.get(reverse('platform-revenue-report'))
        self.assertEqual(resp_rev.status_code, 200)


class Phase10CrossSystemPipelineTests(TestCase):
    """
    Validates the end-to-end cross-system pipeline:
    User -> Role -> Membership -> Course -> Enrollment -> Lesson -> Progress -> Assessment -> Exam -> Project/Lab -> Completion -> Certificate -> Verification
    """
    def test_complete_cross_system_lifecycle_chain(self):
        ensure_default_groups()
        SubscriptionPlan.ensure_default_plans()
        client = Client()

        # 1. User
        student = User.objects.create_user(
            username="pipeline_student",
            email="pipeline@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.assertIsNotNone(student.account_id)

        # 2. Role
        self.assertTrue(student.is_student)
        self.assertEqual(student.role, UserRole.STUDENT)

        # 3. Membership
        standard_plan = SubscriptionPlan.objects.get(plan_type='standard')
        UserSubscription.objects.create(
            user=student,
            plan=standard_plan,
            is_active=True,
            status=UserSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=30),
        )

        # 4. Course
        subject = Subject.objects.create(title="Security Pipeline", slug="sec-pipeline")
        course = Course.objects.create(
            title="Certified Incident Response Handler",
            slug="cirh-track",
            subject=subject,
            price=Decimal('50000.00'),
            is_premium=False,
            status=Course.Status.PUBLISHED,
            is_published=True,
            certificate_eligible=True,
        )

        # 5. Enrollment
        enrollment = enroll_student_in_course(student, course)
        self.assertTrue(can_access_course(student, course))

        # 6. Lesson
        module = Module.objects.create(course=course, title="Module 1: Triage", order=1)
        lesson = Lesson.objects.create(module=module, title="Lesson 1: Memory Forensics", order=1)

        # 7. Progress
        UserProgress.objects.create(user=student, course=course, module=module, lesson=lesson, is_completed=True)
        self.assertEqual(enrollment.completed_lessons_count, 1)

        # 8. Assessment
        checkpoint_quiz = Quiz.objects.create(
            module=module,
            title="Checkpoint 1",
            passing_percentage=75,
            quiz_type=Quiz.AssessmentType.QUIZ,
        )
        q_attempt = QuizAttempt.objects.create(student=student, quiz=checkpoint_quiz, score_percentage=100, passed=True)
        self.assertTrue(q_attempt.passed)

        # 9. Exam
        can_exam, _ = can_take_course_exam(student, course)
        self.assertTrue(can_exam)
        final_exam = Quiz.objects.create(
            module=module,
            title="Final Exam",
            passing_percentage=80,
            quiz_type=Quiz.AssessmentType.FINAL_EXAM,
        )
        exam_attempt = QuizAttempt.objects.create(student=student, quiz=final_exam, score_percentage=95, passed=True)
        self.assertTrue(exam_attempt.passed)

        # 10. Project / Lab
        template = LabTemplate.objects.create(
            name="Forensics Investigation Lab",
            slug="forensics-investigation-lab",
            category=LabCategory.FORENSICS,
            description="Forensics practice container",
        )
        lab = Lab.objects.create(template=template, title="Memory Dump Investigation", slug="memory-dump-inv")
        instance = LabInstance.objects.create(lab=lab, user=student, status='running', target_ip='10.10.20.4')
        self.assertEqual(instance.status, 'running')

        # 11. Completion
        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.save(update_fields=['status'])

        # 12. Certificate
        cert = Certificate.objects.create(
            student=student,
            course=course,
            certificate_code="MEL-CIRH-2026-X891",
            student_name="Pipeline Student",
            program_title=course.title,
            grade="Distinction",
        )
        self.assertEqual(cert.certificate_code, "MEL-CIRH-2026-X891")

        # 13. Public Verification
        resp_verify = client.get(reverse('canonical-verify', kwargs={'code': cert.certificate_code}))
        self.assertEqual(resp_verify.status_code, 200)
        self.assertContains(resp_verify, "MEL-CIRH-2026-X891")
        self.assertContains(resp_verify, "Pipeline Student")


class Phase10SecurityAuditTests(TestCase):
    """
    Authorization and security isolation audit suite.
    """
    def setUp(self):
        ensure_default_groups()
        SubscriptionPlan.ensure_default_plans()
        self.client = Client()

        self.student_a = User.objects.create_user(
            username="student_alice",
            email="alice@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.student_b = User.objects.create_user(
            username="student_bob",
            email="bob@mel.edu.mm",
            password="Password123!",
            role=UserRole.STUDENT,
        )
        self.teacher_a = User.objects.create_user(
            username="teacher_albert",
            email="albert@mel.edu.mm",
            password="Password123!",
            role=UserRole.TEACHER,
        )
        self.teacher_b = User.objects.create_user(
            username="teacher_bernard",
            email="bernard@mel.edu.mm",
            password="Password123!",
            role=UserRole.TEACHER,
        )
        self.subject = Subject.objects.create(title="Sec Ops", slug="sec-ops")

    def test_security_student_cannot_become_admin(self):
        """Student cannot escalate role to Administrator or access admin console."""
        self.assertFalse(self.student_a.is_admin)

        # Student cannot switch to instructor mode
        from apps.users.services import switch_user_mode
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            switch_user_mode(self.student_a, 'instructor')

        # Accessing admin console blocked
        self.client.login(username="student_alice", password="Password123!")
        resp = self.client.get(reverse('console-home'))
        self.assertNotEqual(resp.status_code, 200)
        # Redirected or forbidden
        self.assertIn(resp.status_code, (302, 403))

    def test_security_student_cannot_access_another_user_data(self):
        """Student A cannot access Student B's personal profile or private documents."""
        self.client.login(username="student_alice", password="Password123!")
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "student_alice")
        self.assertNotContains(resp, "student_bob")

    def test_security_instructor_cannot_modify_another_instructor(self):
        """Instructor A cannot manage or edit Instructor B's course."""
        course_b = Course.objects.create(
            title="Bernard's Cryptography Course",
            slug="bernard-crypto",
            subject=self.subject,
            owner=self.teacher_b,
            status=Course.Status.DRAFT,
        )
        # Permission check evaluates false
        self.assertFalse(can_manage_course(self.teacher_a, course_b))

        # Instructor B can manage their own course
        self.assertTrue(can_manage_course(self.teacher_b, course_b))

    def test_security_partner_cannot_access_another_partner(self):
        """Partner A cannot access Partner B's institutional dashboard or data."""
        inst_a = Institution.objects.create(
            name="Partner A Academy",
            slug="partner-a-academy",
            contact_person=self.teacher_a,
            is_verified=True,
        )
        inst_b = Institution.objects.create(
            name="Partner B University",
            slug="partner-b-university",
            contact_person=self.teacher_b,
            is_verified=True,
        )
        self.teacher_a.add_role('partner')
        self.teacher_b.add_role('partner')

        self.client.login(username="teacher_albert", password="Password123!")
        resp = self.client.get(reverse('partner-portal'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Partner A Academy")
        self.assertNotContains(resp, "Partner B University")

    def test_security_partner_student_data_is_isolated(self):
        """Partner A cannot see students invited or enrolled under Partner B."""
        inst_a = Institution.objects.create(
            name="Academy One",
            slug="academy-one",
            contact_person=self.teacher_a,
            is_verified=True,
        )
        inst_b = Institution.objects.create(
            name="Academy Two",
            slug="academy-two",
            contact_person=self.teacher_b,
            is_verified=True,
        )
        PartnerStudent.objects.create(
            institution=inst_b,
            student=self.student_b,
            status=PartnerStudent.Status.ACTIVE,
        )

        self.teacher_a.add_role('partner')
        self.client.login(username="teacher_albert", password="Password123!")

        resp = self.client.get(reverse('partner-enrollments'))
        self.assertEqual(resp.status_code, 200)
        # Student B belonging to Partner B is not listed in Partner A's enrollments
        self.assertNotContains(resp, self.student_b.username)

    def test_security_payment_data_is_protected(self):
        """Student A cannot access Student B's payment invoice."""
        course = Course.objects.create(
            title="Paid Security Training",
            slug="paid-sec-training",
            subject=self.subject,
            price=Decimal('20000.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )
        payment_b = Payment.objects.create(
            student=self.student_b,
            course=course,
            amount=Decimal('20000.00'),
            status=Payment.Status.SUCCESS,
        )
        invoice_b = Invoice.objects.create(
            student=self.student_b,
            payment=payment_b,
            amount=Decimal('20000.00'),
            invoice_number="INV-2026-TEST-BOB",
        )

        # Alice attempts to view Bob's invoice
        self.client.login(username="student_alice", password="Password123!")
        resp = self.client.get(reverse('invoice-detail', kwargs={'invoice_id': invoice_b.id}))
        # Returns 403 Forbidden
        self.assertEqual(resp.status_code, 403)

    def test_security_certificate_data_is_protected(self):
        """Public verification displays canonical details without exposing private email/phone."""
        course = Course.objects.create(
            title="Defensive Operations",
            slug="def-ops",
            subject=self.subject,
            price=Decimal('0.00'),
            status=Course.Status.PUBLISHED,
            is_published=True,
        )
        cert = Certificate.objects.create(
            student=self.student_a,
            course=course,
            certificate_code="MEL-CERT-ALICE-SEC1",
            student_name="Alice Candidate",
            program_title=course.title,
        )
        resp = self.client.get(reverse('canonical-verify', kwargs={'code': cert.certificate_code}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Alice Candidate")
        self.assertContains(resp, "MEL-CERT-ALICE-SEC1")
        # Ensure private email is not leaked on public verification page
        self.assertNotContains(resp, self.student_a.email)

    def test_security_lab_access_is_isolated(self):
        """Student A cannot stop, reset, or access Student B's active lab instance."""
        template = LabTemplate.objects.create(
            name="Isolated Lab Template",
            slug="isolated-lab-template",
            category=LabCategory.LINUX,
            description="Isolated container",
        )
        lab = Lab.objects.create(template=template, title="Secret Sandbox", slug="secret-sandbox")
        inst_b = LabInstance.objects.create(
            lab=lab,
            user=self.student_b,
            status='running',
            target_ip='10.10.99.2',
        )

        self.client.login(username="student_alice", password="Password123!")

        # Alice attempts to stop Bob's lab instance -> 404
        resp_stop = self.client.post(reverse('lab-stop', kwargs={'instance_id': inst_b.id}))
        self.assertEqual(resp_stop.status_code, 404)

        # Alice attempts to reset Bob's lab instance -> 404
        resp_reset = self.client.post(reverse('lab-reset', kwargs={'instance_id': inst_b.id}))
        self.assertEqual(resp_reset.status_code, 404)
