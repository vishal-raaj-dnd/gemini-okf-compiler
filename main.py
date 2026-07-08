import os
import argparse
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

# Add src to python path if needed (although relative imports will work)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser import split_markdown
from src.metadata import extract_metadata
from src.linker import cross_link_concepts
from src.indexer import write_okf_bundle

def read_input_file(filepath: str) -> str:
    """
    Reads the content of the file. If it is a DOCX file, converts it to Markdown using mammoth.
    Otherwise, reads it as a standard text file.
    """
    _, ext = os.path.splitext(filepath.lower())
    if ext == ".docx":
        import mammoth
        print(f"Converting DOCX to Markdown: {filepath}")
        with open(filepath, "rb") as docx_file:
            result = mammoth.convert_to_markdown(docx_file)
            for message in result.messages:
                print(f"  [DOCX Warning] {message.message}")
            return result.value
    elif ext in (".md", ".markdown"):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats are .md, .markdown, and .docx.")

def main():
    # Load .env file
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="OKF Compiler: Transform flat Markdown and Word (.docx) files into structured, cross-linked Open Knowledge Format bundles."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input flat markdown file, .docx file, or directory containing them."
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
    
    if not os.path.exists(args.input):
        print(f"Error: Input path '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    chunks = []
    if os.path.isdir(args.input):
        print(f"Loading input directory: {args.input}")
        input_files = []
        for root, dirs, files in os.walk(args.input):
            for file in files:
                if file.lower().endswith((".md", ".markdown", ".docx")):
                    input_files.append(os.path.join(root, file))
        
        if not input_files:
            print(f"Error: No supported files (.md, .markdown, .docx) found in directory '{args.input}'.", file=sys.stderr)
            sys.exit(1)
            
        print(f"Found {len(input_files)} document files. Processing each...")
        for filepath in input_files:
            try:
                content = read_input_file(filepath)
                file_chunks = split_markdown(content, args.split_level)
                chunks.extend(file_chunks)
            except Exception as e:
                print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
    else:
        try:
            content = read_input_file(args.input)
            chunks = split_markdown(content, args.split_level)
        except Exception as e:
            print(f"Error reading file '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)
        
    print(f"Identified {len(chunks)} total document chunks.")
    
    # Check for API Key, otherwise warn and run in fallback heuristic mode
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[WARNING] GEMINI_API_KEY environment variable is not set!")
        print("The compiler will run in heuristic fallback mode (no LLM calls).")
        print("To resolve, set GEMINI_API_KEY in a .env file or your environment.\n")
        
    concepts = {}
    
    for idx, chunk in enumerate(chunks, 1):
        header = chunk["header"]
        content = chunk["content"]
        
        print(f"Processing chunk {idx}/{len(chunks)}: '{header}'...")
        
        meta = None
        cleaned_content = content
        
        if api_key:
            try:
                meta, cleaned_content = extract_metadata(content)
                print(f"  -> Extracted metadata successfully (Type: {meta['type']})")
            except Exception as e:
                print(f"  -> [LLM Error] Failed to generate metadata via Gemini: {e}")
                print("  -> Falling back to heuristic metadata...")
                
        # Heuristic Fallback
        if not meta:
            # Generate a slug from the header
            slug = re.sub(r'[^a-z0-9\-]', '', header.lower().replace(' ', '-').replace('_', '-'))
            slug = slug.strip('-')
            if not slug:
                slug = f"concept-{idx}"
                
            # Basic OKF-compliant fallback dictionary
            meta = {
                "type": "concept",
                "title": header,
                "description": f"Section covering: {header}.",
                "tags": ["uncategorized"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "filename": slug
            }
            cleaned_content = content
            print(f"  -> Created heuristic fallback (Filename: {meta['filename']})")
            
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
        
    print("\nRunning semantic cross-linker...")
    linked_contents = cross_link_concepts(concepts)
    
    print(f"Writing OKF bundle to: {args.output_dir}")
    write_okf_bundle(args.output_dir, concepts, linked_contents)
    
    print("\n[SUCCESS] Compilation complete!")
    print(f"Created OKF bundle in folder: {os.path.abspath(args.output_dir)}")
    print(f"Index catalog: {os.path.join(args.output_dir, 'index.md')}")

if __name__ == "__main__":
    main()
