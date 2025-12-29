"""Atomic JSON output writer with last-known-good fallback."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from tahoe_conditions.config import OUTPUT_DIR, RESORTS_OUTPUT_DIR
from tahoe_conditions.models import ResortConditions, Summary

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def write_json_atomic(path: Path, data: dict | list | BaseModel) -> None:
    """
    Write JSON atomically using temp file + rename.

    Args:
        path: Target path
        data: Data to write (dict, list, or Pydantic model)
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert Pydantic models to dict
    if isinstance(data, BaseModel):
        json_data = data.model_dump(mode="json")
    else:
        json_data = data

    # Write to temp file in same directory (for atomic rename)
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.stem}_",
        suffix=".tmp"
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, cls=DateTimeEncoder)
            f.write("\n")

        # Atomic rename
        os.replace(temp_path, path)
        logger.debug(f"Wrote {path}")

    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load_existing_resort(slug: str) -> Optional[ResortConditions]:
    """
    Load existing resort data for last-known-good fallback.

    Args:
        slug: Resort slug

    Returns:
        ResortConditions if exists, None otherwise
    """
    path = RESORTS_OUTPUT_DIR / f"{slug}.json"

    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ResortConditions(**data)
    except Exception as e:
        logger.warning(f"Failed to load existing data for {slug}: {e}")
        return None


def write_resort(resort: ResortConditions) -> None:
    """
    Write individual resort JSON file.

    Args:
        resort: Resort conditions
    """
    path = RESORTS_OUTPUT_DIR / f"{resort.slug}.json"
    write_json_atomic(path, resort)


def write_latest(resorts: list[ResortConditions]) -> None:
    """
    Write latest.json with all resorts.

    Args:
        resorts: List of all resort conditions
    """
    path = OUTPUT_DIR / "latest.json"

    data = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "resorts": [r.model_dump(mode="json") for r in resorts],
    }

    write_json_atomic(path, data)
    logger.info(f"Wrote {path} with {len(resorts)} resorts")


def write_summary(summary: Summary) -> None:
    """
    Write summary.json.

    Args:
        summary: Summary object
    """
    path = OUTPUT_DIR / "summary.json"
    write_json_atomic(path, summary)
    logger.info(f"Wrote {path}")


def write_all_outputs(resorts: list[ResortConditions], summary: Summary) -> None:
    """
    Write all output files.

    Args:
        resorts: List of resort conditions
        summary: Summary object
    """
    # Ensure directories exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESORTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write individual resort files
    for resort in resorts:
        write_resort(resort)

    # Write aggregated files
    write_latest(resorts)
    write_summary(summary)
