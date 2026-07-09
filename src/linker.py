import re
import os
from typing import Dict, Any, List

def get_relative_path(source_type: str, target_type: str, target_filename: str) -> str:
    """
    Computes the relative markdown link path from a source category folder
    to a target category file.
    """
    if source_type == target_type:
        return f"./{target_filename}.md"
    else:
        return f"../{target_type}/{target_filename}.md"

def get_link_keywords(title: str) -> List[str]:
    """
    Generates alternative search keywords/phrases from a concept title.
    Strips leading numbers and trailing parentheticals.
    
    Example:
        "3.2 Celery (Async Task Worker)" -> ["3.2 Celery (Async Task Worker)", "Celery", "Celery (Async Task Worker)"]
    """
    keywords = [title]
    
    # 1. Strip leading numbering (e.g., "3.1.2 ", "1. ")
    cleaned_num = re.sub(r'^\d+(?:\.\d+)*\.?\s+', '', title)
    if cleaned_num != title:
        keywords.append(cleaned_num)
        
    # 2. Strip trailing parentheticals (e.g., " (Webhook Receiver)")
    cleaned_paren = re.sub(r'\s*\([^)]*\)\s*$', '', title)
    if cleaned_paren != title:
        keywords.append(cleaned_paren)
        
    # 3. Strip both numbering and parentheticals
    cleaned_both = re.sub(r'\s*\([^)]*\)\s*$', '', cleaned_num)
    if cleaned_both not in keywords:
        keywords.append(cleaned_both)
        
    # Filter keywords: must be longer than 3 characters and not common generic words
    valid_keywords = []
    stopwords = {"plan", "view", "show", "step", "guide", "concept", "process", "overview", "stack", "tools", "schema"}
    
    for kw in keywords:
        kw_strip = kw.strip()
        if len(kw_strip) >= 4 and kw_strip.lower() not in stopwords:
            valid_keywords.append(kw_strip)
            
    # Sort keywords by length descending to match longer phrases first
    return sorted(list(set(valid_keywords)), key=len, reverse=True)

def cross_link_concepts(concepts: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Performs robust auto-linking of concepts.
    Scans each concept's body content for references to target concept titles
    or their clean keywords (e.g., "Flask" -> "3.1 Flask (Webhook Receiver)")
    and automatically replaces them with standard Markdown relative links.
    """
    # Pre-generate keywords and target info for each target concept
    targets_info = []
    for target in concepts.values():
        target_meta = target["metadata"]
        target_title = target_meta["title"]
        target_type = target_meta["type"]
        target_filename = target_meta["filename"]
        
        # Generate match keywords (e.g. "Flask", "Celery", etc.)
        keywords = get_link_keywords(target_title)
        
        targets_info.append({
            "title": target_title,
            "type": target_type,
            "filename": target_filename,
            "keywords": keywords
        })
        
    # Sort overall targets by the length of their longest keyword to prevent partial matches
    targets_info.sort(
        key=lambda x: len(x["keywords"][0]) if x["keywords"] else len(x["title"]),
        reverse=True
    )
    
    updated_contents = {}
    
    for concept_id, concept_data in concepts.items():
        content = concept_data["content"]
        source_meta = concept_data["metadata"]
        source_type = source_meta["type"]
        source_title = source_meta["title"]
        
        for target in targets_info:
            target_title = target["title"]
            target_type = target["type"]
            target_filename = target["filename"]
            target_keywords = target["keywords"]
            
            # Avoid self-linking
            if target_title.lower() == source_title.lower():
                continue
                
            rel_path = get_relative_path(source_type, target_type, target_filename)
            
            # Match each keyword for this target
            for kw in target_keywords:
                # Add word boundary only if keyword starts/ends with alphanumeric characters
                prefix = r"\b" if re.match(r"^\w", kw) else ""
                suffix = r"\b" if re.search(r"\w$", kw) else ""
                
                # Group 1: Matches existing markdown links [text](url) - return as is
                # Group 2: Matches the keyword with word boundaries - wraps in a markdown link
                pattern = re.compile(
                    rf"(\[.*?\]\(.*?\))|({prefix}{re.escape(kw)}{suffix})",
                    re.IGNORECASE
                )
                
                def replace_callback(match):
                    if match.group(1):
                        return match.group(1)
                    else:
                        matched_text = match.group(2)
                        return f"[{matched_text}]({rel_path})"
                        
                content = pattern.sub(replace_callback, content)
                
        updated_contents[concept_id] = content
        
    return updated_contents
