"""
Centralized access control services for Courses and Learning Material.
Evaluates enrollment, membership entitlements, direct course purchases, and institutional partner privileges.
"""
from decimal import Decimal
from django.utils import timezone
from apps.courses.models import Course, Enrollment, Lesson
from apps.billing.models import active_payment_for, active_subscription_for


def can_view_course(user, course: Course) -> bool:
    """
    Determines whether a course is visible in public directory or detail preview.
    - Published courses are publicly visible to all visitors.
    - Draft/Pending/Rejected courses are only visible to platform admins,
      the course author, or staff of the affiliated partner institution.
    """
    if course.status == Course.Status.PUBLISHED and getattr(course, 'is_published', False):
        return True

    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_admin', False):
        return True

    if course.owner_id and course.owner_id == user.id:
        return True

    if course.partner_institution_id:
        from apps.partner.models import PartnerMembership
        if PartnerMembership.objects.filter(
            institution_id=course.partner_institution_id,
            user=user,
            status=PartnerMembership.Status.ACTIVE
        ).exists():
            return True

    return False


def can_manage_course(user, course: Course) -> bool:
    """
    Determines whether a user has editorial control to edit curriculum, modules, or lessons.
    - Platform administrators can edit any course.
    - Official platform courses can ONLY be managed by administrators.
    - Courses under administrative review (PENDING_REVIEW) are locked against modification.
    - Instructors can manage their own non-official courses.
    - Partner organization managers can manage courses belonging to their institution.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_admin', False):
        return True

    if getattr(course, 'is_official', False):
        return False

    if course.status == Course.Status.PENDING_REVIEW:
        return False

    if course.owner_id and course.owner_id == user.id:
        return True

    if course.partner_institution_id:
        from apps.partner.models import PartnerMembership
        return PartnerMembership.objects.filter(
            institution_id=course.partner_institution_id,
            user=user,
            role__in=[
                PartnerMembership.Role.ADMIN,
                PartnerMembership.Role.STAFF,
                PartnerMembership.Role.INSTRUCTOR
            ],
            status=PartnerMembership.Status.ACTIVE
        ).exists()

    return False


def can_submit_for_review(user, course: Course) -> tuple[bool, str]:
    """
    Validates whether a course can transition from DRAFT or REJECTED to PENDING_REVIEW.
    Requirements:
    1. User must own the course or manage its partner institution.
    2. Course must not already be in review or published.
    3. Course must contain at least 1 module.
    4. Course must contain at least 1 lesson.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Login required."

    if course.status == Course.Status.PENDING_REVIEW:
        return False, "Course is already under editorial review."

    if course.status == Course.Status.PUBLISHED:
        return False, "Course is already published."

    # Ownership check
    is_owner = bool(course.owner_id and course.owner_id == user.id)
    is_admin = bool(getattr(user, 'is_admin', False))
    is_partner_manager = False
    if course.partner_institution_id:
        from apps.partner.models import PartnerMembership
        is_partner_manager = PartnerMembership.objects.filter(
            institution_id=course.partner_institution_id,
            user=user,
            status=PartnerMembership.Status.ACTIVE
        ).exists()

    if not (is_owner or is_admin or is_partner_manager):
        return False, "You do not have permission to submit this course for review."

    # Curriculum completeness validation
    if not course.modules.exists():
        return False, "Course must have at least one module before submitting for review."

    if not Lesson.objects.filter(module__course=course).exists():
        return False, "Course must contain at least one lesson before submitting for review."

    return True, ""


