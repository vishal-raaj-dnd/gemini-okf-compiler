import os
import yaml
import re
from typing import Dict, Any, List

def format_yaml_frontmatter(metadata: Dict[str, Any]) -> str:
    """
    Formats metadata dictionary into YAML frontmatter.
    Removes internal fields like 'filename' that are not part of the OKF spec.
    """
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

def generate_mermaid_graph(concepts: Dict[str, Dict[str, Any]]) -> str:
    """
    Inspects concept contents for relative markdown links to other concepts
    and generates a Mermaid graph flowchart representation.
    """
    edges = []
    nodes = {}
    
    # Pre-collect node labels and clean IDs
    for concept_id, concept_data in concepts.items():
        meta = concept_data["metadata"]
        filename = meta["filename"]
        title = meta["title"]
        # Safe ID for Mermaid: letters and numbers only
        mermaid_id = re.sub(r'[^a-zA-Z0-9]', '', filename)
        nodes[filename] = (mermaid_id, title)
        

    # Find links in content
    # Look for links in format [text](../category/filename.md) or [text](./filename.md)
    link_pattern = re.compile(r'\]\((?:\./|\.\./[a-zA-Z0-9_\-]+/)?([a-zA-Z0-9_\-]+)\.md\)')
    
    for concept_id, concept_data in concepts.items():
        source_meta = concept_data["metadata"]
        source_filename = source_meta["filename"]
        content = concept_data["content"]
        
        if source_filename not in nodes:
            continue
            
        source_id, source_title = nodes[source_filename]
        
        # Scan content for target filenames
        targets = link_pattern.findall(content)
        for target_filename in targets:
            if target_filename in nodes and target_filename != source_filename:
                target_id, target_title = nodes[target_filename]
                edge = f'    {source_id}["{source_title}"] --> {target_id}["{target_title}"]'
                if edge not in edges:
                    edges.append(edge)
                    
    # Build Mermaid graph
    if not edges:
        # Fallback if no links: just show nodes
        for filename, (mermaid_id, title) in nodes.items():
            edges.append(f'    {mermaid_id}["{title}"]')
            
    graph_lines = [
        "## 📊 Knowledge Graph",
        "",
        "```mermaid",
        "graph TD",
    ]
    graph_lines.extend(edges)
    graph_lines.extend([
        "```",
        ""
    ])
    return "\n".join(graph_lines)

def write_okf_bundle(output_dir: str, concepts: Dict[str, Dict[str, Any]], linked_contents: Dict[str, str]) -> None:
    """
    Writes the concept files and index.md to the output directory, organizing by type.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Update contents in concepts dict with linked contents
    for concept_id, content in linked_contents.items():
        concepts[concept_id]["content"] = content
        
    # Write each concept file
    for concept_id, concept_data in concepts.items():
        meta = concept_data["metadata"]
        category = meta["type"]
        filename = meta["filename"]
        content = concept_data["content"]
        
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
    ]
    
    # Insert Mermaid Diagram
    lines.append(generate_mermaid_graph(concepts))
    
    lines.extend([
        "## Catalog by Category",
        ""
    ])
    
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
