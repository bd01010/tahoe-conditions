"""Load resort configurations from YAML registry."""

import logging
from pathlib import Path
from typing import Optional

import yaml

from tahoe_conditions.config import RESORTS_YAML
from tahoe_conditions.models import ResortConfig

logger = logging.getLogger(__name__)


def load_resorts(yaml_path: Optional[Path] = None) -> list[ResortConfig]:
    """
    Load resort configurations from YAML file.

    Args:
        yaml_path: Path to resorts.yaml, defaults to config.RESORTS_YAML

    Returns:
        List of ResortConfig objects
    """
    path = yaml_path or RESORTS_YAML

    if not path.exists():
        raise FileNotFoundError(f"Resort registry not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    resorts = []
    for item in data.get("resorts", []):
        try:
            resort = ResortConfig(**item)
            resorts.append(resort)
        except Exception as e:
            logger.warning(f"Invalid resort config: {item.get('slug', 'unknown')}: {e}")

    logger.info(f"Loaded {len(resorts)} resorts from registry")
    return resorts


def get_enabled_resorts(yaml_path: Optional[Path] = None) -> list[ResortConfig]:
    """Get only enabled resorts from registry."""
    resorts = load_resorts(yaml_path)
    enabled = [r for r in resorts if r.enabled]
    logger.info(f"{len(enabled)} resorts enabled")
    return enabled
