"""Docker image build pipeline for lab and challenge bundles."""

import logging
from pathlib import Path
from typing import Tuple

from django.conf import settings

from .models import LabTemplate
from .orchestrator import orchestrator

logger = logging.getLogger(__name__)


def get_template_bundle_path(template: LabTemplate) -> Path:
    """Resolve the filesystem directory for a given LabTemplate bundle."""
    base = Path(settings.CYBER_LAB_DIR)
    if template.docker_compose_path:
        cand = base / template.docker_compose_path.strip('/')
        if cand.is_dir():
            return cand

    # Direct category / slug
    candidates = [
        base / template.category / template.slug,
        base / template.category / template.slug.replace('-', '_'),
        base / template.slug,
        base / template.slug.replace('-', '_'),
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand

    # Search existing folders under cyber/labs/ for Dockerfile matching slug fragments
    if base.is_dir():
        slug_parts = [p for p in template.slug.split('-') if len(p) > 2]
        for sub in base.rglob('*'):
            if sub.is_dir() and any(f.name.lower() == 'dockerfile' for f in sub.iterdir()):
                sub_name = sub.name.lower().replace('-', '_')
                if any(part in sub_name for part in slug_parts):
                    return sub

    return base / template.category / template.slug


def build_template_image(template: LabTemplate, tag: str = None) -> Tuple[bool, str]:
    """
    Build a Docker image from the template's bundle folder.

    Returns:
        (success: bool, message: str)
    """
    bundle_path = get_template_bundle_path(template)
    if not bundle_path.exists():
        return False, f"Bundle folder not found at '{bundle_path}'"

    dockerfile = bundle_path / 'Dockerfile'
    if not dockerfile.is_file():
        # Case-insensitive check
        dockerfiles = [f for f in bundle_path.iterdir() if f.name.lower() == 'dockerfile']
        if not dockerfiles:
            return False, f"No Dockerfile found in bundle folder '{bundle_path}'"
        dockerfile = dockerfiles[0]

    image_tag = tag or template.image_name or f"cyber/{template.slug}:latest"
    client = orchestrator.client

    if not client:
        # Simulation mode when Docker engine is not attached
        logger.info(f"[Simulation] Validated Dockerfile at {dockerfile} for tag {image_tag}")
        return True, f"[Simulated] Dockerfile validated for '{image_tag}' ({bundle_path.name})"

    try:
        logger.info(f"Building Docker image '{image_tag}' from {bundle_path}...")
        client.images.build(
            path=str(bundle_path),
            dockerfile=dockerfile.name,
            tag=image_tag,
            rm=True,
            forcerm=True,
        )
        # Update template image_name if it changed
        if template.image_name != image_tag:
            template.image_name = image_tag
            template.save(update_fields=['image_name'])

        return True, f"Successfully built Docker image '{image_tag}'"
    except Exception as e:
        logger.error(f"Docker build failed for '{image_tag}': {e}", exc_info=True)
        return False, f"Docker build error: {e}"
