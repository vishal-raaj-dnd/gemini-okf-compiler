import re
import os
import math
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
            
    return sorted(list(set(valid_keywords)), key=len, reverse=True)

def cross_link_concepts(concepts: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Performs robust auto-linking of concepts.
    Uses a dynamic TF-IDF relevance calculation to ensure that alternative keywords
    (like 'Flask') are only turned into links in documents where they are highly relevant,
    preventing keyword link scaling collisions in large enterprise databases.
    """
    # 1. Pre-generate keyword maps
    targets_info = []
    for target_id, target in concepts.items():
        target_meta = target["metadata"]
        target_title = target_meta["title"]
        target_type = target_meta["type"]
        target_filename = target_meta["filename"]
        
        keywords = get_link_keywords(target_title)
        
        targets_info.append({
            "id": target_id,
            "title": target_title,
            "type": target_type,
            "filename": target_filename,
            "keywords": keywords
        })
        
    N = len(concepts)
    if N == 0:
        return {}
        
    # 2. Pre-calculate Document Frequency (DF) for each keyword
    # DF = number of documents containing the keyword (case-insensitive)
    keyword_df = {}
    for target in targets_info:
        for kw in target["keywords"]:
            df_count = 0
            for doc in concepts.values():
                if re.search(rf"\b{re.escape(kw.lower())}\b", doc["content"].lower()):
                    df_count += 1
            keyword_df[kw] = df_count
            
    # 3. Calculate TF-IDF for all potential links in each document
    # Also count word lengths in each document
    doc_word_counts = {}
    for cid, doc in concepts.items():
        words = re.findall(r"\w+", doc["content"].lower())
        doc_word_counts[cid] = max(len(words), 1)  # avoid division by 0
        
    updated_contents = {}
    
    for source_id, concept_data in concepts.items():
        content = concept_data["content"]
        source_meta = concept_data["metadata"]
        source_type = source_meta["type"]
        source_title = source_meta["title"]
        
        doc_words_len = doc_word_counts[source_id]
        
        # We will collect all potential keyword link matches in this document and score them
        scored_links = []
        
        for target in targets_info:
            target_id = target["id"]
            # Avoid self-linking
            if target_id == source_id:
                continue
                
            target_title = target["title"]
            target_type = target["type"]
            target_filename = target["filename"]
            target_keywords = target["keywords"]
            
            for kw in target_keywords:
                # Count raw occurrences of this keyword in the document
                kw_matches = len(re.findall(rf"\b{re.escape(kw.lower())}\b", content.lower()))
                if kw_matches == 0:
                    continue
                    
                # TF-IDF Calculation
                tf = kw_matches / doc_words_len
                df = keyword_df.get(kw, 1)
                idf = math.log(1 + (N / (1 + df)))
                tfidf = tf * idf
                
                # Check if it's an exact title match (always highly relevant)
                is_exact = kw.lower() == target_title.lower()
                
                scored_links.append({
                    "keyword": kw,
                    "target_title": target_title,
                    "target_type": target_type,
                    "target_filename": target_filename,
                    "tfidf": tfidf,
                    "is_exact": is_exact
                })
                
        # To avoid link scaling collisions, we sort the candidate links:
        # 1. Exact title matches are prioritised.
        # 2. Then sort by TF-IDF score descending.
        scored_links.sort(key=lambda x: (x["is_exact"], x["tfidf"]), reverse=True)
        
        # Enforce threshold and limit maximum links per document to 4
        active_links = []
        seen_targets = set()
        
        TF_IDF_THRESHOLD = 0.008
        MAX_LINKS_PER_DOC = 4
        
        for link in scored_links:
            target_key = f"{link['target_type']}/{link['target_filename']}"
            if target_key in seen_targets:
                continue
                
            # Filter: must exceed relevance threshold OR be an exact title match
            if link["is_exact"] or link["tfidf"] >= TF_IDF_THRESHOLD:
                active_links.append(link)
                seen_targets.add(target_key)
                if len(active_links) >= MAX_LINKS_PER_DOC:
                    break
                    
        # Apply the active links (ordered longest keyword first to prevent partial matches)
        active_links.sort(key=lambda x: len(x["keyword"]), reverse=True)
        
        for link in active_links:
            kw = link["keyword"]
            target_type = link["target_type"]
            target_filename = link["target_filename"]
            
            rel_path = get_relative_path(source_type, target_type, target_filename)
            
            # Match boundary only if keyword starts/ends with alphanumeric characters
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
            
        updated_contents[source_id] = content
        
    return updated_contents
