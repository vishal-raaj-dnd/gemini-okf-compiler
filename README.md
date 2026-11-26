<p align="center">
  <img src="social_preview.png" alt="OmniOKF" width="720" />
</p>

<h1 align="center">OmniOKF</h1>
<p align="center"><strong>The Universal Open Knowledge Format Compiler</strong></p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License" /></a>
  <a href="https://github.com/vishal-raaj-dnd/gemini-okf-compiler/actions"><img src="https://img.shields.io/github/actions/workflow/status/vishal-raaj-dnd/gemini-okf-compiler/ci.yml?branch=main&style=flat-square&label=tests" alt="CI" /></a>
  <img src="https://komarev.com/ghpvc/?username=vishal-raaj-dnd&repo=gemini-okf-compiler&label=visitors&color=0e75b6&style=flat-square" alt="Visitors" />
</p>

<p align="center">
  Turn messy PDFs, Word docs, spreadsheets, and HTML pages into clean, cross-linked<br/>
  <strong>Markdown Knowledge Graphs</strong> that AI agents can navigate like a wiki.
</p>

---

## The Problem

You have 50 internal docs scattered across PDFs, Word files, and HTML pages. You feed them into a RAG pipeline and get:

- 💸 **Token waste** — entire 100-page documents stuffed into context windows
- 🧩 **Lost connections** — chunks treated as isolated text blocks with no linking
- 🗑️ **Garbage in, garbage out** — messy formatting, duplicated TOC entries, broken headers

## The Solution

OmniOKF compiles your documents into an **OKF bundle** — a directory of small, categorized Markdown files with YAML metadata, relative cross-links, and a master index:

```
Input: 50 messy documents          Output: .okf/ knowledge graph
┌──────────────────────┐           ┌──────────────────────────┐
│ onboarding.pdf       │           │ index.md (master catalog)│
│ runbook.docx         │  ──────▶  │ guide/onboarding.md      │
│ schema.xlsx          │           │ process/incident.md      │
│ architecture.html    │           │ reference/db-schema.md   │
│ ...47 more files     │           │ visualizer.html (graph)  │
└──────────────────────┘           └──────────────────────────┘
```

An AI agent reads `index.md`, picks the 2-3 concept files it needs, follows cross-links to related topics, and answers with **75-95% fewer tokens** than dumping the raw documents.

---

## Features

| Feature | Description |
|---------|-------------|
| **Universal Ingestion** | `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.html`, `.md` — all natively supported |
| **Layout-Aware PDF Parsing** | Infers `#`, `##`, `###` headings from font size ratios and bold styling via PyMuPDF |
| **Gemini Metadata Extraction** | Structured JSON output via `gemini-2.0-flash` for type, title, description, tags, and filename |
| **Offline Heuristic Mode** | Full compilation with zero API calls — classify, tag, and cross-link locally with `--offline` |
| **TF-IDF Cross-Linking** | Automatically generates relative Markdown links between related concepts |
| **Mermaid Knowledge Graph** | `index.md` includes a Mermaid flowchart; `visualizer.html` renders it interactively |
| **Incremental Caching** | MD5 hashes + build config in `manifest.json` — unchanged files compile in milliseconds |
| **Stale File Cleanup** | `--clean` removes orphaned output files no longer in the build |
| **Path-Safe Output** | All LLM-returned filenames and categories are sanitized to prevent traversal |

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/vishal-raaj-dnd/gemini-okf-compiler.git
cd gemini-okf-compiler
pip install -e .
```

### 2. Compile (no API key needed)

```bash
omniokf --input example_raw.md --offline --clean
```

### 3. Explore the output

```bash
cat .okf/index.md           # Master catalog with Mermaid graph
ls .okf/guide/              # Categorized concept files
open .okf/visualizer.html   # Interactive knowledge graph
```

---

## Usage

### Interactive Mode
```bash
python main.py              # Guided step-by-step prompts
```

### CLI Mode
```bash
# Compile a PDF with Gemini metadata extraction
omniokf -i manuals/onboarding.pdf

# Compile a directory of mixed documents
omniokf -i ./raw_documents --clean