def can_publish_course(user, course: Course) -> tuple[bool, str]:
    """
    Validates whether a user can publish a course into the public catalog.
    Requirements:
    1. User must be authenticated.
    2. User must have editorial authority (course owner, platform admin, or partner manager).
    3. User must have instructor publishing rights (admin, verified teacher, or partner manager).
    4. Course must contain at least 1 module.
    5. Course must contain at least 1 lesson.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Login required."

    is_owner = bool(course.owner_id and course.owner_id == user.id)
    is_admin = bool(getattr(user, 'is_admin', False))
    is_partner_manager = False
    if course.partner_institution_id:
        from apps.partner.models import PartnerMembership
        is_partner_manager = PartnerMembership.objects.filter(
            institution_id=course.partner_institution_id,
            user=user,
            status=PartnerMembership.Status.ACTIVE
        ).exists()

    if not (is_owner or is_admin or is_partner_manager):
        return False, "You do not have permission to publish this course."

    # Teacher verification check: unverified teachers cannot publish directly
    if not is_admin and not is_partner_manager:
        if not course.can_publish(user):
            return False, "Only verified instructors can publish courses. Please complete your instructor verification."

    # Curriculum completeness validation
    if not course.modules.exists():
        return False, "Course must have at least one module before it can be published."

    if not Lesson.objects.filter(module__course=course).exists():
        return False, "Course must contain at least one lesson before it can be published."

    return True, ""


def can_review_course(user, course: Course) -> bool:
    """
    Checks if a user has administrative authority to approve, publish, or reject a course.
    """
    return bool(user and getattr(user, 'is_authenticated', False) and getattr(user, 'is_admin', False))


def can_enroll_course(user, course: Course) -> tuple[bool, str]:
    """
    Checks if a user is eligible to enroll in a course.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Please sign in to enrol in this course."

    if Enrollment.objects.filter(course=course, student=user, status=Enrollment.Status.ACTIVE).exists():
        return False, "Already actively enrolled in this course."

    if course.access_type == Course.AccessType.PARTNER_ONLY:
        from apps.partner.models import PartnerStudent, CohortStudent
        is_affiliated = False
        if course.partner_institution_id:
            if PartnerStudent.objects.filter(
                institution_id=course.partner_institution_id,
                student=user,
                status=PartnerStudent.Status.ACTIVE
            ).exists():
                is_affiliated = True
            elif CohortStudent.objects.filter(
                cohort__institution_id=course.partner_institution_id,
                cohort__course=course,
                student=user,
                cohort__is_active=True
            ).exists():
                is_affiliated = True

        if not is_affiliated:
            return False, "This course is restricted to enrolled partner institution students."

    # If course is paid, user must have an active payment or an active qualifying subscription
    if not getattr(course, 'is_free', False) and (getattr(course, 'price', 0) or 0) > 0:
        has_payment = False
        has_sub = False
        payment = active_payment_for(user, course)
        if payment and payment.is_current:
            has_payment = True
        sub = active_subscription_for(user)
        if sub and sub.is_current:
            plan = sub.plan
            plan_type = getattr(plan, 'plan_type', '')
            if getattr(course, 'is_premium', False) or course.access_type == Course.AccessType.PREMIUM:
                has_sub = bool(getattr(plan, 'has_premium_courses', False) or plan_type == 'premium')
            else:
                has_sub = bool(
                    getattr(plan, 'has_all_standard_courses', False) or
                    getattr(plan, 'has_premium_courses', False) or
                    plan_type in ('standard', 'premium')
                )

        if not has_payment and not has_sub:
            return False, f"{course.title} is a paid course — subscribe to a membership plan or complete checkout first."

    return True, ""



