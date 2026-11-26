from collections import Counter
from typing import Dict, List, Tuple

import fitz  # PyMuPDF


def _find_matching_style(
    bbox: Tuple[float, float, float, float],
    dict_blocks: List[Tuple[Tuple[float, float, float, float], Dict[str, object]]],
    default_size: float,
) -> Dict[str, object]:
    """Finds the best-matching dict block style for a text block using coordinate tolerance and overlap."""
    x0, y0, x1, y1 = bbox
    best_style: Dict[str, object] | None = None
    best_overlap = 0.0

    for db_bbox, style in dict_blocks:
        dx0, dy0, dx1, dy1 = db_bbox
        if abs(x0 - dx0) <= 2.0 and abs(y0 - dy0) <= 2.0 and abs(x1 - dx1) <= 2.0 and abs(y1 - dy1) <= 2.0:
            return style

        ix0 = max(x0, dx0)
        iy0 = max(y0, dy0)
        ix1 = min(x1, dx1)
        iy1 = min(y1, dy1)
        if ix1 > ix0 and iy1 > iy0:
            overlap = (ix1 - ix0) * (iy1 - iy0)
            if overlap > best_overlap:
                best_overlap = overlap
                best_style = style

    return best_style if best_style is not None else {"size": default_size, "bold": False}


def parse_pdf_layout(filepath: str) -> str:
    """
    Parses a PDF using PyMuPDF (fitz) and reconstructs structured Markdown text.
    Infers header levels (#, ##, ###) dynamically from relative font sizes and bold styling.
    Falls back to MarkItDown for scanned/image-only PDFs.
    """
    doc = fitz.open(filepath)
    try:
        all_sizes: List[float] = []
        for page in doc:
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if len(text) > 3:
                            all_sizes.append(round(span["size"], 1))

        if not all_sizes:
            body_font_size = 10.0
        else:
            body_font_size = Counter(all_sizes).most_common(1)[0][0]

        h1_ratio = 1.45
        h2_ratio = 1.25
        h3_ratio = 1.10
        markdown_lines: List[str] = []

        for page in doc:
            blocks = page.get_text("blocks")
            raw_dict_blocks = page.get_text("dict").get("blocks", [])
            dict_styles: List[Tuple[Tuple[float, float, float, float], Dict[str, object]]] = []

            for db in raw_dict_blocks:
                if "lines" not in db:
                    continue
                max_size = 0.0
                is_bold = False
                for line in db["lines"]:
                    for span in line["spans"]:
                        if span["text"].strip():
                            max_size = max(max_size, float(span["size"]))
                            font_name = span["font"].lower()
                            if "bold" in font_name or "black" in font_name or (span["flags"] & 16):
                                is_bold = True
                db_bbox = (
                    float(db["bbox"][0]),
                    float(db["bbox"][1]),
                    float(db["bbox"][2]),
                    float(db["bbox"][3]),
                )
                dict_styles.append((db_bbox, {"size": max_size, "bold": is_bold}))

            for block in blocks:
                if len(block) < 7 or block[6] != 0:
                    continue

                x0, y0, x1, y1, text, _, _ = block
                text_strip = text.strip()
                if not text_strip:
                    continue

                style = _find_matching_style((float(x0), float(y0), float(x1), float(y1)), dict_styles, body_font_size)
                size = float(style["size"])
                bold = bool(style["bold"])

                if len(text_strip.split()) < 15 and (size >= body_font_size * h3_ratio or bold):
                    clean_text = text_strip.replace("\n", " ").strip()
                    if size >= body_font_size * h1_ratio:
                        markdown_lines.append(f"# {clean_text}\n")
                    elif size >= body_font_size * h2_ratio:
                        markdown_lines.append(f"## {clean_text}\n")
                    else:
                        markdown_lines.append(f"### {clean_text}\n")
                else:
                    markdown_lines.append(text_strip + "\n")
    finally:
        doc.close()

    reconstructed_md = "\n".join(markdown_lines).strip()

    if len(reconstructed_md) < 100:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(filepath)
        fallback_text = result.text_content
        if fallback_text and fallback_text.strip():
            return fallback_text

    return reconstructed_md
