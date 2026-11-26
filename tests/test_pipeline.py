import json
import shutil
from pathlib import Path

from src.pipeline import run_compiler_pipeline


def test_pipeline_offline_compilation_and_cache_invalidation(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    sample_doc = docs_dir / "handbook.md"
    shutil.copyfile("example_raw.md", sample_doc)

    out_dir = tmp_path / ".okf"

    # 1. Initial offline compilation
    assert run_compiler_pipeline(str(docs_dir), str(out_dir), "##", offline=True) is True
    assert (out_dir / "index.md").exists()
    assert (out_dir / "visualizer.html").exists()
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(iter(manifest.values()))
    assert entry["mode"] == "offline"
    assert entry["split_level"] == "##"
    # Manifest must store unlinked content (no relative .md links baked in)
    for concept in entry["concepts"]:
        assert "../" not in concept["content"]

    # 2. Second run with same split_level hits cache cleanly
    assert run_compiler_pipeline(str(docs_dir), str(out_dir), "##", offline=True) is True

    # 3. Changing split_level invalidates cache and recompiles
    assert run_compiler_pipeline(str(docs_dir), str(out_dir), "#", offline=True) is True
    manifest_after = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry_after = next(iter(manifest_after.values()))
    assert entry_after["split_level"] == "#"
    assert len(entry_after["concepts"]) == 1


def test_pipeline_returns_false_for_missing_input(tmp_path: Path) -> None:
    assert run_compiler_pipeline(str(tmp_path / "nonexistent"), str(tmp_path / ".okf"), "##", offline=True) is False
