import os
import argparse
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

# Initialize colorama for safe cross-platform Windows terminal color mapping
import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser import split_markdown
from src.metadata import extract_metadata
from src.linker import cross_link_concepts
from src.indexer import write_okf_bundle
from src.manifest import calculate_file_hash, load_manifest, save_manifest

# Styling Constants
C_BANNER = Fore.CYAN + Style.BRIGHT
C_STEP = Fore.MAGENTA + Style.BRIGHT
C_PROMPT = Fore.WHITE + Style.BRIGHT
C_SUCCESS = Fore.GREEN + Style.BRIGHT
C_WARNING = Fore.YELLOW + Style.BRIGHT
C_ERROR = Fore.RED + Style.BRIGHT
C_INFO = Fore.BLUE + Style.BRIGHT
C_FILE = Fore.CYAN
C_CHUNK = Fore.WHITE

def deduplicate_text(text: str) -> str:
    """
    Cleans up lines where the exact same heading or phrase is repeated back-to-back
    due to Word document TOC run duplicates (e.g., "1. System Overview1. System Overview").
    """
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            cleaned_lines.append(line)
            continue
            
        # Check if the line is exactly split into two identical halves
        mid = len(line_strip) // 2
        if len(line_strip) % 2 == 0:
            left, right = line_strip[:mid], line_strip[mid:]
            if left == right:
                # Retain original leading whitespace
                lead_space = line[:line.find(line_strip)]
                cleaned_lines.append(lead_space + left)
                continue
                
        # Also check with regex for generic back-to-back repeated phrases
        match = re.match(r'^(.{3,})\1$', line_strip)
        if match:
            lead_space = line[:line.find(line_strip)]
            cleaned_lines.append(lead_space + match.group(1))
            continue
            
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def read_input_file(filepath: str) -> str:
    """
    Reads the content of the file. If it is a PDF file, uses the custom layout-aware
    parser to reconstruct structural headers. If it is another Office document,
    uses Microsoft MarkItDown. Standard text/md is read directly.
    """
    _, ext = os.path.splitext(filepath.lower())
    if ext in (".md", ".markdown"):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    elif ext == ".pdf":
        from src.pdf_layout import parse_pdf_layout
        return parse_pdf_layout(filepath)
    elif ext in (".docx", ".xlsx", ".pptx", ".html", ".htm"):
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(filepath)
        raw_text = result.text_content
        return deduplicate_text(raw_text)
    else:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            "Supported formats are .md, .markdown, .pdf, .docx, .xlsx, .pptx, and .html."
        )

def print_summary_table(summary_list):
    """Prints a beautiful, highly professional ASCII table summarizing the ingestion run."""
    print("\n" + Fore.CYAN + Style.BRIGHT + "+" + "-" * 68 + "+")
    print(Fore.CYAN + Style.BRIGHT + "| " + Fore.WHITE + Style.BRIGHT + "OmniOKF Ingestion Summary".center(66) + Fore.CYAN + Style.BRIGHT + " |")
    print(Fore.CYAN + Style.BRIGHT + "+" + "-" * 30 + "+" + "-" * 10 + "+" + "-" * 10 + "+" + "-" * 14 + "+")
    print(Fore.CYAN + Style.BRIGHT + "| " + Fore.WHITE + "File Name".ljust(28) + 
          Fore.CYAN + "| " + Fore.WHITE + "Type".ljust(8) + 
          Fore.CYAN + "| " + Fore.WHITE + "Chunks".ljust(8) + 
          Fore.CYAN + "| " + Fore.WHITE + "Status".ljust(12) + 
          Fore.CYAN + " |")
    print(Fore.CYAN + Style.BRIGHT + "+" + "-" * 30 + "+" + "-" * 10 + "+" + "-" * 10 + "+" + "-" * 14 + "+")
    
    total_chunks = 0
    cached_chunks = 0
    
    for item in summary_list:
        name = item["name"]
        if len(name) > 26:
            name = name[:23] + "..."
        file_type = item["type"]
        chunks = item["chunks"]
        status = item["status"]
        
        if status == "Fresh":
            status_color = Fore.GREEN + Style.BRIGHT
        elif status == "Cached":
            status_color = Fore.BLUE
        else:
            status_color = Fore.RED + Style.BRIGHT
            
        print(Fore.CYAN + "| " + Fore.WHITE + name.ljust(28) + 
              Fore.CYAN + "| " + Fore.WHITE + file_type.ljust(8) + 
              Fore.CYAN + "| " + str(chunks).rjust(8) + " " + 
              Fore.CYAN + "| " + status_color + status.ljust(12) + 
              Fore.CYAN + " |")
              
        total_chunks += chunks
        if status == "Cached":
            cached_chunks += chunks
            
    print(Fore.CYAN + Style.BRIGHT + "+" + "-" * 30 + "+" + "-" * 10 + "+" + "-" * 10 + "+" + "-" * 14 + "+")
    
    cache_pct = int((cached_chunks / total_chunks) * 100) if total_chunks > 0 else 0
    summary_text = f"Total Concepts: {total_chunks} | Cached: {cache_pct}%"
    print(Fore.CYAN + Style.BRIGHT + "| " + Fore.WHITE + Style.BRIGHT + summary_text.center(66) + Fore.CYAN + Style.BRIGHT + " |")
    print(Fore.CYAN + Style.BRIGHT + "+" + "-" * 68 + "+\n")

