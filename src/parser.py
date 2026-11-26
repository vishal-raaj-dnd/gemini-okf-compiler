import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

_STOPWORDS = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "your", "are", "was",
    "were", "will", "have", "has", "had", "not", "but", "can", "all", "use",
    "using", "used", "into", "when", "where", "which", "what", "how", "why",
    "who", "whom", "their", "there", "these", "those", "then", "than", "also",
    "only", "more", "most", "some", "such", "each", "other", "about", "after",
    "before", "between", "should", "could", "would", "must", "may", "might",
    "make", "made", "take", "takes", "ensure", "based", "within", "through",
    "following", "section", "document", "documentation", "example", "note",
})

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def sanitize_slug(text: str, fallback: str = "concept") -> str:
    """Normalizes arbitrary text into a safe, lowercase kebab-case filename slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug if slug else fallback


def split_markdown(content: str, split_level: str = "##") -> List[Dict[str, Any]]:
    """
    Splits a markdown string into sections at headers at or above `split_level`.
    Ignores headers inside fenced code blocks (``` or ~~~).
    """
    stripped_level = split_level.strip()
    if not stripped_level or any(ch != "#" for ch in stripped_level):
        raise ValueError(f"Invalid split_level '{split_level}'. Expected '#' characters (e.g., '#', '##').")
    split_level_num = min(max(len(stripped_level), 1), 6)

    lines = content.splitlines()
    chunks: List[Dict[str, Any]] = []

    current_header = "Introduction"
    current_header_level = 1
    current_chunk_lines: List[str] = []
    active_fence: str | None = None

    for line in lines:
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            fence_token = fence_match.group(1)
            if active_fence is None:
                active_fence = fence_token[0]
            elif line.strip().startswith(active_fence * 3):
                active_fence = None
            current_chunk_lines.append(line)
            continue

        if active_fence is None:
            match = _HEADER_RE.match(line.strip())
            if match:
                level_str, title = match.groups()
                level_num = len(level_str)
                if level_num <= split_level_num:
                    joined_content = "\n".join(current_chunk_lines).strip()
                    if joined_content:
                        chunks.append({
                            "header": current_header,
                            "level": current_header_level,
                            "content": joined_content,
                        })
                    current_header = title.strip()
                    current_header_level = level_num
                    current_chunk_lines = [line]
                    continue

        current_chunk_lines.append(line)

    joined_content = "\n".join(current_chunk_lines).strip()
    if joined_content:
        chunks.append({
            "header": current_header,
            "level": current_header_level,
            "content": joined_content,
        })

    return chunks


def _extract_tags(header: str, content: str, max_tags: int = 5) -> List[str]:
    """Extracts domain-agnostic lowercase tags from backticked terms and frequent keywords."""
    code_terms = re.findall(r"`([a-zA-Z][a-zA-Z0-9_\-]{1,24})`", content)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{2,24}\b", f"{header} {header} {content}")

    counts: Counter[str] = Counter()
    for term in code_terms:
        norm = term.lower().strip("-_")
        if len(norm) >= 3 and norm not in _STOPWORDS:
            counts[norm] += 3

    for word in words:
        norm = word.lower().strip("-")
        if len(norm) >= 3 and norm not in _STOPWORDS:
            counts[norm] += 1

    tags = [term for term, _ in counts.most_common(max_tags)]
    return tags if tags else ["general"]


def _infer_type(header: str, content: str) -> str:
    """Infers OKF category, prioritizing explicit cues in the header before scanning body text."""
    guide_kws = ("guide", "tutorial", "how-to", "install", "step", "configure", "setup", "initialize", "instruction", "manual")
    process_kws = ("process", "procedure", "workflow", "lifecycle", "incident", "trigger", "onboarding", "flowchart", "deployment", "protocol")
    reference_kws = ("schema", "table", "database", "key", "env", "credentials", "variables", "parameters", "config", "constants", "reference", "api")

    header_lower = header.lower()
    for target_text in (header_lower, f"{header_lower} {content.lower()}"):
        if any(kw in target_text for kw in guide_kws):
            return "guide"
        if any(kw in target_text for kw in process_kws):
            return "process"
        if any(kw in target_text for kw in reference_kws):
            return "reference"
    return "concept"


def smart_local_classify(header: str, content: str, idx: int) -> Dict[str, Any]:
    """
    Offline heuristic metadata generator.
    Infers OKF type, lead-paragraph description, domain-agnostic tags, and a safe filename slug.
    """
    inferred_type = _infer_type(header, content)

    clean_desc = re.sub(r"^#{1,6}\s+.*$", "", content, flags=re.MULTILINE)
    clean_desc = re.sub(r"```[\s\S]*?```", "", clean_desc)
    clean_desc = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean_desc)
    clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_desc) if len(s.strip()) > 5]
    if sentences:
        description = " ".join(sentences[:2])
        if len(description) > 180:
            description = description[:177] + "..."
    else:
        description = f"Documentation covering {header}."

    tags = _extract_tags(header, content)
    slug = sanitize_slug(header, fallback=f"concept-{idx}")

    return {
        "type": inferred_type,
        "title": header,
        "description": description,
        "tags": tags,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filename": slug,
    }
