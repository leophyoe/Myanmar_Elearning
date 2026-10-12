from .urls import urlpatterns

# Re-export all billing patterns unnamespaced to maintain backward compatibility for legacy templates and tests
__all__ = ['urlpatterns']

