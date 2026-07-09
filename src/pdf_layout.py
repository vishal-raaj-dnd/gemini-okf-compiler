import os
import fitz  # PyMuPDF
import re
from collections import Counter
from typing import List, Dict, Any

def parse_pdf_layout(filepath: str) -> str:
    """
    Parses a PDF using PyMuPDF (fitz) and reconstructs structured Markdown text.
    Infers header structures (# and ##) dynamically by analyzing relative font sizing
    and bold styling to ensure compatibility across all document layouts.
    
    If the PDF is detected to be a scanned, image-only document (text length is 0),
    falls back to Microsoft MarkItDown which can attempt OCR conversions.
    """
    doc = fitz.open(filepath)
    
    # Pass 1: Collect all font sizes across the document to determine the base body font size (mode)
    all_sizes = []
    for page in doc:
        blocks = page.get_text("dict").get("blocks", [])
        for b in blocks:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if len(text) > 3:  # Only count actual content words
                        all_sizes.append(round(span["size"], 1))
                        
    if not all_sizes:
        body_font_size = 10.0  # Safe default if no text was found
    else:
        # Compute the statistical mode (most common size)
        size_counts = Counter(all_sizes)
        body_font_size = size_counts.most_common(1)[0][0]
        
    # Standard threshold offsets relative to body font size
    H1_RATIO = 1.45  # 1.45x body size for Title/Header 1
    H2_RATIO = 1.25  # 1.25x body size for Header 2
    H3_RATIO = 1.10  # 1.10x body size for Header 3
    
    markdown_lines = []
    
    # Pass 2: Reconstruct structured markdown based on relative style definitions
    for page_num, page in enumerate(doc):
        # Extract blocks sorted by reading order layout (top-to-bottom, left-to-right)
        blocks = page.get_text("blocks")
        
        # Read raw dictionary blocks for styling metadata matching block coordinates
        dict_blocks = page.get_text("dict").get("blocks", [])
        coordinate_styles = {}
        for db in dict_blocks:
            if "lines" not in db:
                continue
            # Store the largest/boldest span details in this block
            max_size = 0.0
            is_bold = False
            for line in db["lines"]:
                for span in line["spans"]:
                    span_text = span["text"].strip()
                    if span_text:
                        size = span["size"]
                        if size > max_size:
                            max_size = size
                        # Check bold flags (2^4 bit in PyMuPDF flags represents bold font,
                        # or check font name string for common bold identifiers)
                        font_name = span["font"].lower()
                        if "bold" in font_name or "black" in font_name or (span["flags"] & 16):
                            is_bold = True
            
            # Map block coordinates to styling (using bbox rounding to prevent float discrepancies)
            bbox = (round(db["bbox"][0], 1), round(db["bbox"][1], 1), round(db["bbox"][2], 1), round(db["bbox"][3], 1))
            coordinate_styles[bbox] = {"size": max_size, "bold": is_bold}
            
        for b in blocks:
            # We only process text blocks (block_type 0)
            if len(b) < 7 or b[6] != 0:
                continue
                
            x0, y0, x1, y1, text, block_no, block_type = b
            text_strip = text.strip()
            if not text_strip:
                continue
                
            # Find matching block styling by rounding bbox coordinates
            bbox = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
            style = coordinate_styles.get(bbox, {"size": body_font_size, "bold": False})
            
            size = style["size"]
            bold = style["bold"]
            
            # If the block consists of only a few words and is styled like a heading
            word_count = len(text_strip.split())
            
            # Heading Inference Engine
            if word_count < 15 and (size >= body_font_size * H3_RATIO or bold):
                clean_text = text_strip.replace("\n", " ").strip()
                # Determine markdown heading level relative to baseline body size
                if size >= body_font_size * H1_RATIO:
                    markdown_lines.append(f"# {clean_text}\n")
                elif size >= body_font_size * H2_RATIO:
                    markdown_lines.append(f"## {clean_text}\n")
                else:
                    markdown_lines.append(f"## {clean_text}\n")
            else:
                # Maintain standard block text
                markdown_lines.append(text_strip + "\n")
                
    doc.close()
    
    reconstructed_md = "\n".join(markdown_lines).strip()
    
    # 3. Scanned PDF Check & Fallback
    # If the layout-aware text extraction returns no content (image-only PDF),
    # fallback to Microsoft MarkItDown which can invoke local OCR pipelines if available.
    if len(reconstructed_md) < 100:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(filepath)
            fallback_text = result.text_content
            if len(fallback_text.strip()) > 0:
                return fallback_text
        except Exception:
            pass
            
    return reconstructed_md
