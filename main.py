import argparse
import os
import sys

from dotenv import load_dotenv
from rich.panel import Panel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.metadata import DEFAULT_GEMINI_MODEL
from src.pipeline import console, run_compiler_pipeline

__version__ = "0.2.0"


def interactive_mode() -> int:
    """Guides the user step-by-step through input selection and API key configuration."""
    load_dotenv()

    welcome_text = (
        "[bold white]OmniOKF: The Universal Open Knowledge Format Compiler[/bold white]\n\n"
        "[dim white]Convert unstructured documents into structured, cross-linked "
        "Markdown Knowledge Graphs for AI Agents.[/dim white]"
    )
    console.print(Panel(welcome_text, title="[bold magenta]OmniOKF Compiler[/bold magenta]", border_style="magenta", expand=False))

    while True:
        console.print("\n[bold cyan][1/2] Enter the path to your document file or folder:[/bold cyan]")
        input_path = console.input("[bold magenta]      > [/bold magenta]").strip().strip("\"'")
        if not input_path:
            console.print("[bold red]      [-] Input path cannot be empty.[/bold red]")
            continue
        if not os.path.exists(input_path):
            console.print(f"[bold red]      [-] Path '{input_path}' does not exist.[/bold red]")
            continue
        break

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        api_key = None
        console.print("\n[bold yellow][2/2] GEMINI_API_KEY not detected.[/bold yellow]")
        console.print("[dim white]      Get a free key at https://aistudio.google.com/[/dim white]")
        choice = console.input("[bold cyan]      Enter a key now for LLM categorization? (yes/no):[/bold cyan] ").strip().lower()
        if choice in ("y", "yes"):
            entered = console.input("[bold cyan]      Paste GEMINI_API_KEY:[/bold cyan]\n[bold magenta]      > [/bold magenta]").strip()
            if entered:
                api_key = entered
                save_choice = console.input("[bold cyan]      Save key to .env? (yes/no):[/bold cyan] ").strip().lower()
                if save_choice in ("y", "yes"):
                    try:
                        with open(".env", "w", encoding="utf-8") as f:
                            f.write(f"GEMINI_API_KEY={api_key}\n")
                        console.print("[bold green]      [+] Saved GEMINI_API_KEY to .env.[/bold green]")
                    except OSError as exc:
                        console.print(f"[bold yellow]      [!] Could not save .env: {exc}[/bold yellow]")
        else:
            console.print("[bold yellow]      [!] Running in offline heuristic mode.[/bold yellow]")
    else:
        console.print("\n[bold green][2/2] GEMINI_API_KEY detected in environment.[/bold green]")

    output_dir = os.environ.get("OKF_OUTPUT_DIR") or ".okf"
    model = os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    ok = run_compiler_pipeline(input_path, output_dir, "##", api_key=api_key, model=model)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser."""
    default_output = os.environ.get("OKF_OUTPUT_DIR") or ".okf"
    default_model = os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    parser = argparse.ArgumentParser(
        prog="omniokf",
        description="OmniOKF: Compile PDFs, Office docs, HTML, and Markdown into cross-linked OKF knowledge bundles.",
    )
    parser.add_argument("--input", "-i", required=True, help="Input file or directory path.")
    parser.add_argument("--output-dir", "-o", default=default_output, help=f"Output directory (default: {default_output}).")
    parser.add_argument("--split-level", "-s", default="##", help="Markdown header prefix to split at (default: '##').")
    parser.add_argument("--model", "-m", default=default_model, help=f"Gemini model name (default: {default_model}).")
    parser.add_argument("--offline", action="store_true", help="Force offline heuristic classification without calling Gemini.")
    parser.add_argument("--no-cache", action="store_true", help="Ignore manifest cache and recompile all files.")
    parser.add_argument("--clean", action="store_true", help="Remove stale .md files in output-dir no longer in the build.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main() -> int:
    load_dotenv()
    if len(sys.argv) == 1:
        return interactive_mode()

    args = build_parser().parse_args()
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key.startswith("your_"):
        api_key = None

    ok = run_compiler_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        split_level=args.split_level,
        api_key=api_key,
        model=args.model,
        offline=args.offline,
        use_cache=not args.no_cache,
        clean=args.clean,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
