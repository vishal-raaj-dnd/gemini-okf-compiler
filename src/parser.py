import re
from typing import List, Dict, Any

def split_markdown(content: str, split_level: str = "##") -> List[Dict[str, Any]]:
    """
    Heuristically splits a flat markdown string into sections based on headers.
    It splits at any header that matches the split_level (e.g., '##') or a higher level (e.g., '#').
    
    Args:
        content: The raw markdown text.
        split_level: The header token to split on (typically '##' or '#').
        
    Returns:
        A list of dictionaries containing 'header', 'level', and 'content' for each chunk.
    """
    # Regex to detect headers: ^(#{1,6})\s+(.*)$
    header_regex = re.compile(r"^(#{1,6})\s+(.+)$")
    
    # Calculate the numeric level target based on split_level string
    split_level_num = len(split_level.strip())
    
    lines = content.splitlines()
    chunks = []
    
    current_header = "Introduction"
    current_header_level = 1
    current_chunk_lines = []
    
    for line in lines:
        match = header_regex.match(line.strip())
        if match:
            level_str, title = match.groups()
            level_num = len(level_str)
            
            # If we see a header that is at or above the split level (e.g., 1 or 2), we slice here.
            if level_num <= split_level_num:
                # Save previous chunk if it has content
                joined_content = "\n".join(current_chunk_lines).strip()
                if joined_content or current_chunk_lines:
                    chunks.append({
                        "header": current_header,
                        "level": current_header_level,
                        "content": joined_content
                    })
                
                # Reset for the new chunk
                current_header = title.strip()
                current_header_level = level_num
                current_chunk_lines = [line]  # include the header line in the chunk
                continue
        
        current_chunk_lines.append(line)
        
    # Append the last chunk
    joined_content = "\n".join(current_chunk_lines).strip()
    if joined_content or current_chunk_lines:
        chunks.append({
            "header": current_header,
            "level": current_header_level,
            "content": joined_content
        })
        
    return chunks
