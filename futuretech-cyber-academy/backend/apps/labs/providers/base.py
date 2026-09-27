from abc import ABC, abstractmethod
from typing import Dict, Any
from django.core.exceptions import ValidationError
from apps.labs.models import Lab, LabInstance, LabInstanceStatus


class BaseLabProvider(ABC):
    """
    Abstract interface for Cyber Range execution providers.
    Allows modular extension for Docker containers, web apps, VMs, and cloud ranges.
    """
    @abstractmethod
    def validate(self, lab: Lab) -> None:
        pass

    @abstractmethod
    def start(self, user, lab: Lab, **kwargs) -> LabInstance:
        pass

    @abstractmethod
    def stop(self, instance: LabInstance) -> bool:
        pass

    @abstractmethod
    def reset(self, instance: LabInstance) -> LabInstance:
        pass

    @abstractmethod
    def extend(self, instance: LabInstance, minutes: int = 30) -> LabInstance:
        pass

    @abstractmethod
    def health_check(self, instance: LabInstance) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_access_url(self, instance: LabInstance) -> str:
        pass


class DockerLabProvider(BaseLabProvider):
    """
    Core Docker container orchestration provider with resource limits,
    capability drops, and private bridge networking.
    """
    def __init__(self):
        from apps.labs.docker_service import docker_service
        self.docker_service = docker_service

    def validate(self, lab: Lab) -> None:
        self.docker_service.validate_lab_image(lab)

    def start(self, user, lab: Lab, **kwargs) -> LabInstance:
        self.validate(lab)
        instance = self.docker_service.start_lab(user, lab)
        instance.access_url = self.get_access_url(instance)
        instance.save(update_fields=['access_url'])
        return instance

    def stop(self, instance: LabInstance) -> bool:
        return self.docker_service.stop_lab(instance)

    def reset(self, instance: LabInstance) -> LabInstance:
        fresh = self.docker_service.reset_lab(instance)
        fresh.access_url = self.get_access_url(fresh)
        fresh.save(update_fields=['access_url'])
        return fresh

    def extend(self, instance: LabInstance, minutes: int = 30) -> LabInstance:
        return self.docker_service.extend_lab(instance, minutes)

    def health_check(self, instance: LabInstance) -> Dict[str, Any]:
        return {
            'is_healthy': instance.is_running and not instance.is_expired,
            'status': instance.status,
            'assigned_ip': instance.assigned_ip,
        }

    def get_access_url(self, instance: LabInstance) -> str:
        return f"/labs/{instance.lab.slug}/terminal/?instance={instance.uuid}"


class WebApplicationLabProvider(DockerLabProvider):
    """
    Specialized provider for interactive Web Application security training targets.
    Routes students through the controlled secure reverse-proxy gateway /labs/i/<token>/.
    Prevents direct exposure of Docker container ports to the open internet.
    """
    def __init__(self, internal_web_port: int = 80):
        super().__init__()
        self.internal_web_port = internal_web_port

    def get_access_url(self, instance: LabInstance) -> str:
        # Controlled reverse proxy gateway endpoint
        return f"/labs/i/{instance.uuid}/"

