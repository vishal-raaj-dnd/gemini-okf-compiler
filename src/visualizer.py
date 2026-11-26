import html
import re
from typing import Any, Dict, List, Optional, Tuple

_LINK_RE = re.compile(r"\]\((?:\./|\.\./([^/)]+)/)?([^/)]+)\.md\)")


def _escape_mermaid_label(title: str) -> str:
    """Sanitizes a node label so quotes or brackets cannot break Mermaid syntax."""
    cleaned = title.replace('"', "'").replace("[", "(").replace("]", ")")
    return cleaned.replace("\n", " ").strip()


def build_raw_mermaid_graph(
    concepts: Dict[str, Dict[str, Any]],
    linked_contents: Optional[Dict[str, str]] = None,
) -> str:
    """
    Analyzes cross-links between concepts and returns raw Mermaid flowchart syntax.
    Uses deterministic sequential node IDs to prevent filename slug collisions.
    """
    nodes: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for idx, (_, concept_data) in enumerate(concepts.items(), start=1):
        meta = concept_data["metadata"]
        key = (meta["type"], meta["filename"])
        if key not in nodes:
            nodes[key] = (f"node_{idx}", _escape_mermaid_label(meta["title"]))

    edges: List[str] = []
    seen_edges = set()

    for concept_id, concept_data in concepts.items():
        source_meta = concept_data["metadata"]
        source_key = (source_meta["type"], source_meta["filename"])
        if source_key not in nodes:
            continue

        source_id, source_title = nodes[source_key]
        content = linked_contents.get(concept_id, concept_data["content"]) if linked_contents else concept_data["content"]

        for target_cat, target_file in _LINK_RE.findall(content):
            resolved_cat = target_cat if target_cat else source_meta["type"]
            target_key = (resolved_cat, target_file)
            if target_key in nodes and target_key != source_key:
                target_id, target_title = nodes[target_key]
                edge_key = (source_id, target_id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(f'    {source_id}["{source_title}"] --> {target_id}["{target_title}"]')

    if not edges:
        for mermaid_id, title in nodes.values():
            edges.append(f'    {mermaid_id}["{title}"]')

    return "\n".join(["graph TD", *edges])


def generate_mermaid_graph(
    concepts: Dict[str, Dict[str, Any]],
    linked_contents: Optional[Dict[str, str]] = None,
) -> str:
    """Generates a Mermaid graph block wrapped in Markdown fences."""
    raw_graph = build_raw_mermaid_graph(concepts, linked_contents)
    return "\n".join(["## 📊 Knowledge Graph", "", "```mermaid", raw_graph, "```", ""])


def generate_visualizer_html(
    concepts: Dict[str, Dict[str, Any]],
    linked_contents: Optional[Dict[str, str]] = None,
) -> str:
    """Generates a standalone HTML page to visualize the compiled knowledge graph using Mermaid.js."""
    raw_graph = html.escape(build_raw_mermaid_graph(concepts, linked_contents))

    return f"""<!DOCTYPE html>
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
        }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
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
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4);
            max-width: 1200px;
            width: 100%;
            padding: 40px;
            box-sizing: border-box;
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
        <h1>OmniOKF Knowledge Visualizer</h1>
        <p>Interactive graph showing semantic links and conceptual dependencies parsed by OmniOKF.</p>
    </header>
    <div class="main-container">
        <div class="graph-wrapper">
            <pre class="mermaid">
{raw_graph}
            </pre>
        </div>
    </div>
    <footer>
        Generated by <a href="https://github.com/vishal-raaj-dnd/gemini-okf-compiler" target="_blank" rel="noopener noreferrer">OmniOKF Compiler</a>.
    </footer>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'dark',
            securityLevel: 'strict',
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
