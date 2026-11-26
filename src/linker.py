import math
import re
from typing import Any, Dict, List

_STOPWORDS = frozenset({
    "plan", "view", "show", "step", "guide", "concept",
    "process", "overview", "stack", "tools", "schema",
})

_TF_IDF_THRESHOLD = 0.008
_MAX_LINKS_PER_DOC = 4


def get_relative_path(source_type: str, target_type: str, target_filename: str) -> str:
    """Computes the relative markdown link path from a source category folder to a target file."""
    if source_type == target_type:
        return f"./{target_filename}.md"
    return f"../{target_type}/{target_filename}.md"


def get_link_keywords(title: str) -> List[str]:
    """Generates candidate search phrases from a concept title, stripping numbering and parentheticals."""
    keywords = [title]

    cleaned_num = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", title)
    if cleaned_num != title:
        keywords.append(cleaned_num)

    cleaned_paren = re.sub(r"\s*\([^)]*\)\s*$", "", title)
    if cleaned_paren != title:
        keywords.append(cleaned_paren)

    cleaned_both = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned_num)
    if cleaned_both not in keywords:
        keywords.append(cleaned_both)

    valid_keywords = []
    for kw in keywords:
        kw_strip = kw.strip()
        if len(kw_strip) >= 4 and kw_strip.lower() not in _STOPWORDS:
            valid_keywords.append(kw_strip)

    return sorted(set(valid_keywords), key=len, reverse=True)


def cross_link_concepts(concepts: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Auto-links concepts using TF-IDF relevance scoring.
    Preserves fenced code blocks, inline code, headings, images, and existing markdown links.
    """
    total_docs = len(concepts)
    if total_docs == 0:
        return {}

    targets_info = []
    for target_id, target in concepts.items():
        target_meta = target["metadata"]
        targets_info.append({
            "id": target_id,
            "title": target_meta["title"],
            "type": target_meta["type"],
            "filename": target_meta["filename"],
            "keywords": get_link_keywords(target_meta["title"]),
        })

    keyword_df: Dict[str, int] = {}
    for target in targets_info:
        for kw in target["keywords"]:
            if kw in keyword_df:
                continue
            kw_pattern = re.compile(rf"\b{re.escape(kw.lower())}\b")
            keyword_df[kw] = sum(
                1 for doc in concepts.values() if kw_pattern.search(doc["content"].lower())
            )

    doc_word_counts = {
        cid: max(len(re.findall(r"\w+", doc["content"].lower())), 1)
        for cid, doc in concepts.items()
    }

    updated_contents: Dict[str, str] = {}

    for source_id, concept_data in concepts.items():
        content = concept_data["content"]
        source_type = concept_data["metadata"]["type"]
        doc_words_len = doc_word_counts[source_id]

        scored_links = []
        for target in targets_info:
            if target["id"] == source_id:
                continue

            for kw in target["keywords"]:
                kw_matches = len(re.findall(rf"\b{re.escape(kw.lower())}\b", content.lower()))
                if kw_matches == 0:
                    continue

                tf = kw_matches / doc_words_len
                df = keyword_df.get(kw, 1)
                idf = math.log(1 + (total_docs / (1 + df)))
                tfidf = tf * idf
                is_exact = kw.lower() == target["title"].lower()

                scored_links.append({
                    "keyword": kw,
                    "target_type": target["type"],
                    "target_filename": target["filename"],
                    "tfidf": tfidf,
                    "is_exact": is_exact,
                })

        scored_links.sort(key=lambda item: (item["is_exact"], item["tfidf"]), reverse=True)

        active_links = []
        seen_targets = set()
        for link in scored_links:
            target_key = f"{link['target_type']}/{link['target_filename']}"
            if target_key in seen_targets:
                continue
            if link["is_exact"] or link["tfidf"] >= _TF_IDF_THRESHOLD:
                active_links.append(link)
                seen_targets.add(target_key)
                if len(active_links) >= _MAX_LINKS_PER_DOC:
                    break

        active_links.sort(key=lambda item: len(item["keyword"]), reverse=True)

        for link in active_links:
            kw = link["keyword"]
            rel_path = get_relative_path(source_type, link["target_type"], link["target_filename"])
            prefix = r"\b" if re.match(r"^\w", kw) else ""
            suffix = r"\b" if re.search(r"\w$", kw) else ""

            # Group 1: protected regions (code fences, inline code, headings, images, existing links)
            # Group 2: target keyword outside protected regions
            pattern = re.compile(
                rf"(```[\s\S]*?```|`[^`\n]+`|^#{{1,6}}\s+.*$|!?\[[^\]]*\]\([^\)]*\))|({prefix}{re.escape(kw)}{suffix})",
                re.IGNORECASE | re.MULTILINE,
            )

            def _replace(match: re.Match[str], target_path: str = rel_path) -> str:
                if match.group(1) is not None:
                    return match.group(1)
                return f"[{match.group(2)}]({target_path})"

            content = pattern.sub(_replace, content)

        updated_contents[source_id] = content

    return updated_contents
