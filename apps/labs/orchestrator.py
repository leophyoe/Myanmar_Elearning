import logging
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

class DockerOrchestrator:
    """
    Manages isolated, restricted Docker container instances and internal bridge networks.
    Enforces strict security boundaries to prevent WAN egress and container breakouts.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env(timeout=5)
            except Exception as e:
                logger.warning(f"Docker engine connection unavailable: {e}. Running in simulation/mock mode.")
                self._client = None
        return self._client

    def start_instance(self, instance):
        """
        Allocates an isolated bridge network and starts the target container.
        """
        instance.status = 'provisioning'
        instance.save(update_fields=['status'])

        # 1. Generate unique dynamic flag
        flag = instance.generate_dynamic_flag()
        instance.started_at = timezone.now()
        instance.expires_at = timezone.now() + timedelta(minutes=instance.lab.template.default_duration_minutes)

        if not self.client:
            # Simulated environment when Docker daemon is not active
            instance.container_id = f"sim-{instance.id}"
            instance.network_name = f"sim-net-{instance.id}"
            instance.target_ip = "172.30.1.100"
            instance.status = 'running'
            instance.save()
            return True

        template = instance.lab.template
        net_name = f"ftcr_net_{str(instance.id)[:12]}"
        container_name = f"ftcr_lab_{str(instance.id)[:12]}"

        try:
            # 2. Create isolated Docker bridge network with internal=True (NO Internet / WAN egress)
            network = self.client.networks.create(
                name=net_name,
                driver="bridge",
                internal=True,
                check_duplicate=True,
                labels={"ftcr.managed": "true", "ftcr.instance_id": str(instance.id)}
            )
            instance.network_name = net_name

            # 3. Define restricted container configuration
            container = self.client.containers.create(
                image=template.image_name,
                name=container_name,
                environment={
                    "FTCR_FLAG": flag,
                    "INSTANCE_ID": str(instance.id),
                    "STUDENT_USER": instance.user.username,
                },
                network=net_name,
                mem_limit=template.mem_limit,
                memswap_limit=template.mem_limit,
                cpu_quota=int(float(template.cpu_limit) * 100000),
                pids_limit=template.pids_limit,
                cap_drop=["ALL"],
                cap_add=["CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"],
                security_opt=["no-new-privileges:true"],
                read_only=template.read_only_root,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m", "/run": "rw,noexec,nosuid,size=16m"},
                labels={"ftcr.managed": "true", "ftcr.instance_id": str(instance.id)}
            )

            container.start()
            container.reload()

            # 4. Inject dynamic flag into container filesystem (/root/flag.txt, /home/student/flag.txt)
            self._inject_flag_files(container, flag)

            # Extract internal IP address
            networks_data = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            assigned_ip = networks_data.get(net_name, {}).get('IPAddress', '172.30.1.100')

            instance.container_id = container.id
            instance.target_ip = assigned_ip
            instance.status = 'running'
            instance.save()
            return True

        except Exception as e:
            logger.error(f"Failed to provision container for instance {instance.id}: {e}", exc_info=True)
            instance.status = 'failed'
            instance.error_log = str(e)
            instance.save()
            return False

    def _inject_flag_files(self, container, flag: str):
        """
        Injects the dynamic flag into filesystem targets (/root/flag.txt, /home/student/flag.txt, /tmp/flag.txt)
        so students can retrieve it during Linux, Web, or Privilege Escalation labs.
        """
        try:
            safe_flag = flag.replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
            inject_cmd = (
                f"sh -c 'mkdir -p /root /home/student 2>/dev/null; "
                f"echo \"{safe_flag}\" > /root/flag.txt 2>/dev/null; "
                f"echo \"{safe_flag}\" > /home/student/flag.txt 2>/dev/null; "
                f"echo \"{safe_flag}\" > /tmp/flag.txt 2>/dev/null; "
                f"chmod 644 /home/student/flag.txt /tmp/flag.txt 2>/dev/null; "
                f"chmod 600 /root/flag.txt 2>/dev/null || true'"
            )
            container.exec_run(inject_cmd, user="root")
            logger.info(f"Dynamic flag injected successfully into container {container.id[:12]}")
        except Exception as e:
            logger.debug(f"Flag file injection non-fatal note for container: {e}")

    def stop_instance(self, instance):
        """Stops and cleans up the container and associated isolated bridge network."""
        instance.status = 'stopping'
        instance.save(update_fields=['status'])

        if not self.client or str(instance.container_id).startswith("sim-"):
            instance.status = 'stopped'
            instance.save()
            return True

        # Remove container
        if instance.container_id:
            try:
                container = self.client.containers.get(instance.container_id)
                container.kill()
                container.remove(v=True, force=True)
            except Exception as e:
                logger.warning(f"Container removal error ({instance.container_id}): {e}")

        # Remove isolated network
        if instance.network_name:
            try:
                network = self.client.networks.get(instance.network_name)
                network.remove()
            except Exception as e:
                logger.warning(f"Network removal error ({instance.network_name}): {e}")

        instance.status = 'stopped'
        instance.container_id = None
        instance.network_name = None
        instance.save()
        return True

    def reset_instance(self, instance):
        """Destroys current instance and creates a fresh instance with new credentials & flag."""
        self.stop_instance(instance)
        return self.start_instance(instance)

orchestrator = DockerOrchestrator()

