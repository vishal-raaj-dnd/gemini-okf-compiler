import copy
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.table import Table

from src.indexer import write_okf_bundle
from src.linker import cross_link_concepts
from src.manifest import calculate_file_hash, load_manifest, save_manifest
from src.metadata import DEFAULT_GEMINI_MODEL, create_genai_client, extract_metadata
from src.parser import smart_local_classify, split_markdown

SUPPORTED_EXTENSIONS = (".md", ".markdown", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm")
console = Console()


def deduplicate_text(text: str) -> str:
    """Removes back-to-back duplicated headings/phrases produced by Office TOC conversions."""
    cleaned_lines: List[str] = []
    for line in text.splitlines():
        line_strip = line.strip()
        if not line_strip:
            cleaned_lines.append(line)
            continue

        mid = len(line_strip) // 2
        if len(line_strip) % 2 == 0 and line_strip[:mid] == line_strip[mid:]:
            lead_space = line[: line.find(line_strip)]
            cleaned_lines.append(lead_space + line_strip[:mid])
            continue

        match = re.match(r"^(.{3,})\1$", line_strip)
        if match:
            lead_space = line[: line.find(line_strip)]
            cleaned_lines.append(lead_space + match.group(1))
            continue

        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def read_input_file(filepath: str) -> str:
    """Reads and normalizes `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, or `.html` files to Markdown."""
    _, ext = os.path.splitext(filepath.lower())
    if ext in (".md", ".markdown"):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    if ext == ".pdf":
        from src.pdf_layout import parse_pdf_layout

        return parse_pdf_layout(filepath)
    if ext in (".docx", ".xlsx", ".pptx", ".html", ".htm"):
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(filepath)
        return deduplicate_text(result.text_content)

    raise ValueError(
        f"Unsupported file format: {ext}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def print_summary_table(summary_list: List[Dict[str, Any]]) -> None:
    """Prints a Rich summary table of the compilation run."""
    table = Table(
        title="[bold magenta]OmniOKF Ingestion Summary[/bold magenta]",
        border_style="magenta",
        header_style="bold cyan",
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
        chunks = item["chunks"]
        status = item["status"]

        if status == "Fresh":
            status_str = "[bold green]Fresh[/bold green]"
        elif status == "Cached":
            status_str = "[bold blue]Cached[/bold blue]"
            cached_chunks += chunks
        else:
            status_str = "[bold red]Failed[/bold red]"

        table.add_row(name, item["type"], str(chunks), status_str)
        total_chunks += chunks

    console.print("")
    console.print(Align.center(table))
    cache_pct = int((cached_chunks / total_chunks) * 100) if total_chunks > 0 else 0
    summary_text = (
        f"[bold cyan]Total Concepts:[/bold cyan] [bold white]{total_chunks}[/bold white] | "
        f"[bold cyan]Cached Ratio:[/bold cyan] [bold blue]{cache_pct}%[/bold blue]"
    )
    console.print(Align.center(summary_text))
    console.print("")


def extract_metadata_with_retry(
    body: str,
    client: Any,
    model: str,
    max_retries: int = 3,
) -> Tuple[Dict[str, Any], str]:
    """Calls extract_metadata with exponential backoff + jitter on rate-limit errors."""
    delay = 2.0
    for attempt in range(max_retries):
        try:
            return extract_metadata(body, client=client, model=model)
        except Exception as exc:
            err_str = str(exc).lower()
            is_rate_limit = "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str
            if is_rate_limit and attempt < max_retries - 1:
                time.sleep(delay * random.uniform(0.5, 1.5))
                delay *= 2.0
                continue
            raise
    raise RuntimeError("API retries exhausted.")


def _assign_unique_filename(base_filename: str, existing_filenames: set[str]) -> str:
    """Ensures each concept filename is unique within the compiled bundle."""
    unique_filename = base_filename
    counter = 2
    while unique_filename in existing_filenames:
        unique_filename = f"{base_filename}-{counter}"
        counter += 1
    existing_filenames.add(unique_filename)
    return unique_filename


def _gather_input_files(input_path: str) -> List[str]:
    """Collects supported document paths from a file or directory."""
    if not os.path.isdir(input_path):
        return [os.path.abspath(input_path)]

    found: List[str] = []
    for root, _, files in os.walk(input_path):
        for file in sorted(files):
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                found.append(os.path.abspath(os.path.join(root, file)))
    return found


def run_compiler_pipeline(
    input_path: str,
    output_dir: str,
    split_level: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    offline: bool = False,
    use_cache: bool = True,
    clean: bool = False,
) -> bool:
    """Core OKF compilation pipeline with incremental caching, cross-linking, and indexing."""
    console.print(
        Panel(
            f"[bold cyan]OmniOKF Compilation Process[/bold cyan]\n[dim white]Source: {input_path}[/dim white]",
            border_style="cyan",
        )
    )

    if not os.path.exists(input_path):
        console.print(f"[bold red][-] Error:[/bold red] Input path '{input_path}' does not exist.")
        return False

    input_files = _gather_input_files(input_path)
    if not input_files:
        console.print(f"[bold red][-] Error:[/bold red] No supported files found in '{input_path}'.")
        return False

    active_model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    mode = "offline" if (offline or not api_key) else "llm"
    genai_client = create_genai_client(api_key) if mode == "llm" else None

    console.print(f"[dim white][Info] Found {len(input_files)} document file(s) to process.[/dim white]")
    if mode == "offline":
        console.print("[bold yellow][!] Running in Offline Heuristic mode (no LLM calls).[/bold yellow]")
    else:
        console.print(f"[bold green][LLM] Using Gemini ({active_model}) for metadata extraction.[/bold green]\n")

    manifest = load_manifest(output_dir) if use_cache else {}
    new_manifest: Dict[str, Any] = {}
    concepts: Dict[str, Dict[str, Any]] = {}
    existing_filenames: set[str] = set()
    concept_idx = 1
    file_summary: List[Dict[str, Any]] = []
    errors: List[str] = []

    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30, complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("[cyan]Ingesting Documents...", total=len(input_files))

        for filepath in input_files:
            filename = os.path.basename(filepath)
            _, ext = os.path.splitext(filepath.lower())
            file_type_label = ext[1:].upper() if ext else "FILE"
            progress.update(task_id, description=f"[cyan]Scanning: {filename[:15]}...")

            try:
                file_hash = calculate_file_hash(filepath)
            except OSError as exc:
                errors.append(f"{filename}: failed to read file hash ({exc})")
                file_summary.append({"name": filename, "type": file_type_label, "chunks": 0, "status": "Failed"})
                progress.advance(task_id)
                continue

            cached_entry = manifest.get(filepath)
            cache_valid = (
                use_cache
                and isinstance(cached_entry, dict)
                and cached_entry.get("hash") == file_hash
                and cached_entry.get("split_level") == split_level
                and cached_entry.get("mode") == mode
                and (mode == "offline" or cached_entry.get("model") == active_model)
            )
            if cache_valid:
                cached_concepts = cached_entry.get("concepts", [])
                for concept_data in cached_concepts:
                    entry_copy = copy.deepcopy(concept_data)
                    entry_copy["metadata"]["filename"] = _assign_unique_filename(
                        entry_copy["metadata"]["filename"], existing_filenames
                    )
                    concepts[f"chunk_{concept_idx}"] = entry_copy
                    concept_idx += 1

                new_manifest[filepath] = cached_entry
                file_summary.append({"name": filename, "type": file_type_label, "chunks": len(cached_concepts), "status": "Cached"})
                progress.advance(task_id)
                continue

            try:
                content = read_input_file(filepath)
                file_chunks = split_markdown(content, split_level)
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
                file_summary.append({"name": filename, "type": file_type_label, "chunks": 0, "status": "Failed"})
                progress.advance(task_id)
                continue

            file_concepts: List[Dict[str, Any]] = []
            total_file_chunks = len(file_chunks)

            for idx, chunk in enumerate(file_chunks, start=1):
                header = chunk["header"]
                body = chunk["content"]
                progress.update(task_id, description=f"[cyan]Processing: {filename[:12]} [magenta][{idx}/{total_file_chunks}][/magenta]")

                meta = None
                cleaned_content = body
                if mode == "llm" and genai_client is not None:
                    try:
                        meta, cleaned_content = extract_metadata_with_retry(body, genai_client, active_model)
                    except Exception as exc:
                        errors.append(f"{filename} chunk {idx} LLM fallback: {exc}")

                if not meta:
                    meta = smart_local_classify(header, body, concept_idx)
                    cleaned_content = body

                manifest_entry = {"metadata": copy.deepcopy(meta), "content": cleaned_content}
                file_concepts.append(manifest_entry)

                bundle_entry = {"metadata": meta, "content": cleaned_content}
                bundle_entry["metadata"]["filename"] = _assign_unique_filename(meta["filename"], existing_filenames)
                concepts[f"chunk_{concept_idx}"] = bundle_entry
                concept_idx += 1

            new_manifest[filepath] = {
                "hash": file_hash,
                "split_level": split_level,
                "mode": mode,
                "model": active_model if mode == "llm" else None,
                "concepts": file_concepts,
            }
            file_summary.append({"name": filename, "type": file_type_label, "chunks": total_file_chunks, "status": "Fresh"})
            progress.advance(task_id)

    for err in errors:
        console.print(f"[bold yellow][!] Warning:[/bold yellow] {err}")

    if not concepts:
        console.print("[bold red][-] Error: No concepts were successfully compiled.[/bold red]")
        return False

    with console.status("[bold magenta]Establishing semantic cross-links (TF-IDF)...", spinner="dots"):
        linked_contents = cross_link_concepts(concepts)

    with console.status("[bold magenta]Writing index catalog, graph, and category folders...", spinner="dots"):
        try:
            write_okf_bundle(output_dir, concepts, linked_contents, clean=clean)
            save_manifest(output_dir, new_manifest)
        except Exception as exc:
            console.print(f"[bold red][-] Error writing output bundle: {exc}[/bold red]")
            return False

    print_summary_table(file_summary)
    console.print(
        Panel(
            "[bold green]SUCCESS: OKF Compilation Complete![/bold green]\n\n"
            f"[dim white]Output Directory:[/dim white] [cyan]{os.path.abspath(output_dir)}[/cyan]\n"
            f"[dim white]Master Catalog Index:[/dim white] [cyan]{os.path.join(output_dir, 'index.md')}[/cyan]",
            border_style="green",
        )
    )
    return True
