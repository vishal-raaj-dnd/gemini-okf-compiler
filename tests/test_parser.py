import pytest

from src.parser import sanitize_slug, smart_local_classify, split_markdown


def test_split_markdown_ignores_headers_inside_code_blocks() -> None:
    md = (
        "\n\n"
        "# Top Title\n\n"
        "Intro text.\n\n"
        "## Section One\n\n"
        "```python\n"
        "# This is a python comment, not a heading\n"
        "## Neither is this\n"
        "x = 1\n"
        "```\n\n"
        "## Section Two\n\n"
        "More content.\n"
    )
    chunks = split_markdown(md, "##")
    assert len(chunks) == 3
    assert chunks[0]["header"] == "Top Title"
    assert chunks[1]["header"] == "Section One"
    assert "# This is a python comment" in chunks[1]["content"]
    assert chunks[2]["header"] == "Section Two"


def test_split_markdown_rejects_invalid_split_level() -> None:
    with pytest.raises(ValueError, match="Invalid split_level"):
        split_markdown("# Hello", "invalid")


def test_smart_local_classify_extracts_domain_agnostic_tags() -> None:
    meta = smart_local_classify(
        "Database Setup Guide",
        "Configure `postgresql.conf` with `wal_level` for streaming replication.",
        idx=1,
    )
    assert meta["type"] == "guide"
    assert meta["filename"] == "database-setup-guide"
    assert meta["timestamp"].endswith("Z")
    assert "general" not in meta["tags"]
    assert any(t in meta["tags"] for t in ("postgresql-conf", "wal-level", "database", "replication"))


def test_sanitize_slug_prevents_traversal_and_empty_names() -> None:
    assert sanitize_slug("../../etc/passwd") == "etc-passwd"
    assert sanitize_slug("   !!!   ", fallback="concept-9") == "concept-9"
