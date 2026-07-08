import os
import json
import hashlib
from typing import Dict, Any

MANIFEST_FILENAME = "manifest.json"

def calculate_file_hash(filepath: str) -> str:
    """
    Calculates the MD5 hash of the file contents.
    Handles both text and binary files.
    """
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        # Read in chunks of 4096 bytes
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_manifest(output_dir: str) -> Dict[str, Any]:
    """
    Loads the manifest file from the output directory.
    Returns an empty dict if the manifest does not exist.
    """
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Failed to load manifest file: {e}")
    return {}

def save_manifest(output_dir: str, manifest_data: Dict[str, Any]) -> None:
    """
    Saves the manifest data to manifest.json in the output directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Warning: Failed to save manifest file: {e}")
