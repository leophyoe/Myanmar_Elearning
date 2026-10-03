from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Institution, PartnerMembership, PartnerStudent

User = get_user_model()


def add_partner_staff(institution: Institution, user, role=PartnerMembership.StaffRole.STAFF, title='', department=''):
    """
    Grant institutional staff privileges to a user under a specific institution.
    Also ensures the user possesses the PARTNER role.
    """
    with transaction.atomic():
        membership, created = PartnerMembership.objects.update_or_create(
            institution=institution,
            user=user,
            defaults={
                'role': role,
                'status': PartnerMembership.Status.ACTIVE,
                'title': title,
                'department': department,
            }
        )
        if hasattr(user, 'add_role'):
            user.add_role('partner')
        return membership


def enroll_partner_student_by_account_id(institution: Institution, account_id: str, external_student_id=''):
    """
    Associate a student with a partner institution using their unique Account ID (MEL-XXXXXXXX)
    or email address without duplicating user accounts.
    """
    clean_id = account_id.strip()
    student = User.objects.filter(account_id__iexact=clean_id).first()
    if not student:
        # Fallback search by email
        student = User.objects.filter(email__iexact=clean_id).first()
    if not student:
        raise ValidationError(f"No student found with Account ID or Email: '{account_id}'")

    partner_student, created = PartnerStudent.objects.update_or_create(
        institution=institution,
        student=student,
        defaults={
            'external_student_id': external_student_id,
            'status': PartnerStudent.Status.ACTIVE,
        }
    )
    return partner_student


def calculate_partner_revenue_split(amount, partner_pct=Decimal('25.00')):
    """
    Calculate configurable revenue share split between Partner Institution (default 25%)
    and Myanmar E-Learning Platform/Instructor (default 75%).
    """
    amount = Decimal(str(amount))
    partner_ratio = Decimal(str(partner_pct)) / Decimal('100.00')
    partner_share = (amount * partner_ratio).quantize(Decimal('0.01'))
    platform_author_share = amount - partner_share
    return {
        'total_amount': amount,
        'partner_share': partner_share,
        'platform_author_share': platform_author_share,
        'partner_percentage': partner_pct,
        'platform_author_percentage': Decimal('100.00') - partner_pct,
    }
