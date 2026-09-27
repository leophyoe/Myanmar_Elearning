from .base import BaseLabProvider, DockerLabProvider, WebApplicationLabProvider
from .juice_shop import OWASPJuiceShopProvider
from apps.labs.models import Lab, LabType


def get_lab_provider(lab: Lab) -> BaseLabProvider:
    """
    Factory function returning the specialized LabProvider instance for a lab target.
    """
    if lab.slug == 'owasp-juice-shop' or 'juice-shop' in lab.docker_image.lower():
        return OWASPJuiceShopProvider()
    elif lab.type == LabType.WEB_APPLICATION:
        return WebApplicationLabProvider()
    return DockerLabProvider()


__all__ = [
    'BaseLabProvider',
    'DockerLabProvider',
    'WebApplicationLabProvider',
    'OWASPJuiceShopProvider',
    'get_lab_provider',
]

