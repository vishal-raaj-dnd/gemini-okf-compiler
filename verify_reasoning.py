import argparse
import os
import re
import sys
from dotenv import load_dotenv

from src.metadata import DEFAULT_GEMINI_MODEL, create_genai_client


def load_bundle_file(bundle_dir: str, rel_path: str) -> str:
    """Reads a markdown file from the compiled OKF bundle directory."""
    clean_rel = rel_path.lstrip("./")
    full_path = os.path.abspath(os.path.join(bundle_dir, clean_rel))
    if not full_path.startswith(os.path.abspath(bundle_dir) + os.sep):
        return ""
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Query a compiled OKF bundle using index-guided traversal.")
    parser.add_argument("--bundle-dir", default=".okf", help="Path to compiled OKF bundle (default: .okf).")
    parser.add_argument(
        "--question",
        default="What is the incident response process and how does it relate to database backups?",
        help="Question to answer from the compiled OKF bundle.",
    )
    args = parser.parse_args()

    index_md = load_bundle_file(args.bundle_dir, "index.md")
    if not index_md:
        print(f"[-] Error: Could not find '{os.path.join(args.bundle_dir, 'index.md')}'.")
        print("    Compile a bundle first: python main.py -i example_raw.md --offline")
        return 1

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        print("[-] GEMINI_API_KEY is required for live LLM traversal.")
        print("    Available index entries:")
        for line in index_md.splitlines():
            if line.startswith("- **["):
                print(f"    {line}")
        return 0

    model_name = os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
    client = create_genai_client(api_key)

    step1_prompt = (
        "You are an AI Agent navigating an OKF knowledge base.\n"
        "From the following index.md, list the relative file paths (e.g. `./guide/database-setup.md`) "
        "needed to answer the question.\n\n"
        f"Question: {args.question}\n\n"
        f"Index:\n{index_md}\n\n"
        "Output only the relative file paths, one per line:"
    )
    step1_resp = client.models.generate_content(model=model_name, contents=step1_prompt)
    selected_paths = re.findall(r"\./[a-z0-9\-]+/[a-z0-9\-]+\.md", step1_resp.text or "")

    if not selected_paths:
        print("[-] No concept files matched by index traversal.")
        return 1

    print("[+] Selected OKF nodes:")
    contexts = []
    for rel_path in dict.fromkeys(selected_paths):
        print(f"    -> {rel_path}")
        content = load_bundle_file(args.bundle_dir, rel_path)
        if content:
            contexts.append(content)

    final_prompt = (
        "Answer the question based ONLY on the provided OKF concept files.\n\n"
        f"Question: {args.question}\n\n"
        + "\n\n---\n\n".join(contexts)
    )
    final_resp = client.models.generate_content(model=model_name, contents=final_prompt)
    print("\n[+] Answer:\n" + (final_resp.text or "").strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
