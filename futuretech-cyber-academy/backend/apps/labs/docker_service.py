import logging
import uuid
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import (
    Lab, LabInstance, LabInstanceStatus, LabAccess,
    FlagType, LabFlag
)

logger = logging.getLogger(__name__)

try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False
    DockerException = Exception
    NotFound = Exception
    APIError = Exception


class DockerSandboxService:
    """
    Secure Docker Sandbox Orchestration Service for Cyber Range.
    Enforces strict isolation, resource quotas, allowlisted images, and lifecycle TTL.
    Supports live Docker Engine with automatic fallback to isolated simulation engine.
    """

    DEFAULT_ALLOWLISTED_IMAGES = {
        "futuretech/dvwa-target:1.0",
        "futuretech/linux-privesc-target:1.0",
        "futuretech/pcap-analysis-target:1.0",
        "futuretech/metasploitable-target:latest",
        "futuretech/web-vuln-playground:latest",
        "futuretech/buffer-overflow-sandbox:latest",
        "bkimminich/juice-shop:v17.1.1",
        "bkimminich/juice-shop:latest",
        "futuretech/juice-shop:17.1.1",
    }

    def __init__(self):
        self.client = None
        self._is_live_docker = False

        if DOCKER_SDK_AVAILABLE:
            try:
                self.client = docker.from_env(timeout=3)
                self.client.ping()
                self._is_live_docker = True
                logger.info("Connected to live Docker Engine daemon.")
            except Exception as e:
                logger.warning(f"Docker daemon not accessible: {e}. Operating in Sandboxed Simulation Mode.")
                self.client = None
                self._is_live_docker = False

    @property
    def is_live_docker(self) -> bool:
        return self._is_live_docker

    def validate_lab_image(self, lab: Lab):
        """
        Validates that the lab image is allowlisted and approved.
        """
        image_name = lab.docker_image.strip()
        if not image_name:
            raise ValidationError(f"Lab '{lab.name}' does not have a configured Docker image.")

        # Check against approved prefixes or registered allowlist
        if not (image_name.startswith("futuretech/") or image_name in self.DEFAULT_ALLOWLISTED_IMAGES):
            raise ValidationError(f"Docker image '{image_name}' is not in the approved Cyber Range allowlist.")

    def start_lab(self, user, lab: Lab) -> LabInstance:
        """
        Starts an isolated target sandbox for a student.
        Enforces maximum of 1 concurrent active lab per student.
        """
        # 1. Enforce single active instance constraint
        active_instance = LabInstance.objects.filter(
            student=user,
            status__in=[LabInstanceStatus.CREATING, LabInstanceStatus.RUNNING]
        ).first()

        if active_instance:
            if active_instance.lab == lab:
                # Return existing instance if already running
                return active_instance
            else:
                raise ValidationError(
                    f"You already have an active lab instance running for '{active_instance.lab.name}'. "
                    "Please stop your current lab before launching a new target."
                )

        # 2. Validate allowlisted Docker image
        self.validate_lab_image(lab)

        now = timezone.now()
        ttl_minutes = lab.max_runtime_minutes or 60
        expires_at = now + timedelta(minutes=ttl_minutes)

        # 3. Create database record
        instance = LabInstance.objects.create(
            lab=lab,
            student=user,
            status=LabInstanceStatus.CREATING,
            started_at=now,
            expires_at=expires_at,
            last_activity=now,
        )

        container_name = f"ftc_target_{lab.slug[:16]}_{instance.uuid.hex[:8]}"

        try:
            if self._is_live_docker and self.client:
                # ==========================================================
                # LIVE PRODUCTION DOCKER DEPLOYMENT
                # ==========================================================
                # Convert resource limits
                nano_cpus = int(float(lab.cpu_limit or 1.0) * 1e9)
                mem_limit = f"{lab.memory_limit_mb or 1024}m"
                pids_limit = lab.process_limit or 100

                # Provision container with strict sandboxing
                container = self.client.containers.run(
                    image=lab.docker_image,
                    name=container_name,
                    detach=True,
                    nano_cpus=nano_cpus,
                    mem_limit=mem_limit,
                    pids_limit=pids_limit,
                    security_opt=["no-new-privileges:true"],
                    cap_drop=["ALL"],
                    cap_add=["NET_BIND_SERVICE"],  # Allow binding standard HTTP/SSH ports
                    network_mode="bridge",
                    labels={
                        "managed_by": "futuretech_academy",
                        "student_id": str(user.id),
                        "instance_uuid": str(instance.uuid),
                        "lab_id": str(lab.id),
                    }
                )

                # Fetch network info
                container.reload()
                networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                ip_addr = "127.0.0.1"
                for net_name, net_conf in networks.items():
                    ip_addr = net_conf.get("IPAddress", ip_addr)

                target_url = (
                    f"/labs/i/{instance.uuid}/"
                    if lab.type == "WEB_APPLICATION"
                    else f"/labs/{lab.slug}/terminal/?instance={instance.uuid}"
                )
                instance.container_id = container.id[:12]
                instance.internal_address = ip_addr
                instance.assigned_ip = ip_addr
                instance.status = LabInstanceStatus.RUNNING
                instance.access_url = target_url
                instance.save()
            else:
                # ==========================================================
                # SECURE SANDBOXED SIMULATION DEPLOYMENT
                # ==========================================================
                # Generates deterministic isolated student network node
                subnet_octet = (abs(hash(str(instance.uuid))) % 200) + 10
                ip_addr = f"10.10.{subnet_octet}.15"
                target_url = (
                    f"/labs/i/{instance.uuid}/"
                    if lab.type == "WEB_APPLICATION"
                    else f"/labs/{lab.slug}/terminal/?instance={instance.uuid}"
                )

                instance.container_id = f"sim-{instance.uuid.hex[:8]}"
                instance.internal_address = ip_addr
                instance.assigned_ip = ip_addr
                instance.port_mappings = "3000/tcp, 80/tcp, 443/tcp" if lab.type == "WEB_APPLICATION" else "80/tcp, 443/tcp, 22/tcp"
                instance.status = LabInstanceStatus.RUNNING
                instance.access_url = target_url
                instance.save()

            # Generate dynamic instance flag if lab uses dynamic flag pattern
            dynamic_flag_obj = lab.flags.filter(flag_type=FlagType.DYNAMIC_FLAG).first()
            if dynamic_flag_obj:
                flag_str = dynamic_flag_obj.dynamic_flag_pattern.replace(
                    "{instance_uuid}", instance.uuid.hex[:12]
                )
                # Store dynamic flag in flags lookup
                LabFlag.objects.get_or_create(
                    lab=lab,
                    flag_type=FlagType.DYNAMIC_FLAG,
                    static_flag=flag_str,
                    defaults={'points': dynamic_flag_obj.points}
                )

            logger.info(f"Successfully deployed lab instance {instance.uuid} for user {user.username}.")
            return instance

        except Exception as err:
            logger.error(f"Failed to spawn lab container: {err}")
            instance.status = LabInstanceStatus.FAILED
            instance.save(update_fields=['status'])
            raise ValidationError(f"Could not provision sandbox container: {err}")

    def stop_lab(self, instance: LabInstance) -> bool:
        """
        Stops and removes the running container instance cleanly.
        """
        if instance.status in [LabInstanceStatus.STOPPED, LabInstanceStatus.EXPIRED]:
            return True

        try:
            if self._is_live_docker and self.client and instance.container_id:
                try:
                    container = self.client.containers.get(instance.container_id)
                    container.stop(timeout=5)
                    container.remove(force=True)
                except NotFound:
                    pass
                except Exception as e:
                    logger.warning(f"Error removing container {instance.container_id}: {e}")

            instance.status = LabInstanceStatus.STOPPED
            instance.stopped_at = timezone.now()
            instance.save(update_fields=['status', 'stopped_at'])
            logger.info(f"Stopped lab instance {instance.uuid}.")
            return True
        except Exception as e:
            logger.error(f"Error stopping lab instance {instance.uuid}: {e}")
            instance.status = LabInstanceStatus.STOPPED
            instance.save(update_fields=['status'])
            return False

    def reset_lab(self, instance: LabInstance) -> LabInstance:
        """
        Destroys the current instance and launches a brand new fresh environment.
        """
        user = instance.student
        lab = instance.lab
        self.stop_lab(instance)
        return self.start_lab(user, lab)

    def extend_lab(self, instance: LabInstance, minutes: int = 30) -> LabInstance:
        """
        Extends the lab session TTL up to an absolute cap (3 hours).
        """
        if instance.status != LabInstanceStatus.RUNNING:
            raise ValidationError("Cannot extend a stopped or expired lab instance.")

        max_cap = instance.started_at + timedelta(hours=3)
        new_expires_at = instance.expires_at + timedelta(minutes=minutes)

        if new_expires_at > max_cap:
            new_expires_at = max_cap

        instance.expires_at = new_expires_at
        instance.save(update_fields=['expires_at'])
        return instance

    def cleanup_expired_instances(self) -> int:
        """
        Reaps all expired lab instances and cleans up orphaned containers.
        """
        now = timezone.now()
        expired_instances = LabInstance.objects.filter(
            status=LabInstanceStatus.RUNNING,
            expires_at__lte=now
        )
        count = 0
        for inst in expired_instances:
            self.stop_lab(inst)
            inst.status = LabInstanceStatus.EXPIRED
            inst.save(update_fields=['status'])
            count += 1

        if count > 0:
            logger.info(f"Reaped {count} expired lab instances.")
        return count


# Singleton orchestrator instance
docker_service = DockerSandboxService()

