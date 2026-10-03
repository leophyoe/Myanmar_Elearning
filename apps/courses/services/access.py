"""
Centralized access control services for Courses and Learning Material.
Evaluates enrollment, membership entitlements, direct course purchases, and institutional partner privileges.
"""
from apps.courses.models import Course, Enrollment
from apps.billing.models import active_payment_for, active_subscription_for


def can_access_course(user, course: Course) -> bool:
    """
    Determines whether a user has full learning access to a given course.
    Rules:
    1. Unauthenticated users cannot access course contents.
    2. Platform Administrators and Instructors (Teachers) have universal access.
    3. Student must have an ACTIVE enrollment.
    4. If course is free (is_free or price <= 0), access is granted once actively enrolled.
    5. Direct Course Payment: Approved and unexpired payment unlocks the course.
    6. Membership Subscription Tier:
       - Starter Tier: Free courses only.
       - Standard Tier: All standard courses across all disciplines.
       - Premium Tier: All courses, including premium and cyber range courses.
    7. Institutional Partner: If course has a partner institution, enrolled partner students
       or cohort students have access.
    """
    if not getattr(user, 'is_authenticated', False):
        return False

    if getattr(user, 'is_teacher', False) or getattr(user, 'is_admin', False):
        return True

    # Active enrollment check
    if not Enrollment.objects.filter(
        course=course, student=user, status=Enrollment.Status.ACTIVE
    ).exists():
        return False

    # Free course check
    if getattr(course, 'is_free', False) or (getattr(course, 'price', None) is not None and course.price <= 0):
        return True

    # 1. Direct course purchase check
    payment = active_payment_for(user, course)
    if payment and payment.is_current:
        return True

    # 2. Subscription tier access check
    sub = active_subscription_for(user)
    if sub and sub.is_current:
        if getattr(course, 'is_premium', False):
            if getattr(sub.plan, 'has_premium_courses', False):
                return True
        elif getattr(sub.plan, 'has_all_standard_courses', False):
            return True

    # 3. Partner institutional affiliation check
    if getattr(course, 'partner_institution_id', None):
        from apps.partner.models import PartnerStudent, CohortStudent
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
