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
    cross-links, and indexes documents with clean, human-readable styled outputs.
    """
    print("\n" + C_BANNER + "┌" + "─" * 58 + "┐")
    print(C_BANNER + "│  " + Style.BRIGHT + "OmniOKF Compilation Process" + " " * 29 + C_BANNER + "│")
    print(C_BANNER + "└" + "─" * 58 + "┘")

    if not os.path.exists(input_path):
        print(C_ERROR + f"[-] Error: Input path '{input_path}' does not exist.")
        return False
        
    chunks = []
    supported_extensions = (".md", ".markdown", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm")
    
    if os.path.isdir(input_path):
        print(C_INFO + f"[Folder] " + C_CHUNK + f"Scanning directory: {input_path}")
        input_files = []
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    input_files.append(os.path.join(root, file))
        
        if not input_files:
            print(C_ERROR + f"[-] Error: No supported files {supported_extensions} found in '{input_path}'.")
            return False
            
        print(C_INFO + f"[Info] " + C_CHUNK + f"Found {len(input_files)} document files. Compiling...")
        for filepath in input_files:
            filename = os.path.basename(filepath)
            print(C_STEP + f"  [Parse] " + C_FILE + f"Reading & converting: {filename}")
            try:
                content = read_input_file(filepath)
                file_chunks = split_markdown(content, split_level)
                print(C_SUCCESS + f"    [Split] " + C_CHUNK + f"Segmented into {len(file_chunks)} logical sections.")
                chunks.extend(file_chunks)
            except Exception as e:
                print(C_ERROR + f"    [-] Error reading file: {e}")
    else:
        filename = os.path.basename(input_path)
        print(C_STEP + f"[Parse] " + C_FILE + f"Reading & converting file: {filename}")
        try:
            content = read_input_file(input_path)
            file_chunks = split_markdown(content, split_level)
            print(C_SUCCESS + f"  [Split] " + C_CHUNK + f"Segmented into {len(file_chunks)} sections.")
            chunks.extend(file_chunks)
        except Exception as e:
            print(C_ERROR + f"[-] Error reading file: {e}")
            return False
        
    total_chunks = len(chunks)
    if total_chunks == 0:
        print(C_ERROR + "[-] Error: No content sections found to process.")
        return False
        
    print(C_INFO + f"\n[Info] " + C_CHUNK + f"Total sections to process: {total_chunks}")
    if not api_key:
        print(C_WARNING + "[!] Running in Heuristic Fallback mode (no Gemini API key provided).")
        print(C_WARNING + "    Standard default metadata will be generated for your concepts.")
    else:
        print(C_SUCCESS + "[LLM] API Key loaded. Generating custom metadata via Gemini...")

    concepts = {}
    
    for idx, chunk in enumerate(chunks, 1):
        header = chunk["header"]
        content = chunk["content"]
        
        # Display progress line with clean carriage return
        sys.stdout.write(
            "\r" + C_STEP + f"[LLM] " + C_CHUNK + f"Structuring section {idx}/{total_chunks}: " + C_FILE + f"\"{header[:30]}...\""
        )
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
        
    print(C_SUCCESS + "\n  [+] Concept structuring completed.")
    
    print(C_STEP + "[Linker] " + C_CHUNK + "Establishing semantic cross-links...")
    linked_contents = cross_link_concepts(concepts)
    
    print(C_STEP + "[Save] " + C_CHUNK + f"Writing index catalog and category folders to: {output_dir}")
    write_okf_bundle(output_dir, concepts, linked_contents)
    
    print("\n" + C_SUCCESS + "┌" + "─" * 58 + "┐")
    print(C_SUCCESS + "│  " + Style.BRIGHT + "SUCCESS: OKF Compilation Complete!" + " " * 22 + C_SUCCESS + "│")
    print(C_SUCCESS + "└" + "─" * 58 + "┘")
    print(C_SUCCESS + f"   📂 Output Directory: " + Fore.WHITE + f"{os.path.abspath(output_dir)}")
    print(C_SUCCESS + f"   📄 Master Catalog Index: " + Fore.WHITE + f"{os.path.join(output_dir, 'index.md')}")
    print(C_SUCCESS + "─" * 60 + "\n")
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
    
    print(C_BANNER + "\n┌" + "─" * 58 + "┐")
    print(C_BANNER + "│ " + Style.BRIGHT + "🌌 OmniOKF: The Universal Open Knowledge Format Compiler" + "  " + C_BANNER + "│")
    print(C_BANNER + "└" + "─" * 58 + "┘")
    print(C_PROMPT + "   This guide will help you convert your documents step-by-step.")
    print(C_BANNER + "─" * 60)
    
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
