from pathlib import Path

from src.indexer import write_okf_bundle
from src.manifest import calculate_file_hash, load_manifest, save_manifest
from src.visualizer import build_raw_mermaid_graph


def test_write_okf_bundle_does_not_mutate_concepts_and_prunes_stale(tmp_path: Path) -> None:
    out_dir = tmp_path / ".okf"
    stale_dir = out_dir / "guide"
    stale_dir.mkdir(parents=True)
    stale_file = stale_dir / "old-doc.md"
    stale_file.write_text("stale", encoding="utf-8")

    concepts = {
        "c1": {
            "metadata": {
                "type": "../../escape",
                "title": 'Intro "Alpha" [v1]',
                "description": "Desc",
                "tags": ["alpha"],
                "timestamp": "2026-01-01T00:00:00Z",
                "filename": "foo-bar",
            },
            "content": "Original unlinked content.",
        },
        "c2": {
            "metadata": {
                "type": "concept",
                "title": "Beta",
                "description": "Desc 2",
                "tags": ["beta"],
                "timestamp": "2026-01-01T00:00:00Z",
                "filename": "foobar",
            },
            "content": "Links to [Intro](../escape/foo-bar.md).",
        },
    }
    linked = {
        "c1": "Linked content for c1.",
        "c2": "Links to [Intro](../escape/foo-bar.md).",
    }

    write_okf_bundle(str(out_dir), concepts, linked, clean=True)

    # Original concepts dict must not be mutated
    assert concepts["c1"]["content"] == "Original unlinked content."
    # Stale file should be pruned
    assert not stale_file.exists()
    # Path traversal must be sanitized inside out_dir
    assert (out_dir / "escape" / "foo-bar.md").exists()
    assert (out_dir / "index.md").exists()
    assert (out_dir / "visualizer.html").exists()

    # Mermaid graph must have distinct node IDs for foo-bar vs foobar and escaped quotes/brackets
    graph = build_raw_mermaid_graph(concepts, linked)
    assert "node_1" in graph and "node_2" in graph
    assert '["Intro \'Alpha\' (v1)"]' in graph


def test_manifest_roundtrip_and_hash(tmp_path: Path) -> None:
    sample = tmp_path / "doc.md"
    sample.write_text("hello world", encoding="utf-8")
    digest = calculate_file_hash(str(sample))
    assert len(digest) == 32

    save_manifest(str(tmp_path), {"doc.md": {"hash": digest}})
    loaded = load_manifest(str(tmp_path))
    assert loaded["doc.md"]["hash"] == digest
