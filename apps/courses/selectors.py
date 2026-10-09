"""
Reusable query selectors and filters for Course discovery, authoring, and partner management.
"""
from typing import Optional
from django.db.models import QuerySet, Q, Count
from django.contrib.auth import get_user_model
from .models import Course, Subject


def get_published_courses(
    subject_slug: Optional[str] = None,
    level: Optional[str] = None,
    access_type: Optional[str] = None,
    search_query: Optional[str] = None,
    is_premium: Optional[bool] = None,
    owner_type: Optional[str] = None,
    partner_id: Optional[str] = None,
    price_type: Optional[str] = None,
    sort: Optional[str] = None,
) -> QuerySet[Course]:
    """
    Returns public catalog courses that are active and published.
    Supports granular multi-criteria filtering, text search, price filtering, and sorting.
    """
    qs = Course.objects.filter(
        is_published=True,
        status=Course.Status.PUBLISHED,
    ).select_related(
        'subject', 'owner', 'partner_institution'
    ).prefetch_related('modules__lessons').annotate(
        enrollments_count=Count('enrollments', filter=Q(enrollments__status='active'), distinct=True)
    )

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

    if price_type == 'free':
        qs = qs.filter(Q(price__isnull=True) | Q(price__lte=0) | Q(access_type=Course.AccessType.FREE))
    elif price_type == 'paid':
        qs = qs.filter(Q(price__gt=0) & ~Q(access_type=Course.AccessType.FREE))

    if search_query:
        query = search_query.strip()
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(subject__title__icontains=query) |
            Q(owner__username__icontains=query) |
            Q(partner_institution__name__icontains=query)
        )

    # Sorting
    if sort == 'popular':
        qs = qs.order_by('-enrollments_count', '-created_at')
    elif sort == 'newest':
        qs = qs.order_by('-created_at')
    elif sort == 'price_asc':
        qs = qs.order_by('price', '-created_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-price', '-created_at')
    elif sort == 'title':
        qs = qs.order_by('title')
    else:
        qs = qs.order_by('-is_official', '-created_at')

    return qs.distinct()


def get_featured_courses(limit: int = 8) -> QuerySet[Course]:
    """
    Returns official or premium highlighted courses for featured discovery showcase.
    """
    return get_published_courses().filter(
        Q(is_official=True) | Q(is_premium=True)
    ).order_by('-is_official', '-created_at')[:limit]


def get_popular_courses(limit: int = 8) -> QuerySet[Course]:
    """
    Returns trending courses ordered by active enrollment count.
    """
    return get_published_courses(sort='popular')[:limit]


def get_new_courses(limit: int = 8) -> QuerySet[Course]:
    """
    Returns the newest additions to the catalog.
    """
    return get_published_courses(sort='newest')[:limit]


def get_free_courses(limit: int = 8) -> QuerySet[Course]:
    """
    Returns free introductory and open-access courses.
    """
    return get_published_courses(price_type='free')[:limit]


def get_popular_categories(limit: int = 8) -> QuerySet[Subject]:
    """
    Returns active subjects/disciplines annotated with published course count.
    """
    return Subject.objects.filter(is_active=True).annotate(
        courses_count=Count(
            'courses',
            filter=Q(courses__is_published=True, courses__status=Course.Status.PUBLISHED),
            distinct=True
        )
    ).order_by('-courses_count', 'order')[:limit]


def get_top_instructors(limit: int = 8):
    """
    Returns active instructors who author published courses, with published course count.
    """
    user_model = get_user_model()
    return user_model.objects.filter(
        owned_courses__is_published=True,
        owned_courses__status=Course.Status.PUBLISHED
    ).distinct().annotate(
        courses_count=Count(
            'owned_courses',
            filter=Q(owned_courses__is_published=True, owned_courses__status=Course.Status.PUBLISHED),
            distinct=True
        )
    ).order_by('-courses_count', 'username')[:limit]


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
