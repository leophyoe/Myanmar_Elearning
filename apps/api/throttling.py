from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle, UserRateThrottle


class AuthRateThrottle(ScopedRateThrottle):
    """
    Strict rate limiting for authentication endpoints to prevent brute-force attacks.
    """
    scope = 'auth'


class AssessmentRateThrottle(ScopedRateThrottle):
    """
    Rate limiting for assessment submissions to prevent rapid automated guessing.
    """
    scope = 'assessment'
