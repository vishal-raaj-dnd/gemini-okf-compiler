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

def build_raw_mermaid_graph(concepts: Dict[str, Dict[str, Any]]) -> str:
    """
    Analyzes references between concepts and returns raw Mermaid flowchart syntax.
    """
    edges = []
    nodes = {}
    
    # Pre-collect node labels and clean IDs
    for concept_id, concept_data in concepts.items():
        meta = concept_data["metadata"]
        filename = meta["filename"]
        title = meta["title"]
        # Safe ID for Mermaid: must start with a letter and contain only alphanumeric chars
        mermaid_id = "node_" + re.sub(r'[^a-zA-Z0-9]', '', filename)
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
            
    graph_lines = ["graph TD"]
    graph_lines.extend(edges)
    return "\n".join(graph_lines)

def generate_mermaid_graph(concepts: Dict[str, Dict[str, Any]]) -> str:
    """
    Generates a Mermaid graph representation wrapped in Markdown tags.
    """
    raw_graph = build_raw_mermaid_graph(concepts)
    graph_lines = [
        "## 📊 Knowledge Graph",
        "",
        "```mermaid",
        raw_graph,
        "```",
        ""
    ]
    return "\n".join(graph_lines)

def generate_visualizer_html(concepts: Dict[str, Dict[str, Any]]) -> str:
    """
    Generates a premium, interactive standalone HTML/CSS page to visualize
    the compiled knowledge graph using Mermaid.js.
    """
    raw_graph = build_raw_mermaid_graph(concepts)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OmniOKF Knowledge Visualizer</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --panel-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-color: #38bdf8;
            --success-color: #10b981;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 40px;
            max-width: 800px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent-color);
            margin: 0 0 10px 0;
            letter-spacing: -0.025em;
            text-shadow: 0 0 40px rgba(56, 189, 248, 0.15);
        }}
        
        p {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin: 0;
            line-height: 1.6;
        }}
        
        .main-container {{
            background-color: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 10px 10px -5px rgba(0, 0, 0, 0.4);
            max-width: 1200px;
            width: 100%;
            padding: 40px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        
        .graph-wrapper {{
            width: 100%;
            overflow-x: auto;
            display: flex;
            justify-content: center;
            padding: 20px;
            border-radius: 8px;
            background-color: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .mermaid {{
            width: 100%;
            display: flex;
            justify-content: center;
        }}
        
        footer {{
            margin-top: 50px;
            font-size: 0.875rem;
            color: var(--text-secondary);
            text-align: center;
        }}
        
        footer a {{
            color: var(--accent-color);
            text-decoration: none;
        }}
        
        footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🌌 OmniOKF Knowledge Visualizer</h1>
        <p>Interactive graph showing semantic links and conceptual dependencies parsed by your OKF compiler.</p>
    </header>
    
    <div class="main-container">
        <div class="graph-wrapper">
            <pre class="mermaid">
{raw_graph}
            </pre>
        </div>
    </div>
    
    <footer>
        Generated dynamically by <a href="https://github.com/vishal-raaj-dnd/OKF-Compiler-PDF-to-Markdown-to-OKF-Open-Knowledge-Format-" target="_blank">OmniOKF Compiler</a>.
    </footer>

    <!-- Load Mermaid ES module dynamically via ESM CDN -->
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ 
            startOnLoad: true,
            theme: 'dark',
            securityLevel: 'loose',
            flowchart: {{
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis'
            }}
        }});
    </script>
</body>
</html>
"""
    return html

def write_okf_bundle(output_dir: str, concepts: Dict[str, Dict[str, Any]], linked_contents: Dict[str, str]) -> None:
    """
    Writes the concept files, index.md, and visualizer.html to the output directory.
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
        
    # Generate and write visualizer.html
    html_content = generate_visualizer_html(concepts)
    html_path = os.path.join(output_dir, "visualizer.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

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
    
    # Insert Mermaid Diagram link and raw graph
    lines.append(generate_mermaid_graph(concepts))
    lines.append("💡 *Tip: Open [visualizer.html](./visualizer.html) in your browser to view this network graph as a beautiful interactive dashboard!*")
    lines.append("")
    
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
