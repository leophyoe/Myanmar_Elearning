from django.db.models import Q
from django.contrib.auth import get_user_model
from apps.courses.models import Course, Enrollment
from apps.partner.models import CohortStudent, Institution
from apps.chat.models import UserBlock, ConversationParticipant

User = get_user_model()


def can_access_conversation(user, conversation):
    """
    Privacy-first access rule:
    Only participants of a conversation are permitted to read or send messages in it.
    Administrators do NOT have blanket access to inspect private 1-on-1 chats.
    """
    if not user or not user.is_authenticated:
        return False
    return ConversationParticipant.objects.filter(
        conversation=conversation,
        user=user
    ).exists()


def can_user_message(sender, recipient, course=None):
    """
    Enforces strict role-based messaging boundaries:
    - Sender cannot message themselves.
    - Blocked interactions are rejected.
    - Students may message instructors of courses in which they are actively enrolled,
      their partner institution coordinators, or platform support.
    - Teachers may message students enrolled in their courses, fellow faculty, and admins.
    - Partners may message cohort students and course instructors.
    - Unrelated student-to-student direct messaging is prohibited.
    """
    if not sender or not recipient or not sender.is_authenticated or not recipient.is_authenticated:
        return False, "Authentication required."

    if sender.id == recipient.id:
        return False, "You cannot start a conversation with yourself."

    # Check mutual blocks
    if UserBlock.objects.filter(blocker=sender, blocked_user=recipient).exists():
        return False, "You have blocked this user. Unblock them first to send messages."

    if UserBlock.objects.filter(blocker=recipient, blocked_user=sender).exists():
        return False, "This user is currently not accepting messages from you."

    # Platform administrators have authority to message any platform user
    if getattr(sender, 'is_admin', False) or sender.is_superuser:
        return True, "Authorized (Administrator)"

    # Messaging platform administrators for support/inquiry is always permitted
    if getattr(recipient, 'is_admin', False) or recipient.is_superuser:
        return True, "Authorized (Platform Administration Support)"

    # Specific course context check if provided
    if course:
        if course.owner_id == recipient.id:
            # Recipient is instructor: verify sender enrollment
            has_enrollment = Enrollment.objects.filter(
                course=course,
                student=sender,
                status=Enrollment.Status.ACTIVE
            ).exists()
            if has_enrollment:
                return True, "Authorized (Enrolled Course Student -> Instructor)"

        if course.owner_id == sender.id:
            # Sender is instructor: verify recipient enrollment
            has_enrollment = Enrollment.objects.filter(
                course=course,
                student=recipient,
                status=Enrollment.Status.ACTIVE
            ).exists()
            if has_enrollment:
                return True, "Authorized (Instructor -> Enrolled Course Student)"

    # General Student Permissions
    if getattr(sender, 'is_student', False) and not getattr(sender, 'is_teacher', False):
        # 1. Check if recipient is instructor of ANY actively enrolled course
        enrolled_course_owners = Course.objects.filter(
            enrollments__student=sender,
            enrollments__status=Enrollment.Status.ACTIVE,
            owner__isnull=False
        ).values_list('owner_id', flat=True).distinct()

        if recipient.id in enrolled_course_owners:
            return True, "Authorized (Enrolled Student -> Course Instructor)"

        # 2. Check if recipient is institutional coordinator for the student
        is_cohort_coordinator = Institution.objects.filter(
            cohorts__students__student=sender,
            contact_person=recipient
        ).exists()

        if is_cohort_coordinator:
            return True, "Authorized (Cohort Student -> Partner Coordinator)"

        return False, "Students may only message instructors of their enrolled courses or institutional coordinators."

    # General Teacher / Instructor Permissions
    if getattr(sender, 'is_teacher', False):
        # 1. Fellow faculty (other teachers or instructors)
        if getattr(recipient, 'is_teacher', False):
            return True, "Authorized (Faculty to Faculty)"

        # 2. Students enrolled in any course owned by this teacher
        is_enrolled_student = Enrollment.objects.filter(
            course__owner=sender,
            student=recipient,
            status=Enrollment.Status.ACTIVE
        ).exists()

        if is_enrolled_student:
            return True, "Authorized (Instructor -> Enrolled Student)"

        # 3. Partner institutional coordinators
        is_partner_contact = Institution.objects.filter(
            contact_person=recipient
        ).exists()
        if is_partner_contact:
            return True, "Authorized (Faculty -> Partner Representative)"

        return False, "Instructors may only message enrolled students, fellow faculty, or partner coordinators."

    # General Partner Permissions
    if getattr(sender, 'is_partner', False):
        # 1. Students in their institutional cohorts
        is_institution_student = CohortStudent.objects.filter(
            cohort__institution__contact_person=sender,
            student=recipient
        ).exists()
        if is_institution_student:
            return True, "Authorized (Partner -> Cohort Student)"

        # 2. Instructors teaching courses for their cohorts
        is_cohort_instructor = Course.objects.filter(
            institution_cohorts__institution__contact_person=sender,
            owner=recipient
        ).exists()
        if is_cohort_instructor:
            return True, "Authorized (Partner -> Course Instructor)"

        return False, "Partner coordinators are restricted to their institutional cohorts and instructors."

    return False, "Messaging permission denied."


