import hashlib
import json
import logging
import os
from typing import Any, Dict

MANIFEST_FILENAME = "manifest.json"
logger = logging.getLogger(__name__)


def calculate_file_hash(filepath: str) -> str:
    """Calculates the MD5 hash of the file contents."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_manifest(output_dir: str) -> Dict[str, Any]:
    """Loads the manifest file from the output directory, returning an empty dict if absent or invalid."""
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    if not os.path.exists(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load manifest file %s: %s", manifest_path, exc)
        return {}


def save_manifest(output_dir: str, manifest_data: Dict[str, Any]) -> None:
    """Saves the manifest data to manifest.json in the output directory."""
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
