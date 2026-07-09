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

def smart_local_classify(header: str, content: str, idx: int) -> dict:
    """
    Performs robust offline metadata generation, mimicking an LLM classifier.
    Extracts type classification, lead-sentence descriptions, and taxonomy tags.
    """
    text_lower = (header + " " + content).lower()
    
    # 1. Infer OKF Type Category
    inferred_type = "concept"
    
    guide_kws = ["guide", "tutorial", "how-to", "install", "step", "configure", "setup", "initialize", "instruction", "manual"]
    process_kws = ["process", "procedure", "workflow", "lifecycle", "incident", "trigger", "onboarding", "flowchart", "deployment", "protocol"]
    reference_kws = ["schema", "table", "database", "key", "env", "credentials", "variables", "parameters", "config", "constants", "reference"]
    
    if any(kw in text_lower for kw in reference_kws):
        inferred_type = "reference"
    elif any(kw in text_lower for kw in process_kws):
        inferred_type = "process"
    elif any(kw in text_lower for kw in guide_kws):
        inferred_type = "guide"
        
    # 2. Extract Lead-Paragraph Description (Cleaned of Markdown formatting)
    # Remove markdown headers and code blocks from description text
    clean_desc = re.sub(r'^(#+)\s+.*$', '', content, flags=re.MULTILINE)
    clean_desc = re.sub(r'```.*?```', '', clean_desc, flags=re.DOTALL)
    clean_desc = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_desc)  # clean links
    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
    
    # Take first two sentences
    sentences = re.split(r'(?<=[.!?])\s+', clean_desc)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    
    if sentences:
        description = " ".join(sentences[:2])
        if len(description) > 180:
            description = description[:177] + "..."
    else:
        description = f"Documentation covering parameters and specifications for {header}."
        
    # 3. Taxonomy Tag Scanning
    taxonomy = [
        "redis", "celery", "postgres", "sqlite", "drizzle", "groq", "llama", "twilio", 
        "whatsapp", "supabase", "ssl", "webhook", "aws", "docker", "python", "javascript", 
        "react", "html", "css", "flask", "django", "fastapi", "rag", "embedding", "security"
    ]
    
    tags = []
    for term in taxonomy:
        # Match as whole word boundary to prevent partial matches like 'as' in 'flask'
        if re.search(rf"\b{term}\b", text_lower):
            tags.append(term)
            
    if not tags:
        tags = ["general"]
        
    # Create clean file slug
    slug = re.sub(r'[^a-z0-9\-]', '', header.lower().replace(' ', '-').replace('_', '-'))
    slug = slug.strip('-')
    if not slug:
        slug = f"concept-{idx}"
        
    from datetime import datetime
    return {
        "type": inferred_type,
        "title": header,
        "description": description,
        "tags": tags,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "filename": slug
    }
