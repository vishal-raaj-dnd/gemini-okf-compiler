import os
from typing import Any, Dict, List, Optional, Set

import yaml

from src.parser import sanitize_slug
from src.visualizer import generate_mermaid_graph, generate_visualizer_html


def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """Formats metadata dictionary into OKF-compliant YAML frontmatter."""
    okf_meta = {
        "type": metadata.get("type"),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "tags": metadata.get("tags"),
        "timestamp": metadata.get("timestamp"),
    }
    yaml_str = yaml.safe_dump(okf_meta, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n"


def _resolve_safe_output_path(output_dir: str, category: str, filename: str) -> str:
    """Resolves and validates that the target concept file path stays within output_dir."""
    safe_category = sanitize_slug(category, fallback="concept")
    safe_filename = sanitize_slug(filename, fallback="concept")
    base_abs = os.path.abspath(output_dir)
    target_path = os.path.abspath(os.path.join(base_abs, safe_category, f"{safe_filename}.md"))
    if not target_path.startswith(base_abs + os.sep):
        raise ValueError(f"Unsafe output path resolved: {target_path}")
    return target_path


def _prune_stale_files(output_dir: str, active_paths: Set[str]) -> None:
    """Removes stale concept .md files from category subdirectories that are no longer in the bundle."""
    base_abs = os.path.abspath(output_dir)
    index_abs = os.path.join(base_abs, "index.md")
    for root, _, files in os.walk(base_abs):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            full_path = os.path.abspath(os.path.join(root, fname))
            if full_path == index_abs:
                continue
            if full_path not in active_paths:
                os.remove(full_path)


def generate_index_md(
    concepts: Dict[str, Dict[str, Any]],
    linked_contents: Optional[Dict[str, str]] = None,
) -> str:
    """Generates the master index.md catalog categorizing all concepts."""
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for concept_data in concepts.values():
        meta = concept_data["metadata"]
        category = meta["type"]
        by_category.setdefault(category, []).append(meta)

    lines = [
        "# Knowledge Catalog Index",
        "",
        "Welcome to the Open Knowledge Format (OKF) Bundle. Below is a structured graph index of all available concepts, processes, guides, and reference documents.",
        "",
        generate_mermaid_graph(concepts, linked_contents),
        "*Tip: Open [visualizer.html](./visualizer.html) in your browser to view this network graph.*",
        "",
        "## Catalog by Category",
        "",
    ]

    for category in sorted(by_category.keys()):
        lines.append(f"### {category.capitalize()}")
        lines.append("")
        for meta in sorted(by_category[category], key=lambda item: item["title"]):
            title = meta["title"]
            filename = meta["filename"]
            description = meta["description"]
            tags_str = ", ".join(meta["tags"])
            link_path = f"./{category}/{filename}.md"
            lines.append(f"- **[{title}]({link_path})** - {description} *({tags_str})*")
        lines.append("")

    return "\n".join(lines)


def write_okf_bundle(
    output_dir: str,
    concepts: Dict[str, Dict[str, Any]],
    linked_contents: Dict[str, str],
    clean: bool = False,
) -> None:
    """
    Writes concept files, index.md, and visualizer.html to output_dir.
    Does not mutate the input `concepts` dictionary.
    """
    os.makedirs(output_dir, exist_ok=True)
    written_paths: Set[str] = set()

    for concept_id, concept_data in concepts.items():
        meta = concept_data["metadata"]
        content = linked_contents.get(concept_id, concept_data["content"])
        file_path = _resolve_safe_output_path(output_dir, meta["type"], meta["filename"])
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        yaml_frontmatter = format_yaml_frontmatter(meta)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(yaml_frontmatter)
            f.write("\n")
            f.write(content)
        written_paths.add(file_path)

    if clean:
        _prune_stale_files(output_dir, written_paths)

    index_path = os.path.join(output_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(generate_index_md(concepts, linked_contents))

    html_path = os.path.join(output_dir, "visualizer.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(generate_visualizer_html(concepts, linked_contents))