# Offline mode, bypass cache, custom split level
omniokf -i ./raw_documents --offline --no-cache --split-level "#"

# Use a specific Gemini model
omniokf -i ./docs --model gemini-2.5-flash
```

### All Options

| Flag | Description | Default |
|------|-------------|---------|
| `--input`, `-i` | Input file or directory (required) | — |
| `--output-dir`, `-o` | Output bundle directory | `.okf` |
| `--split-level`, `-s` | Markdown header level to split at | `##` |
| `--model`, `-m` | Gemini model for metadata extraction | `gemini-2.0-flash` |
| `--offline` | Skip all Gemini API calls | `false` |
| `--no-cache` | Ignore `manifest.json` and recompile everything | `false` |
| `--clean` | Remove stale `.md` files from previous builds | `false` |
| `--version` | Print version and exit | — |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key ([get one free](https://aistudio.google.com/)) | *(offline mode if unset)* |
| `GEMINI_MODEL` | Default Gemini model | `gemini-2.0-flash` |
| `OKF_OUTPUT_DIR` | Default output directory | `.okf` |

---

## OKF Bundle Structure

```text
.okf/
├── index.md              # Master catalog + Mermaid knowledge graph
├── visualizer.html       # Standalone interactive graph viewer
├── manifest.json         # Incremental build cache
├── guide/
│   ├── company-knowledge-handbook.md
│   └── database-setup-guide.md
├── process/
│   ├── backup-standards.md
│   └── incident-response-protocol.md
└── reference/
    └── db-schema.md
```

Each concept file has OKF YAML frontmatter:

```yaml
---
type: process
title: Incident Response Protocol
description: Steps to take when a production alert triggers.
tags:
  - incident
  - pagerduty
  - slack
timestamp: 2026-07-09T03:20:00Z
---
```

---

## How AI Agents Use an OKF Bundle

```text
Agent starts
  │
  ▼
Reads index.md ──▶ Gets a map of all concepts, categories, and cross-links
  │
  ▼
Fetches 2-3 concept files ──▶ Only the specific topics needed (saves 75-95% tokens)
  │
  ▼
Follows relative Markdown links ──▶ Traverses to related concepts as needed
```

Instead of feeding a 100-page PDF into the context window, the agent selectively loads and traverses only the graph nodes it needs.

---

## Incremental Compilation

OmniOKF caches intelligently:

- **MD5 file hashes** detect content changes
- **Build config** (`split_level`, `mode`, `model`) is tracked per file — changing any setting triggers recompilation
- **Manifest isolation** — cached content stores pre-link Markdown, so cross-links are always recomputed fresh

```bash
# First run: compiles everything
omniokf -i ./docs --clean
# Output: 50 concepts compiled | Cached: 0%

# Second run: only changed files recompile
omniokf -i ./docs --clean
# Output: 50 concepts compiled | Cached: 96%
```

---

## GitHub Action

Automatically compile documents on push. See [`.github/workflows/okf-generator.yml`](.github/workflows/okf-generator.yml):

```yaml
- name: Run OKF Compiler
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  run: omniokf --input documents --output-dir .okf --clean
```

---

## Architecture

```text
main.py                    CLI entrypoint & interactive mode
src/
├── pipeline.py            Orchestrates the full compilation pipeline
├── parser.py              Markdown splitter (code-block aware) + offline classifier
├── pdf_layout.py          Layout-aware PDF → Markdown via PyMuPDF
├── metadata.py            Gemini structured metadata extraction (Pydantic schema)
├── linker.py              TF-IDF cross-linking (preserves code blocks & existing links)
├── indexer.py             Bundle writer with path-safe output + stale file pruning
├── visualizer.py          Mermaid graph + standalone HTML visualizer
└── manifest.py            MD5 hashing + JSON manifest for incremental caching
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest -v

# Run the caching verification script
python verify_caching.py

# Query a compiled bundle (requires GEMINI_API_KEY)
python verify_reasoning.py --bundle-dir .okf --question "How do backups work?"
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run `pytest -v` to ensure all tests pass
4. Submit a pull request

---

## License

MIT License © 2026 [Vishal Raaj DND](https://github.com/vishal-raaj-dnd). See [LICENSE](LICENSE) for details.