def can_access_course(user, course: Course) -> bool:
    """
    Determines whether a user has full learning access to a given course.
    Rules:
    1. Unauthenticated users cannot access course contents.
    2. Platform Administrators have universal access.
    3. Course Author has universal access to their own course.
    4. Enrolled Student must have an ACTIVE enrollment.
    5. Free courses: Once actively enrolled, access is granted.
    6. Direct Course Payment: Approved and unexpired payment unlocks the course.
    7. Membership Subscription Tier:
       - Standard courses unlocked by Standard or Premium plans.
       - Premium courses unlocked exclusively by Premium plan.
    8. Institutional Partner: Students affiliated with the course's partner institution have access.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_admin', False):
        return True

    if course.owner_id and course.owner_id == user.id:
        return True

    # Active or completed enrollment check
    if not Enrollment.objects.filter(
        course=course, student=user, status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED]
    ).exists():
        return False

    # Free course or coupon redemption enrollment check
    if (
        getattr(course, 'is_free', False)
        or course.access_type == Course.AccessType.FREE
        or (getattr(course, 'price', None) is not None and course.price <= 0)
        or Enrollment.objects.filter(
            course=course, student=user, source=Enrollment.Source.COUPON,
            status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED]
        ).exists()
    ):
        return True

    # 1. Direct course purchase check
    payment = active_payment_for(user, course)
    if payment and payment.is_current:
        return True

    # 2. Subscription tier access check
    sub = active_subscription_for(user)
    if sub and sub.is_current:
        plan = sub.plan
        plan_type = getattr(plan, 'plan_type', '')
        if getattr(course, 'is_premium', False) or course.access_type == Course.AccessType.PREMIUM:
            if getattr(plan, 'has_premium_courses', False) or plan_type == 'premium':
                return True
        elif getattr(plan, 'has_all_standard_courses', False) or getattr(plan, 'has_premium_courses', False) or plan_type in ('standard', 'premium'):
            return True

    # 3. Partner institutional affiliation check
    if getattr(course, 'partner_institution_id', None) or course.access_type == Course.AccessType.PARTNER_ONLY:
        from apps.partner.models import PartnerStudent, CohortStudent
        if course.partner_institution_id:
            if PartnerStudent.objects.filter(
                institution_id=course.partner_institution_id,
                student=user,
                status=PartnerStudent.Status.ACTIVE
            ).exists():
                return True
            if CohortStudent.objects.filter(
                cohort__institution_id=course.partner_institution_id,
                cohort__course=course,
                student=user,
                cohort__is_active=True
            ).exists():
                return True

    return False


def can_start_course(user, course: Course) -> tuple[bool, str]:
    """
    Returns whether a user can begin coursework immediately.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Login required to start learning."
    if can_access_course(user, course):
        return True, "Enrolled with active entitlement."
    return False, "Course access entitlement required."


def can_take_course_exam(user, course: Course) -> tuple[bool, str]:
    """
    Checks if student has fulfilled prerequisites to sit for the course exam.
    Course-specific exam rules remain authoritative (e.g. separate voucher fees).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Sign in to take the examination."
    if getattr(user, 'is_admin', False):
        return True, "Platform administrator access."
    if course.owner_id and course.owner_id == user.id:
        return True, "Course author access."
    if not can_access_course(user, course):
        return False, "Active course enrollment and completion required."

    # When exam is required for course completion, all curriculum lessons must be finished first
    if getattr(course, 'exam_required', False):
        from django.db.models import Q
        from apps.courses.models import Lesson, UserProgress

        total_lessons = Lesson.objects.filter(module__course=course).count()
        if total_lessons > 0:
            completed_lessons = UserProgress.objects.filter(
                Q(course=course) | Q(lesson__module__course=course),
                user=user,
                is_completed=True,
                lesson__isnull=False,
            ).distinct().count()
            if completed_lessons < total_lessons:
                return False, f"All curriculum lessons must be completed before taking the Final Assessment ({completed_lessons}/{total_lessons} completed)."

    voucher_price = getattr(course, 'exam_voucher_price', None)
    if voucher_price and voucher_price > Decimal('0.00'):
        from apps.billing.models import Payment
        has_voucher = Payment.objects.filter(
            student=user,
            course=course,
            payment_type=Payment.PaymentType.EXAM_VOUCHER,
            status=Payment.Status.SUCCESS,
        ).exists()
        if not has_voucher:
            return False, "Course-specific exam rules are authoritative: separate exam voucher fee required."

    return True, "Eligible to sit for examination."


def can_claim_certificate(user, course: Course) -> tuple[bool, str]:
    """
    Checks if student has fulfilled prerequisites to claim a completion certificate.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False, "Sign in to claim certificate."
    if not getattr(course, 'certificate_eligible', True):
        return False, "Course is not eligible for certificate issuance."
    if not can_access_course(user, course):
        return False, "Active course enrollment required."
    return True, "Eligible to claim certificate."


def enroll_student_in_course(user, course: Course, source: str = None, partner_institution=None) -> Enrollment:
    """
    Enrolls a student in a course, setting status to ACTIVE and tracking source channel.
    """
    if not source:
        source = Enrollment.Source.FREE if course.is_free else Enrollment.Source.SELF

    enrollment, _ = Enrollment.objects.update_or_create(
        course=course,
        student=user,
        defaults={
            'status': Enrollment.Status.ACTIVE,
            'source': source,
            'partner_institution': partner_institution or course.partner_institution,
        }
    )
    return enrollment