def extract_metadata_with_retry(body: str, max_retries: int = 3) -> tuple:
    """
    Calls extract_metadata with exponential backoff and random jitter.
    Gracefully falls back to heuristic generation if rate limits are exhausted.
    """
    import time
    import random
    delay = 2.0  # starting delay of 2 seconds
    for attempt in range(max_retries):
        try:
            return extract_metadata(body)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str:
                jitter = random.uniform(0.5, 1.5)
                wait_time = delay * jitter
                time.sleep(wait_time)
                delay *= 2.0  # double the delay for the next attempt
            else:
                raise e
    raise RuntimeError("API retries exhausted.")

def run_compiler_pipeline(input_path: str, output_dir: str, split_level: str, api_key: str = None):
    """
    Core compilation pipeline that reads, parses, splits, metadata-extracts,
    cross-links, and indexes documents with clean, human-readable styled outputs.
    Supports incremental compilation (caching) via manifest hashes.
    """
    print("\n" + C_BANNER + "+" + "-" * 58 + "+")
    print(C_BANNER + "|  " + Style.BRIGHT + "OmniOKF Compilation Process" + " " * 29 + C_BANNER + "|")
    print(C_BANNER + "+" + "-" * 58 + "+")

    if not os.path.exists(input_path):
        print(C_ERROR + f"[-] Error: Input path '{input_path}' does not exist.")
        print(C_INFO + "    Suggestion: Check that you entered the path correctly.")
        return False
        
    supported_extensions = (".md", ".markdown", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm")
    input_files = []
    
    # 1. Gather all files
    if os.path.isdir(input_path):
        print(C_INFO + f"[Folder] " + C_CHUNK + f"Scanning directory: {input_path}")
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    input_files.append(os.path.abspath(os.path.join(root, file)))
        
        if not input_files:
            print(C_ERROR + f"[-] Error: No supported files {supported_extensions} found in '{input_path}'.")
            print(C_INFO + "    Suggestion: Ensure you placed documents in the directory, or verify folder permissions.")
            return False
    else:
        input_files.append(os.path.abspath(input_path))
        
    print(C_INFO + f"[Info] " + C_CHUNK + f"Found {len(input_files)} document file(s) to process.")
    if not api_key:
        print(C_WARNING + "[!] Running in Heuristic Fallback mode (no Gemini API key provided).")
    else:
        print(C_SUCCESS + "[LLM] API Key loaded. Generating custom metadata via Gemini...")

    # Load cache manifest
    manifest = load_manifest(output_dir)
    new_manifest = {}
    concepts = {}
    concept_idx = 1
    file_summary = []
    
    # Process files
    for filepath in input_files:
        filename = os.path.basename(filepath)
        _, ext = os.path.splitext(filepath.lower())
        file_type_label = ext[1:].upper()
        
        try:
            file_hash = calculate_file_hash(filepath)
        except Exception as e:
            print(C_ERROR + f"\n  [-] Error calculating hash for '{filename}': {e}")
            file_summary.append({
                "name": filename,
                "type": file_type_label,
                "chunks": 0,
                "status": "Failed"
            })
            continue
            
        # Check cache
        cached_entry = manifest.get(filepath)
        if cached_entry and cached_entry.get("hash") == file_hash:
            cached_concepts = cached_entry.get("concepts", [])
            for concept_data in cached_concepts:
                meta = concept_data["metadata"]
                
                # Check uniqueness of filename dynamically
                base_filename = meta["filename"]
                unique_filename = base_filename
                counter = 2
                existing_filenames = {c["metadata"]["filename"] for c in concepts.values()}
                while unique_filename in existing_filenames:
                    unique_filename = f"{base_filename}-{counter}"
                    counter += 1
                meta["filename"] = unique_filename
                
                concepts[f"chunk_{concept_idx}"] = {
                    "metadata": meta,
                    "content": concept_data["content"]
                }
                concept_idx += 1
                
            new_manifest[filepath] = cached_entry
            file_summary.append({
                "name": filename,
                "type": file_type_label,
                "chunks": len(cached_concepts),
                "status": "Cached"
            })
            continue
            
        # Parse document fresh
        try:
            content = read_input_file(filepath)
            file_chunks = split_markdown(content, split_level)
        except Exception as e:
            print(C_ERROR + f"\n  [-] Error converting document '{filename}': {e}")
            file_summary.append({
                "name": filename,
                "type": file_type_label,
                "chunks": 0,
                "status": "Failed"
            })
            continue
            
        file_concepts = []
        total_file_chunks = len(file_chunks)
        
        for idx, chunk in enumerate(file_chunks, 1):
            header = chunk["header"]
            body = chunk["content"]
            
            # Dynamic Progress Bar setup (updates in-place)
            percent = int((idx / total_file_chunks) * 100)
            bar_len = 25
            filled_len = int(bar_len * idx // total_file_chunks)
            bar = '=' * filled_len + '-' * (bar_len - filled_len)
            
            sys.stdout.write(
                f"\r{C_STEP}  [Process] {Fore.WHITE}[{bar}] {percent}% | {C_FILE}{filename[:15]} {C_CHUNK}-> {C_FILE}\"{header[:20]}...\""
            )
            sys.stdout.flush()
            
            meta = None
            cleaned_content = body
            
            if api_key:
                try:
                    os.environ["GEMINI_API_KEY"] = api_key
                    meta, cleaned_content = extract_metadata_with_retry(body)
                except Exception:
                    pass
                    
            # Fallback metadata
            if not meta:
                from src.parser import smart_local_classify
                meta = smart_local_classify(header, body, concept_idx)
                cleaned_content = body
                
            # Uniqueness check
            base_filename = meta["filename"]
            unique_filename = base_filename
            counter = 2
            existing_filenames = {c["metadata"]["filename"] for c in concepts.values()}
            while unique_filename in existing_filenames:
                unique_filename = f"{base_filename}-{counter}"
                counter += 1
            meta["filename"] = unique_filename
            
            concept_entry = {
                "metadata": meta,
                "content": cleaned_content
            }
            
            file_concepts.append(concept_entry)
            concepts[f"chunk_{concept_idx}"] = concept_entry
            concept_idx += 1
            
        # Clear progress line
        if file_chunks:
            sys.stdout.write("\r" + " " * 95 + "\r")
            sys.stdout.flush()
            
        new_manifest[filepath] = {
            "hash": file_hash,
            "concepts": file_concepts
        }
        file_summary.append({
            "name": filename,
            "type": file_type_label,
            "chunks": total_file_chunks,
            "status": "Fresh"
        })
        
    if not concepts:
        print(C_ERROR + "\n[-] Error: No concepts were successfully compiled.")
        return False
        
    print(C_STEP + "\n[Linker] " + C_CHUNK + "Establishing semantic cross-links...")
    linked_contents = cross_link_concepts(concepts)
    
    print(C_STEP + "[Save] " + C_CHUNK + f"Writing index catalog, graph, and category folders to: {output_dir}")
    try:
        write_okf_bundle(output_dir, concepts, linked_contents)
        save_manifest(output_dir, new_manifest)
    except Exception as e:
        print(C_ERROR + f"[-] Error writing output bundle: {e}")
        return False
        
    # Render final ingestion summary table
    print_summary_table(file_summary)
    
    print(C_SUCCESS + "+" + "-" * 58 + "+")
    print(C_SUCCESS + "|  " + Style.BRIGHT + "SUCCESS: OKF Compilation Complete!" + " " * 22 + C_SUCCESS + "|")
    print(C_SUCCESS + "+" + "-" * 58 + "+")
    print(C_SUCCESS + f"   Output Directory: " + Fore.WHITE + f"{os.path.abspath(output_dir)}")
    print(C_SUCCESS + f"   Master Catalog Index: " + Fore.WHITE + f"{os.path.join(output_dir, 'index.md')}")
    print(C_SUCCESS + "-" * 60 + "\n")
    return True

def interactive_mode():
    """
    Guides a non-technical user step-by-step through configuration and processing.
    Only asks for:
    1. Input path (file or folder).
    2. Gemini API key (if not present).
    Defaults output to '.okf' and split level to '##'.
    """
    load_dotenv()
    
    print(C_BANNER + "\n+" + "-" * 58 + "+")
    print(C_BANNER + "| " + Style.BRIGHT + "OmniOKF: The Universal Open Knowledge Format Compiler" + "   " + C_BANNER + "|")
    print(C_BANNER + "+" + "-" * 58 + "+")
    print(C_PROMPT + "   This guide will help you convert your documents to a structured bundle.")
    print(C_BANNER + "-" * 60)
    
    # 1. Ask for input path
    while True:
        print(C_STEP + "\n[1/2] Enter the path to your document file or folder:")
        input_path = input(C_PROMPT + "      > ").strip()
        input_path = input_path.strip('"\'')
        if not input_path:
            print(C_ERROR + "      [-] Input path cannot be empty.")
            continue
        if not os.path.exists(input_path):
            print(C_ERROR + f"      [-] Path '{input_path}' does not exist. Please check the spelling.")
            continue
        break
        
    # 2. Check for Gemini Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(C_WARNING + "\n[2/2] Gemini API Key was not detected in your configuration.")
        print(C_INFO + "      Note: Get a free API Key from Google AI Studio (https://aistudio.google.com/)")
        choice = input(C_PROMPT + "      Would you like to enter a key now to use LLM categorization? (yes/no):\n      > ").strip().lower()
        if choice in ("y", "yes"):
            api_key = input(C_PROMPT + "      Paste your GEMINI_API_KEY here:\n      > ").strip()
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                save_choice = input(C_PROMPT + "      Save this API Key in a .env file for future runs? (yes/no):\n      > ").strip().lower()
                if save_choice in ("y", "yes"):
                    try:
                        with open(".env", "w") as f:
                            f.write(f"GEMINI_API_KEY={api_key}\n")
                        print(C_SUCCESS + "      [+] Gemini API Key successfully saved to .env file.")
                    except Exception as e:
                        print(C_ERROR + f"      [!] Warning: Could not save key to .env file: {e}")
        else:
            print(C_WARNING + "      [!] Running in heuristic fallback mode (no LLM metadata extraction).")
    else:
        print(C_SUCCESS + "\n[2/2] Gemini API Key detected in environment configuration.")

    # Defaults for Output Folder & Split Level
    output_dir = ".okf"
    split_level = "##"
        
    # Launch pipeline
    run_compiler_pipeline(input_path, output_dir, split_level, api_key)

def main():
    # If no arguments are passed, launch interactive mode
    if len(sys.argv) == 1:
        interactive_mode()
        return

    # CLI mode using argparse
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="OmniOKF: The Universal Open Knowledge Format (OKF) Compiler. Transform PDFs, Office docs (DOCX, XLSX, PPTX), HTML, and Markdown into structured, cross-linked OKF directories."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input file (PDF, DOCX, XLSX, PPTX, HTML, MD) or directory containing them."
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=".okf",
        help="Directory where the OKF bundle will be created (default: .okf)"
    )
    parser.add_argument(
        "--split-level", "-s",
        default="##",
        help="Header prefix to split the document at (default: '##')"
    )
    
    args = parser.parse_args()
    api_key = os.environ.get("GEMINI_API_KEY")
    run_compiler_pipeline(args.input, args.output_dir, args.split_level, api_key)

if __name__ == "__main__":
    main()
