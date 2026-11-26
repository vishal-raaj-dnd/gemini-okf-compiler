from src.linker import cross_link_concepts, get_link_keywords, get_relative_path


def test_get_relative_path_same_and_different_categories() -> None:
    assert get_relative_path("guide", "guide", "setup") == "./setup.md"
    assert get_relative_path("process", "guide", "setup") == "../guide/setup.md"


def test_get_link_keywords_strips_numbering_and_parentheticals() -> None:
    kws = get_link_keywords("3.1 Incident Response (Production)")
    assert "3.1 Incident Response (Production)" in kws
    assert "Incident Response" in kws


def test_cross_link_preserves_code_headings_and_existing_links() -> None:
    concepts = {
        "c1": {
            "metadata": {
                "type": "guide",
                "title": "Database Setup",
                "filename": "database-setup",
            },
            "content": (
                "# Database Setup\n\n"
                "Follow Backup Standards for safety.\n\n"
                "```bash\n"
                "# Backup Standards inside code must stay untouched\n"
                "```\n\n"
                "Inline `Backup Standards` must stay untouched.\n"
                "Existing [Backup Standards](../reference/custom.md) stays untouched.\n"
            ),
        },
        "c2": {
            "metadata": {
                "type": "reference",
                "title": "Backup Standards",
                "filename": "backup-standards",
            },
            "content": "# Backup Standards\n\nDaily backups are required.",
        },
    }

    linked = cross_link_concepts(concepts)
    c1_out = linked["c1"]

    assert "Follow [Backup Standards](../reference/backup-standards.md) for safety." in c1_out
    assert "# Backup Standards inside code must stay untouched" in c1_out
    assert "Inline `Backup Standards` must stay untouched." in c1_out
    assert "Existing [Backup Standards](../reference/custom.md) stays untouched." in c1_out
