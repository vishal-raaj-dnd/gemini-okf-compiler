import os
import yaml
from typing import Dict, Any

def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Formates metadata dictionary into YAML frontmatter.
    Removes internal fields like 'filename' that are not part of the OKF spec.
    """
    # Exclude internal tracking fields
    okf_meta = {
        "type": metadata.get("type"),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "tags": metadata.get("tags"),
        "timestamp": metadata.get("timestamp")
    }
    
    # Safe dump YAML
    yaml_str = yaml.safe_dump(okf_meta, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_str}---\n"

def write_okf_bundle(output_dir: str, concepts: Dict[str, Dict[str, Any]], linked_contents: Dict[str, str]) -> None:
    """
    Writes the concept files and index.md to the output directory, organizing by type.
    """
    # Create the root folder if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Write each concept file
    for concept_id, concept_data in concepts.items():
        meta = concept_data["metadata"]
        category = meta["type"]
        filename = meta["filename"]
        content = linked_contents[concept_id]
        
        # Create category folder
        category_dir = os.path.join(output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Write file with YAML frontmatter
        yaml_frontmatter = format_yaml_frontmatter(meta)
        file_path = os.path.join(category_dir, f"{filename}.md")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(yaml_frontmatter)
            f.write("\n")
            f.write(content)
            
    # Generate and write index.md
    index_content = generate_index_md(concepts)
    index_path = os.path.join(output_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_content)

def generate_index_md(concepts: Dict[str, Dict[str, Any]]) -> str:
    """
    Generates a master index.md file categorizing all concepts.
    """
    # Group concepts by type
    by_category = {}
    for concept_data in concepts.values():
        meta = concept_data["metadata"]
        category = meta["type"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(meta)
        
    # Build markdown index
    lines = [
        "# Knowledge Catalog Index",
        "",
        "Welcome to the Open Knowledge Format (OKF) Bundle. Below is a structured graph index of all available concepts, processes, guides, and reference documents.",
        "",
        "## Catalog by Category",
        ""
    ]
    
    # Sort categories alphabetically
    for category in sorted(by_category.keys()):
        lines.append(f"### {category.capitalize()}")
        lines.append("")
        
        # Sort files inside category by title
        sorted_metas = sorted(by_category[category], key=lambda x: x["title"])
        for meta in sorted_metas:
            title = meta["title"]
            filename = meta["filename"]
            description = meta["description"]
            tags_str = ", ".join(meta["tags"])
            
            # Link path is relative to the index.md root
            link_path = f"./{category}/{filename}.md"
            lines.append(f"- **[{title}]({link_path})** - {description} *({tags_str})*")
            
        lines.append("")
        
    return "\n".join(lines)
