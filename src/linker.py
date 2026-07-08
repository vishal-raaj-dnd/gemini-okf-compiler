import re
import os
from typing import Dict, Any

def get_relative_path(source_type: str, target_type: str, target_filename: str) -> str:
    """
    Computes the relative markdown link path from a source category folder
    to a target category file.
    
    Example:
        source_type='processes', target_type='guides', target_filename='onboarding'
        returns '../guides/onboarding.md'
    """
    if source_type == target_type:
        return f"./{target_filename}.md"
    else:
        return f"../{target_type}/{target_filename}.md"

def cross_link_concepts(concepts: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Performs auto-linking of concepts.
    Scans each concept's body content for references to other concept titles
    and automatically replaces them with standard Markdown relative links.
    
    Args:
        concepts: A dict of {concept_id: {'metadata': dict, 'content': str}}
        
    Returns:
        A dict of {concept_id: modified_content}
    """
    # Sort target concepts by title length descending to match longer titles first
    sorted_targets = sorted(
        concepts.values(),
        key=lambda x: len(x["metadata"]["title"]),
        reverse=True
    )
    
    updated_contents = {}
    
    for concept_id, concept_data in concepts.items():
        content = concept_data["content"]
        source_meta = concept_data["metadata"]
        source_type = source_meta["type"]
        source_title = source_meta["title"]
        
        for target in sorted_targets:
            target_meta = target["metadata"]
            target_title = target_meta["title"]
            target_type = target_meta["type"]
            target_filename = target_meta["filename"]
            
            # Avoid self-linking
            if target_title.lower() == source_title.lower():
                continue
                
            # Compute relative path from source file's directory to target file's directory
            rel_path = get_relative_path(source_type, target_type, target_filename)
            
            # Regex pattern to match the phrase, but skip it if it is inside an existing markdown link [like this](path)
            # Group 1: existing markdown links
            # Group 2: the target title as a separate word
            pattern = re.compile(
                rf"(\[.*?\]\(.*?\))|(\b{re.escape(target_title)}\b)",
                re.IGNORECASE
            )
            
            def replace_callback(match):
                if match.group(1):
                    # It's an existing link, return it as-is
                    return match.group(1)
                else:
                    # It's the keyword, wrap in a markdown link
                    matched_text = match.group(2)
                    return f"[{matched_text}]({rel_path})"
                    
            content = pattern.sub(replace_callback, content)
            
        updated_contents[concept_id] = content
        
    return updated_contents
