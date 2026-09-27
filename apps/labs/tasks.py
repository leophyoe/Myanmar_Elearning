import logging
from django.utils import timezone
from .models import LabInstance
from .orchestrator import orchestrator

logger = logging.getLogger(__name__)

# Celery @shared_task decorator is imported conditionally or fallback to simple function
try:
    from celery import shared_task
except ImportError:
    def shared_task(func):
        return func

@shared_task
def provision_lab_task(instance_id):
    """Background task to provision a student's Docker sandbox."""
    try:
        instance = LabInstance.objects.get(id=instance_id)
        return orchestrator.start_instance(instance)
    except LabInstance.DoesNotExist:
        logger.error(f"LabInstance {instance_id} does not exist.")
        return False

@shared_task
def destroy_lab_task(instance_id):
    """Background task to tear down a student's Docker sandbox."""
    try:
        instance = LabInstance.objects.get(id=instance_id)
        return orchestrator.stop_instance(instance)
    except LabInstance.DoesNotExist:
        return False

@shared_task
def reap_expired_labs():
    """
    Automated reaper task: terminates any running lab instance whose expiration has passed.
    Executed every 60 seconds by Celery Beat.
    """
    now = timezone.now()
    expired_instances = LabInstance.objects.filter(
        status='running',
        expires_at__lte=now
    )
    reaped_count = 0
    for instance in expired_instances:
        logger.info(f"Reaping expired lab instance: {instance.id} (user: {instance.user.username})")
        orchestrator.stop_instance(instance)
        instance.status = 'expired'
        instance.save(update_fields=['status'])
        reaped_count += 1
    return f"Reaped {reaped_count} expired instances."

@shared_task
def collect_resource_telemetry():
    """Gathers memory and CPU usage across running student sandboxes."""
    running_count = LabInstance.objects.filter(status='running').count()
    return f"Active running lab instances: {running_count}"