def get_allowed_recipients(user, query=''):
    """
    Returns a distinct list or QuerySet of Users whom `user` has permission to message.
    """
    if not user or not user.is_authenticated:
        return User.objects.none()

    # Blocked user IDs
    blocked_ids = set(UserBlock.objects.filter(blocker=user).values_list('blocked_user_id', flat=True))
    blocked_by_ids = set(UserBlock.objects.filter(blocked_user=user).values_list('blocker_id', flat=True))
    excluded_ids = blocked_ids | blocked_by_ids | {user.id}

    recipient_ids = set()

    # Always include admins
    admin_ids = User.objects.filter(
        Q(role='admin') | Q(is_superuser=True)
    ).exclude(id__in=excluded_ids).values_list('id', flat=True)
    recipient_ids.update(admin_ids)

    def _build_search_filter(q_text):
        filt = (
            Q(username__icontains=q_text) |
            Q(first_name__icontains=q_text) |
            Q(last_name__icontains=q_text) |
            Q(email__icontains=q_text) |
            Q(account_id__icontains=q_text) |
            Q(student_profile__student_id__icontains=q_text)
        )
        import uuid as _uuid
        try:
            val = _uuid.UUID(q_text)
            filt |= Q(id=val)
        except (ValueError, AttributeError):
            pass
        return filt

    if getattr(user, 'is_admin', False) or user.is_superuser:
        # Admin can search all active platform users
        base_qs = User.objects.filter(is_active=True).exclude(id__in=excluded_ids)
        if query:
            base_qs = base_qs.filter(_build_search_filter(query))
        return base_qs.select_related('teacher_profile', 'student_profile')[:25]

    if getattr(user, 'is_student', False) and not getattr(user, 'is_teacher', False):
        # Enrolled course instructors
        instructor_ids = Course.objects.filter(
            enrollments__student=user,
            enrollments__status=Enrollment.Status.ACTIVE,
            owner__isnull=False
        ).exclude(owner_id__in=excluded_ids).values_list('owner_id', flat=True).distinct()
        recipient_ids.update(instructor_ids)

        # Partner coordinators
        coord_ids = Institution.objects.filter(
            cohorts__students__student=user,
            contact_person__isnull=False
        ).exclude(contact_person_id__in=excluded_ids).values_list('contact_person_id', flat=True).distinct()
        recipient_ids.update(coord_ids)

    elif getattr(user, 'is_teacher', False):
        # Fellow faculty (Teachers, Instructors, Admins)
        faculty_ids = User.objects.filter(
            Q(role='teacher') | Q(role='instructor') | Q(role='admin')
        ).exclude(id__in=excluded_ids).values_list('id', flat=True)
        recipient_ids.update(faculty_ids)

        # Enrolled students
        student_ids = Enrollment.objects.filter(
            course__owner=user,
            status=Enrollment.Status.ACTIVE
        ).exclude(student_id__in=excluded_ids).values_list('student_id', flat=True).distinct()
        recipient_ids.update(student_ids)

    elif getattr(user, 'is_partner', False):
        # Cohort students
        student_ids = CohortStudent.objects.filter(
            cohort__institution__contact_person=user
        ).exclude(student_id__in=excluded_ids).values_list('student_id', flat=True).distinct()
        recipient_ids.update(student_ids)

        # Course instructors
        instructor_ids = Course.objects.filter(
            institution_cohorts__institution__contact_person=user,
            owner__isnull=False
        ).exclude(owner_id__in=excluded_ids).values_list('owner_id', flat=True).distinct()
        recipient_ids.update(instructor_ids)

    qs = User.objects.filter(id__in=recipient_ids, is_active=True)
    if query:
        qs = qs.filter(_build_search_filter(query))
    return qs.select_related('teacher_profile', 'student_profile')[:25]

