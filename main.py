import os
import argparse
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

# Initialize rich elements for highly graphical console output mimicking Claude Code
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.align import Align
from rich import print as rprint

console = Console()

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser import split_markdown
from src.metadata import extract_metadata
from src.linker import cross_link_concepts
from src.indexer import write_okf_bundle
from src.manifest import calculate_file_hash, load_manifest, save_manifest

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
            
        mid = len(line_strip) // 2
        if len(line_strip) % 2 == 0:
            left, right = line_strip[:mid], line_strip[mid:]
            if left == right:
                lead_space = line[:line.find(line_strip)]
                cleaned_lines.append(lead_space + left)
                continue
                
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
    """Prints a beautiful, highly professional Table summarizing the ingestion run using rich."""
    table = Table(
        title="[bold magenta]OmniOKF Ingestion Summary[/bold magenta]",
        border_style="magenta",
        header_style="bold cyan"
    )
    table.add_column("File Name", style="white")
    table.add_column("Type", style="dim white")
    table.add_column("Chunks", justify="right", style="cyan")
    table.add_column("Status", justify="center")
    
    total_chunks = 0
    cached_chunks = 0
    
    for item in summary_list:
        name = item["name"]
        if len(name) > 30:
            name = name[:27] + "..."
        file_type = item["type"]
        chunks = item["chunks"]
        status = item["status"]
        
        if status == "Fresh":
            status_str = "[bold green]Fresh[/bold green]"
        elif status == "Cached":
            status_str = "[bold blue]Cached[/bold blue]"
            cached_chunks += chunks
        else:
            status_str = "[bold red]Failed[/bold red]"
            
        table.add_row(name, file_type, str(chunks), status_str)
        total_chunks += chunks
        
    console.print("")
    console.print(Align.center(table))
    
    cache_pct = int((cached_chunks / total_chunks) * 100) if total_chunks > 0 else 0
    summary_text = f"[bold cyan]Total Concepts:[/bold cyan] [bold white]{total_chunks}[/bold white] | [bold cyan]Cached Ratio:[/bold cyan] [bold blue]{cache_pct}%[/bold blue]"
    console.print(Align.center(summary_text))
    console.print("")

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

