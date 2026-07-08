import os
import argparse
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser import split_markdown
from src.metadata import extract_metadata
from src.linker import cross_link_concepts
from src.indexer import write_okf_bundle

def read_input_file(filepath: str) -> str:
    """
    Reads the content of the file. If it is an Office document, PDF, or HTML file,
    converts it to Markdown using Microsoft's MarkItDown.
    Otherwise, reads it as a standard text file (for .md/.markdown).
    """
    _, ext = os.path.splitext(filepath.lower())
    if ext in (".md", ".markdown"):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    elif ext in (".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm"):
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(filepath)
        return result.text_content
    else:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            "Supported formats are .md, .markdown, .pdf, .docx, .xlsx, .pptx, and .html."
        )

def run_compiler_pipeline(input_path: str, output_dir: str, split_level: str, api_key: str = None):
    """
    Core compilation pipeline that reads, parses, splits, metadata-extracts,
    cross-links, and indexes documents with clean, human-readable status outputs.
    """
    print("\n" + "-" * 60)
    print(">>> Starting OmniOKF Compilation Pipeline...")
    print("-" * 60)

    if not os.path.exists(input_path):
        print(f"[-] Error: Input path '{input_path}' does not exist.")
        return False
        
    chunks = []
    supported_extensions = (".md", ".markdown", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm")
    
    if os.path.isdir(input_path):
        print(f"[Folder] Scanning directory: {input_path}")
        input_files = []
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    input_files.append(os.path.join(root, file))
        
        if not input_files:
            print(f"[-] Error: No supported files {supported_extensions} found in directory '{input_path}'.")
            return False
            
        print(f"[Info] Found {len(input_files)} document files. Processing...")
        for filepath in input_files:
            filename = os.path.basename(filepath)
            print(f"  [Parse] Reading & converting: {filename}")
            try:
                content = read_input_file(filepath)
                file_chunks = split_markdown(content, split_level)
                print(f"    [Split] Segmented into {len(file_chunks)} logical sections.")
                chunks.extend(file_chunks)
            except Exception as e:
                print(f"    [-] Error reading file: {e}")
    else:
        filename = os.path.basename(input_path)
        print(f"[Parse] Reading & converting file: {filename}")
        try:
            content = read_input_file(input_path)
            file_chunks = split_markdown(content, split_level)
            print(f"  [Split] Segmented into {len(file_chunks)} logical sections.")
            chunks.extend(file_chunks)
        except Exception as e:
            print(f"[-] Error reading file: {e}")
            return False
        
    total_chunks = len(chunks)
    if total_chunks == 0:
        print("[-] Error: No content sections found to process.")
        return False
        
    print(f"\n[Info] Total sections to process: {total_chunks}")
    if not api_key:
        print("[!] No Gemini API Key provided. Running in Heuristic Fallback mode.")
        print("    (Standard default metadata will be generated for your concepts.)")
    else:
        print("[LLM] LLM mode activated. Extracting semantic metadata via Gemini...")

    concepts = {}
    
    for idx, chunk in enumerate(chunks, 1):
        header = chunk["header"]
        content = chunk["content"]
        
        # Display clean progress line without emojis
        sys.stdout.write(f"\r[LLM] Processing section {idx}/{total_chunks}: \"{header[:35]}...\"")
        sys.stdout.flush()
        
        meta = None
        cleaned_content = content
        
        if api_key:
            try:
                os.environ["GEMINI_API_KEY"] = api_key
                meta, cleaned_content = extract_metadata(content)
            except Exception:
                pass
                
        # Heuristic Fallback
        if not meta:
            slug = re.sub(r'[^a-z0-9\-]', '', header.lower().replace(' ', '-').replace('_', '-'))
            slug = slug.strip('-')
            if not slug:
                slug = f"concept-{idx}"
                
            meta = {
                "type": "concept",
                "title": header,
                "description": f"Section covering: {header}.",
                "tags": ["uncategorized"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "filename": slug
            }
            cleaned_content = content
            
        # Ensure filename uniqueness across all loaded files/chunks
        base_filename = meta["filename"]
        unique_filename = base_filename
        counter = 2
        existing_filenames = {c["metadata"]["filename"] for c in concepts.values()}
        while unique_filename in existing_filenames:
            unique_filename = f"{base_filename}-{counter}"
            counter += 1
        meta["filename"] = unique_filename
        
        concepts[f"chunk_{idx}"] = {
            "metadata": meta,
            "content": cleaned_content
        }
        
    print("\n   [+] Concept structuring completed.")
    
    print("[Linker] Establishing semantic cross-links...")
    linked_contents = cross_link_concepts(concepts)
    
    print(f"[Save] Writing index catalog and category folders to: {output_dir}")
    write_okf_bundle(output_dir, concepts, linked_contents)
    
    print("\n[SUCCESS] OKF Compilation complete!")
    print(f"   [+] Output Directory: {os.path.abspath(output_dir)}")
    print(f"   [+] Master Catalog index: {os.path.join(output_dir, 'index.md')}")
    print("-" * 60 + "\n")
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
    
    print("=" * 60)
    print("*** Welcome to OmniOKF: The Universal OKF Compiler! ***")
    print("This guide will help you convert your documents to a structured bundle.")
    print("=" * 60)
    
    # 1. Ask for input path
    while True:
        input_path = input("\n[1/2] Enter the path to your document file or folder:\n> ").strip()
        input_path = input_path.strip('"\'')
        if not input_path:
            print("[-] Input path cannot be empty.")
            continue
        if not os.path.exists(input_path):
            print(f"[-] Path '{input_path}' does not exist. Please check the spelling.")
            continue
        break
        
    # 2. Check for Gemini Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[2/2] Gemini API Key was not detected.")
        print("Note: You can get a free API Key from Google AI Studio (https://aistudio.google.com/)")
        choice = input("Would you like to enter your Gemini API Key now to use LLM categorization? (yes/no):\n> ").strip().lower()
        if choice in ("y", "yes"):
            api_key = input("Paste your GEMINI_API_KEY here:\n> ").strip()
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                save_choice = input("Save this API Key in a .env file for future runs? (yes/no):\n> ").strip().lower()
                if save_choice in ("y", "yes"):
                    try:
                        with open(".env", "w") as f:
                            f.write(f"GEMINI_API_KEY={api_key}\n")
                        print("[+] Gemini API Key successfully saved to .env file.")
                    except Exception as e:
                        print(f"[!] Warning: Could not save key to .env file: {e}")
        else:
            print("[!] Running in heuristic fallback mode (no LLM metadata extraction).")
    else:
        print("\n[2/2] Gemini API Key detected in environment configuration.")

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
