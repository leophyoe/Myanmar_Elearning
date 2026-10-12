from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.users.models import (
    User, UserRole, TeacherProfile, InstructorLevel,
    InstructorApplication, TermAgreement, InstructorLevelHistory
)
from apps.users.terms import record_term_agreement, has_agreed_to_terms, CURRENT_TERMS_VERSION
from apps.courses.models import Course, Enrollment
from apps.courses.forms import CourseForm
from apps.billing.models import (
    Payment, SubscriptionPlan, UserSubscription, PaymentMethod
)


class RoleAndInstructorLevelPolicyTests(TestCase):
    """
    Tests enforcing clear separation between:
    1. Account Roles & Permissions
    2. Instructor Professional Levels & Course Monetization
    3. Student Membership Plans
    4. Individual Course Price & Enrollment
    5. Course Revenue-Sharing Percentages
    """

    def setUp(self):
        self.client = Client()
        PaymentMethod.ensure_defaults()

        # Admin
        self.admin = User.objects.create_superuser(
            username='admin_thuta', password='pw', email='admin@thuta.edu.mm'
        )

        # Student
        self.student = User.objects.create_user(
            username='student_mgmg', password='pw', email='mgmg@student.mm',
            role=UserRole.STUDENT
        )

        # Entry-level Teacher (Free tutorials only)
        self.teacher_entry = User.objects.create_user(
            username='teacher_aye', password='pw', email='aye@teacher.mm',
            role=UserRole.TEACHER
        )
        self.profile_entry = self.teacher_entry.teacher_profile
        self.profile_entry.level = InstructorLevel.TEACHER
        self.profile_entry.is_verified = True
        self.profile_entry.save()

        # Associate Instructor (Paid courses approved, 60/40 split)
        self.instructor_assoc = User.objects.create_user(
            username='inst_kyaw', password='pw', email='kyaw@assoc.mm',
            role=UserRole.INSTRUCTOR
        )
        self.profile_assoc = self.instructor_assoc.teacher_profile
        self.profile_assoc.level = InstructorLevel.ASSOCIATE_INSTRUCTOR
        self.profile_assoc.is_verified = True
        self.profile_assoc.free_tutorial_approved = True
        self.profile_assoc.save()

        # Full Instructor (50/50 split)
        self.instructor_mid = User.objects.create_user(
            username='inst_hla', password='pw', email='hla@instructor.mm',
            role=UserRole.INSTRUCTOR
        )
        self.profile_mid = self.instructor_mid.teacher_profile
        self.profile_mid.level = InstructorLevel.INSTRUCTOR
        self.profile_mid.is_verified = True
        self.profile_mid.free_tutorial_approved = True
        self.profile_mid.save()

        # Professional Instructor (40/60 split)
        self.instructor_pro = User.objects.create_user(
            username='inst_zaw', password='pw', email='zaw@pro.mm',
            role=UserRole.INSTRUCTOR
        )
        self.profile_pro = self.instructor_pro.teacher_profile
        self.profile_pro.level = InstructorLevel.PROFESSIONAL_INSTRUCTOR
        self.profile_pro.is_verified = True
        self.profile_pro.free_tutorial_approved = True
        self.profile_pro.save()

    def test_01_role_and_level_separation(self):
        """Account roles and pedagogical ranks remain strictly decoupled."""
        self.assertTrue(self.teacher_entry.is_teacher)
        self.assertFalse(self.teacher_entry.can_sell_paid_courses)
        self.assertEqual(self.profile_entry.canonical_level, InstructorLevel.TEACHER)
        self.assertEqual(self.profile_entry.platform_revenue_share_pct, 0)
        self.assertEqual(self.profile_entry.instructor_revenue_share_pct, 0)

        # Associate Instructor
        self.assertTrue(self.instructor_assoc.is_teacher)
        self.assertTrue(self.instructor_assoc.can_sell_paid_courses)
        self.assertEqual(self.profile_assoc.canonical_level, InstructorLevel.ASSOCIATE_INSTRUCTOR)
        self.assertEqual(self.profile_assoc.platform_revenue_share_pct, 60)
        self.assertEqual(self.profile_assoc.instructor_revenue_share_pct, 40)

        # Instructor
        self.assertEqual(self.profile_mid.platform_revenue_share_pct, 50)
        self.assertEqual(self.profile_mid.instructor_revenue_share_pct, 50)

        # Professional Instructor
        self.assertEqual(self.profile_pro.platform_revenue_share_pct, 40)
        self.assertEqual(self.profile_pro.instructor_revenue_share_pct, 60)

    def test_02_entry_level_teacher_blocked_from_publishing_paid_courses(self):
        """Entry-level Teacher rank cannot publish or price paid courses."""
        # 1. Clean validation on model
        paid_course = Course(
            title='Hacking 101', slug='hacking-101',
            owner=self.teacher_entry, price=Decimal('25000.00')
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            paid_course.clean()

        # 2. Form validation in Content Studio
        form = CourseForm(
            data={
                'title': 'Hacking 101 Form',
                'description': 'Course description',
                'price': '25000',
                'access_type': Course.AccessType.PAID,
                'billing_period': Course.BillingPeriod.ONE_TIME,
                'level': Course.Level.BEGINNER,
                'language': Course.Language.BURMESE,
                'duration_months': 3,
            },
            request_user=self.teacher_entry
        )
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)
        self.assertIn('Associate Instructor', form.errors['price'][0])

        # But free tutorial is allowed!
        free_course = Course(
            title='Intro Tutorial', slug='intro-tutorial',
            owner=self.teacher_entry, price=Decimal('0.00'), is_free_tutorial=True
        )
        free_course.clean()  # Should not raise!
        free_course.save()
        self.assertTrue(free_course.pk)

    def test_03_associate_instructor_revenue_split_60_40(self):
        """Associate Instructor yields 60% THUTA Platform / 40% Instructor split."""
        course = Course.objects.create(
            title='Fullstack Web Dev', slug='fullstack-web',
            owner=self.instructor_assoc, price=Decimal('50000.00')
        )
        split = Payment.calculate_level_split(Decimal('50000.00'), course=course)
        self.assertEqual(split['platform_commission_pct'], Decimal('60.00'))
        self.assertEqual(split['instructor_share_pct'], Decimal('40.00'))
        self.assertEqual(split['platform_fee'], Decimal('30000.00'))
        self.assertEqual(split['teacher_amount'], Decimal('20000.00'))
        self.assertEqual(split['net_financial_basis'], Decimal('50000.00'))
        self.assertEqual(split['instructor_level_at_payment'], InstructorLevel.ASSOCIATE_INSTRUCTOR)

    def test_04_mid_instructor_revenue_split_50_50(self):
        """Full Instructor yields 50% THUTA Platform / 50% Instructor split."""
        course = Course.objects.create(
            title='Cyber Defense Pro', slug='cyber-defense',
            owner=self.instructor_mid, price=Decimal('80000.00')
        )
        split = Payment.calculate_level_split(Decimal('80000.00'), course=course)
        self.assertEqual(split['platform_commission_pct'], Decimal('50.00'))
        self.assertEqual(split['instructor_share_pct'], Decimal('50.00'))
        self.assertEqual(split['platform_fee'], Decimal('40000.00'))
        self.assertEqual(split['teacher_amount'], Decimal('40000.00'))
        self.assertEqual(split['net_financial_basis'], Decimal('80000.00'))
        self.assertEqual(split['instructor_level_at_payment'], InstructorLevel.INSTRUCTOR)

    def test_05_professional_instructor_revenue_split_40_60(self):
        """Professional Instructor yields 40% THUTA Platform / 60% Instructor split."""
        course = Course.objects.create(
            title='AI & Machine Learning Diploma', slug='ai-diploma',
            owner=self.instructor_pro, price=Decimal('120000.00')
        )
        split = Payment.calculate_level_split(Decimal('120000.00'), course=course)
        self.assertEqual(split['platform_commission_pct'], Decimal('40.00'))
        self.assertEqual(split['instructor_share_pct'], Decimal('60.00'))
        self.assertEqual(split['platform_fee'], Decimal('48000.00'))
        self.assertEqual(split['teacher_amount'], Decimal('72000.00'))
        self.assertEqual(split['net_financial_basis'], Decimal('120000.00'))
        self.assertEqual(split['instructor_level_at_payment'], InstructorLevel.PROFESSIONAL_INSTRUCTOR)

    def test_06_frozen_split_immutability_on_promotion(self):
        """When an instructor is later promoted, past payment splits remain completely frozen."""
        course = Course.objects.create(
            title='Database Engineering', slug='db-eng',
            owner=self.instructor_assoc, price=Decimal('60000.00')
        )
        payment = Payment.objects.create(
            student=self.student,
            course=course,
            amount=Decimal('60000.00'),
            method=Payment.Method.KBZ_PAY,
            status=Payment.Status.PENDING
        )
        payment.mark_success(reviewer=self.admin)

        # Frozen values as Associate Instructor
        self.assertEqual(payment.instructor_level_at_payment, InstructorLevel.ASSOCIATE_INSTRUCTOR)
        self.assertEqual(payment.platform_commission_pct, Decimal('60.00'))
        self.assertEqual(payment.instructor_share_pct, Decimal('40.00'))
        self.assertEqual(payment.platform_fee, Decimal('36000.00'))
        self.assertEqual(payment.teacher_amount, Decimal('24000.00'))

        # Later: Admin promotes instructor to Professional Instructor!
        self.profile_assoc.level = InstructorLevel.PROFESSIONAL_INSTRUCTOR
        self.profile_assoc.save()

        # Audit history logged
        InstructorLevelHistory.objects.create(
            user=self.instructor_assoc,
            previous_level=InstructorLevel.ASSOCIATE_INSTRUCTOR,
            new_level=InstructorLevel.PROFESSIONAL_INSTRUCTOR,
            changed_by=self.admin,
            reason="Promotion based on student feedback and course reviews"
        )

        # Refresh payment from DB — MUST REMAIN FROZEN!
        payment.refresh_from_db()
        self.assertEqual(payment.instructor_level_at_payment, InstructorLevel.ASSOCIATE_INSTRUCTOR)
        self.assertEqual(payment.platform_commission_pct, Decimal('60.00'))
        self.assertEqual(payment.instructor_share_pct, Decimal('40.00'))
        self.assertEqual(payment.platform_fee, Decimal('36000.00'))
        self.assertEqual(payment.teacher_amount, Decimal('24000.00'))

    def test_07_student_membership_plan_independence(self):
        """Student membership subscriptions are 100% platform revenue and do not grant instructor privileges."""
        plan = SubscriptionPlan.objects.create(
            name='Standard Membership',
            plan_type=SubscriptionPlan.PlanType.STANDARD,
            monthly_price=Decimal('5000.00'),
            has_all_standard_courses=True
        )
        payment = Payment.objects.create(
            student=self.student,
            plan=plan,
            payment_type=Payment.PaymentType.SUBSCRIPTION,
            amount=Decimal('5000.00'),
            method=Payment.Method.KBZ_PAY,
            status=Payment.Status.SUCCESS
        )
        self.assertEqual(payment.platform_fee, Decimal('5000.00'))
        self.assertEqual(payment.teacher_amount, Decimal('0.00'))
        self.assertEqual(payment.platform_commission_pct, Decimal('100.00'))
        self.assertEqual(payment.instructor_share_pct, Decimal('0.00'))

        # Student remains a student!
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_teacher)
        self.assertEqual(self.student.role, UserRole.STUDENT)

    def test_08_versioned_term_agreements_tracking(self):
        """Platform policies require auditable versioned agreements."""
        record_term_agreement(
            user=self.student,
            terms_type=TermAgreement.TermsType.STUDENT_REGISTRATION,
            terms_version=CURRENT_TERMS_VERSION,
            ip_address='127.0.0.1',
            user_agent='Mozilla/5.0 TestBrowser',
            metadata={'consent': True}
        )
        self.assertTrue(
            has_agreed_to_terms(
                self.student,
                TermAgreement.TermsType.STUDENT_REGISTRATION,
                CURRENT_TERMS_VERSION
            )
        )
        agreement = TermAgreement.objects.filter(
            user=self.student,
            terms_type=TermAgreement.TermsType.STUDENT_REGISTRATION
        ).first()
        self.assertIsNotNone(agreement)
        self.assertEqual(agreement.terms_version, CURRENT_TERMS_VERSION)
        self.assertEqual(agreement.ip_address, '127.0.0.1')

    def test_09_faculty_application_form_with_terms_and_free_tutorial(self):
        """Faculty application form enforces mandatory terms agreement and free tutorial inputs."""
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('apply-instructor'),
            {
                'department': 'Faculty of Computing',
                'title': 'Senior Lecturer',
                'target_subjects': 'Python, Cybersecurity',
                'qualifications': 'M.Sc. Computer Science',
                'teaching_experience': '5 years teaching experience',
                'bio': 'Passionate about digital security education',
                'free_tutorial_title': 'Introduction to Cryptography Basics',
                'free_tutorial_url': 'https://thuta.edu.mm/courses/crypto-intro',
                'terms_accepted': 'on',
                'terms_version': '2026.1',
            }
        )
        self.assertEqual(response.status_code, 302)
        app = InstructorApplication.objects.filter(user=self.student).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.free_tutorial_title, 'Introduction to Cryptography Basics')
        self.assertEqual(app.terms_version, '2026.1')
        self.assertTrue(app.terms_accepted)

        # Verified that TermAgreement was automatically recorded
        self.assertTrue(
            has_agreed_to_terms(
                self.student,
                TermAgreement.TermsType.TEACHER_APPLICATION,
                '2026.1'
            )
        )

    def test_10_admin_console_application_approval_records_level_history(self):
        """Admin console approving application assigns rank, approves free tutorial, and writes history log."""
        app = InstructorApplication.objects.create(
            user=self.student,
            department='Cyber Security',
            title='Lecturer',
            target_subjects='Network Defense',
            free_tutorial_title='Firewall Basics',
            free_tutorial_url='https://thuta.edu.mm/courses/firewall-basics',
            terms_accepted=True,
            terms_version='2026.1',
            status=InstructorApplication.Status.PENDING,
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('console-instructor-application-action', kwargs={'app_id': app.id, 'action': 'approve'}),
            {
                'awarded_level': InstructorApplication.AwardedLevel.ASSOCIATE,
                'free_tutorial_approved': '1',
                'admin_notes': 'Credentials verified. Free tutorial accepted.',
            }
        )
        self.assertEqual(response.status_code, 302)

        app.refresh_from_db()
        self.assertEqual(app.status, InstructorApplication.Status.APPROVED)
        self.assertEqual(app.awarded_level, InstructorApplication.AwardedLevel.ASSOCIATE)

        self.student.refresh_from_db()
        self.assertEqual(self.student.role, UserRole.INSTRUCTOR)
        self.assertTrue(self.student.teacher_profile.is_verified)
        self.assertTrue(self.student.teacher_profile.free_tutorial_approved)
        self.assertEqual(self.student.teacher_profile.level, InstructorLevel.ASSOCIATE_INSTRUCTOR)
        self.assertTrue(self.student.teacher_profile.can_sell_paid_courses)

        # Audit history log created
        history = InstructorLevelHistory.objects.filter(user=self.student).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.new_level, InstructorApplication.AwardedLevel.ASSOCIATE)
        self.assertEqual(history.changed_by, self.admin)

