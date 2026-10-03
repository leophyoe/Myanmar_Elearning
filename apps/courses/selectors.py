"""
Reusable query selectors and filters for Course discovery, authoring, and partner management.
"""
from typing import Optional
from django.db.models import QuerySet, Q
from .models import Course


def get_published_courses(
    subject_slug: Optional[str] = None,
    level: Optional[str] = None,
    access_type: Optional[str] = None,
    search_query: Optional[str] = None,
    is_premium: Optional[bool] = None,
    owner_type: Optional[str] = None,
    partner_id: Optional[str] = None,
) -> QuerySet[Course]:
    """
    Returns public catalog courses that are active and published.
    Supports granular multi-criteria filtering and text search.
    """
    qs = Course.objects.filter(
        is_published=True,
        status=Course.Status.PUBLISHED,
    ).select_related('subject', 'owner', 'partner_institution').prefetch_related('modules__lessons')

    if subject_slug:
        qs = qs.filter(subject__slug=subject_slug)

    if level:
        qs = qs.filter(level=level)

    if access_type:
        qs = qs.filter(access_type=access_type)

    if is_premium is not None:
        qs = qs.filter(is_premium=is_premium)

    if owner_type:
        qs = qs.filter(owner_type=owner_type)

    if partner_id:
        qs = qs.filter(partner_institution_id=partner_id)

    if search_query:
        query = search_query.strip()
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(subject__title__icontains=query) |
            Q(owner__username__icontains=query) |
            Q(partner_institution__name__icontains=query)
        )

    return qs.distinct()


def get_instructor_courses(user) -> QuerySet[Course]:
    """
    Returns courses authored by the given instructor.
    """
    return Course.objects.filter(
        owner=user,
        is_official=False,
    ).select_related('subject', 'partner_institution').prefetch_related('modules__lessons')


def get_partner_courses(institution) -> QuerySet[Course]:
    """
    Returns courses affiliated with the specified partner institution.
    """
    return Course.objects.filter(
        partner_institution=institution,
    ).select_related('subject', 'owner').prefetch_related('modules__lessons')


def get_pending_review_courses() -> QuerySet[Course]:
    """
    Returns courses submitted by instructors or partners awaiting admin approval.
    """
    return Course.objects.filter(
        status=Course.Status.PENDING_REVIEW,
    ).select_related('subject', 'owner', 'partner_institution').prefetch_related('modules__lessons').order_by('-updated_at')