def run_compiler_pipeline(input_path: str, output_dir: str, split_level: str, api_key: str = None) -> bool:
    """
    Core compilation pipeline that reads, parses, splits, metadata-extracts,
    cross-links, and indexes documents with rich console layouts.
    Supports incremental compilation (caching) via manifest hashes.
    """
    welcome_text = (
        "[bold cyan]OmniOKF Compilation Process[/bold cyan]\n"
        f"[dim white]Source Ingestion Path: {input_path}[/dim white]"
    )
    console.print(Panel(welcome_text, border_style="cyan"))

    if not os.path.exists(input_path):
        console.print(f"[bold red][-] Error:[/bold red] Input path '{input_path}' does not exist.")
        return False
        
    supported_extensions = (".md", ".markdown", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm")
    input_files = []
    
    # 1. Gather all files
    if os.path.isdir(input_path):
        for root, dirs, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(supported_extensions):
                    input_files.append(os.path.abspath(os.path.join(root, file)))
        
        if not input_files:
            console.print(f"[bold red][-] Error:[/bold red] No supported files {supported_extensions} found in '{input_path}'.")
            return False
    else:
        input_files.append(os.path.abspath(input_path))
        
    console.print(f"[dim white][Info] Found {len(input_files)} document file(s) to process.[/dim white]")
    if not api_key:
        console.print("[bold yellow][!] Running in Offline Heuristic Fallback mode (no Gemini API key).[/bold yellow]")
    else:
        console.print("[bold green][LLM] API Key loaded. Generating custom metadata via Gemini...[/bold green]\n")

    # Load cache manifest
    manifest = load_manifest(output_dir)
    new_manifest = {}
    concepts = {}
    concept_idx = 1
    file_summary = []
    
    # Process files inside a rich Progress Context
    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("[cyan]Ingesting Documents...", total=len(input_files))
        
        for filepath in input_files:
            filename = os.path.basename(filepath)
            _, ext = os.path.splitext(filepath.lower())
            file_type_label = ext[1:].upper()
            
            progress.update(task_id, description=f"[cyan]Scanning: {filename[:15]}...")
            
            try:
                file_hash = calculate_file_hash(filepath)
            except Exception as e:
                file_summary.append({
                    "name": filename,
                    "type": file_type_label,
                    "chunks": 0,
                    "status": "Failed"
                })
                progress.advance(task_id)
                continue
                
            # Check cache
            cached_entry = manifest.get(filepath)
            if cached_entry and cached_entry.get("hash") == file_hash:
                cached_concepts = cached_entry.get("concepts", [])
                for concept_data in cached_concepts:
                    meta = concept_data["metadata"]
                    
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
                progress.advance(task_id)
                continue
                
            # Parse document fresh
            try:
                content = read_input_file(filepath)
                file_chunks = split_markdown(content, split_level)
            except Exception as e:
                file_summary.append({
                    "name": filename,
                    "type": file_type_label,
                    "chunks": 0,
                    "status": "Failed"
                })
                progress.advance(task_id)
                continue
                
            file_concepts = []
            total_file_chunks = len(file_chunks)
            
            for idx, chunk in enumerate(file_chunks, 1):
                header = chunk["header"]
                body = chunk["content"]
                
                # Update text details in-place
                progress.update(
                    task_id, 
                    description=f"[cyan]Processing: {filename[:12]} [magenta][{idx}/{total_file_chunks}][/magenta]"
                )
                
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
            progress.advance(task_id)
        
    if not concepts:
        console.print("[bold red][-] Error: No concepts were successfully compiled.[/bold red]")
        return False
        
    # Running linking and writing phases in spinners
    with console.status("[bold magenta]Establishing semantic cross-links (TF-IDF)...", spinner="dots"):
        linked_contents = cross_link_concepts(concepts)
        
    with console.status("[bold magenta]Writing index catalog, graph, and category folders...", spinner="dots"):
        try:
            write_okf_bundle(output_dir, concepts, linked_contents)
            save_manifest(output_dir, new_manifest)
        except Exception as e:
            console.print(f"[bold red][-] Error writing output bundle: {e}[/bold red]")
            return False
        
    # Render final ingestion summary table
    print_summary_table(file_summary)
    
    success_text = (
        "[bold green]SUCCESS: OKF Compilation Complete![/bold green]\n\n"
        f"[dim white]Output Directory:[/dim white] [cyan]{os.path.abspath(output_dir)}[/cyan]\n"
        f"[dim white]Master Catalog Index:[/dim white] [cyan]{os.path.join(output_dir, 'index.md')}[/cyan]"
    )
    console.print(Panel(success_text, border_style="green"))
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
    
    welcome_text = (
        "[bold white]OmniOKF: The Universal Open Knowledge Format Compiler[/bold white]\n\n"
        "[dim white]This guide will help you convert unstructured document sets into "
        "structured, cross-linked Markdown Knowledge Graphs for AI Agents.[/dim white]"
    )
    console.print(Panel(welcome_text, title="[bold magenta]🌌 OmniOKF Compiler[/bold magenta]", border_style="magenta", expand=False))
    
    # 1. Ask for input path
    while True:
        console.print("\n[bold cyan][1/2] Enter the path to your document file or folder:[/bold cyan]")
        input_path = console.input("[bold magenta]      > [/bold magenta]").strip()
        input_path = input_path.strip('"\'')
        if not input_path:
            console.print("[bold red]      [-] Input path cannot be empty.[/bold red]")
            continue
        if not os.path.exists(input_path):
            console.print(f"[bold red]      [-] Path '{input_path}' does not exist. Please check the spelling.[/bold red]")
            continue
        break
        
    # 2. Check for Gemini Key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("\n[bold yellow][2/2] Gemini API Key was not detected in your configuration.[/bold yellow]")
        console.print("[dim white]      Note: Get a free API Key from Google AI Studio (https://aistudio.google.com/)[/dim white]")
        choice = console.input("[bold cyan]      Would you like to enter a key now to use LLM categorization? (yes/no):[/bold cyan] ").strip().lower()
        if choice in ("y", "yes"):
            api_key = console.input("[bold cyan]      Paste your GEMINI_API_KEY here:[/bold cyan]\n[bold magenta]      > [/bold magenta]").strip()
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                save_choice = console.input("[bold cyan]      Save this API Key in a .env file for future runs? (yes/no):[/bold cyan] ").strip().lower()
                if save_choice in ("y", "yes"):
                    try:
                        with open(".env", "w") as f:
                            f.write(f"GEMINI_API_KEY={api_key}\n")
                        console.print("[bold green]      [+] Gemini API Key successfully saved to .env file.[/bold green]")
                    except Exception as e:
                        console.print(f"[bold yellow]      [!] Warning: Could not save key to .env file: {e}[/bold yellow]")
        else:
            console.print("[bold yellow]      [!] Running in heuristic fallback mode (no LLM metadata extraction).[/bold yellow]")
    else:
        console.print("\n[bold green][2/2] Gemini API Key detected in environment configuration.[/bold green]")

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
