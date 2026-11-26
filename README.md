# OmniOKF: The Universal Open Knowledge Format Compiler

[![OKF BundleDex](https://bundledex.net/static-badge.svg)](https://bundledex.net)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Turn unstructured documents into clean, semantic, cross-linked Markdown Knowledge Graphs designed for AI Agents and RAG pipelines.

**OmniOKF** compiles raw enterprise documentation (PDFs, Word files, Excel sheets, PowerPoints, HTML pages, and Markdown) into agent-ready **Open Knowledge Format (OKF)** bundles.

It combines layout-aware PDF parsing (`PyMuPDF`), Office document conversion (`markitdown`), optional **Gemini** structured metadata extraction, TF-IDF cross-linking, and incremental MD5 caching into a single CLI.

---

## Why OmniOKF

1. **Structured Ingestion**: Extracts headings from PDFs via font-size/boldness analysis and cleans Office TOC duplicates before chunking.
2. **Focused Context Loading**: Splits documents at configurable header boundaries into categorized Markdown files with YAML frontmatter, so agents read only the concepts they need instead of entire 100-page files.
3. **Zero-Database Knowledge Graph**: Generates relative Markdown links between related concepts (`[Incident Response](../process/incident-response.md)`), a master `index.md` with a Mermaid flowchart, and an interactive `visualizer.html`.
4. **Offline & Compliance Ready**: Run with `--offline` (or without a Gemini API key) to classify, tag, and cross-link 100% locally with zero external LLM API calls.

---

## Installation & Setup

### Prerequisites
- Python **3.10+**
- *(Optional)* A Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/) for LLM-powered metadata extraction

### Install
```bash
git clone https://github.com/vishal-raaj-dnd/gemini-okf-compiler.git
cd gemini-okf-compiler
pip install -e .
```
*(Or install dependencies directly with `pip install -r requirements.txt`.)*

### Configure Credentials (Optional)
```bash
cp .env.template .env
# Edit .env to set GEMINI_API_KEY, GEMINI_MODEL, and OKF_OUTPUT_DIR
```

---

## Quickstart

Try it immediately on the included sample handbook without an API key:
```bash
python main.py --input example_raw.md --output-dir .okf --offline --clean
```

Or if installed via `pip install -e .`:
```bash
omniokf --input example_raw.md --output-dir .okf --offline --clean
```

### Interactive Mode
Run without arguments for a guided prompt:
```bash
python main.py
```

### CLI Mode
```bash
# Compile a PDF using Gemini metadata extraction
omniokf --input manuals/onboarding.pdf --output-dir .okf

# Compile an entire directory of mixed documents and prune stale outputs
omniokf --input ./raw_documents --output-dir .okf --clean

# Force offline heuristic mode and bypass cache
omniokf --input ./raw_documents --offline --no-cache
```

### Command Line Arguments
- `--input`, `-i`: Path to the input file or directory containing files (required in CLI mode).
- `--output-dir`, `-o`: Directory where the OKF bundle will be created (default: `OKF_OUTPUT_DIR` or `.okf`).
- `--split-level`, `-s`: Markdown header prefix to split at (default: `##`).
- `--model`, `-m`: Gemini model name for metadata extraction (default: `GEMINI_MODEL` or `gemini-2.0-flash`).
- `--offline`: Force offline heuristic classification without calling Gemini.
- `--no-cache`: Ignore `manifest.json` cache and recompile all files.
- `--clean`: Remove stale `.md` files in `output-dir` no longer present in the build.
- `--version`: Print the installed version and exit.

### Environment Variables
- `GEMINI_API_KEY`: Google Gemini API key (if unset, OmniOKF automatically uses offline heuristic mode).
- `GEMINI_MODEL`: Default Gemini model (defaults to `gemini-2.0-flash`).
- `OKF_OUTPUT_DIR`: Default output directory (defaults to `.okf`).

---

## OKF Bundle Structure

```text
.okf/
├── index.md             # Master catalog + Mermaid knowledge graph
├── visualizer.html      # Standalone interactive graph viewer
├── manifest.json        # Incremental MD5 & build-config cache
├── guide/
│   └── database-setup-guide.md
└── process/
    └── incident-response-protocol.md
```

Each concept file includes OKF YAML frontmatter:
```markdown
---
type: process
title: Incident Response Protocol
description: Steps to take when an alert is triggered in production.
tags:
- incident
- pagerduty
- slack
timestamp: 2026-07-09T03:20:00Z
---

## Incident Response Protocol
...
```

---

## Incremental Compilation & GitHub Action

- **Incremental Cache**: OmniOKF hashes each input file and records `split_level`, `mode`, and `model` in `.okf/manifest.json`. Unchanged files with matching build settings are loaded from cache on subsequent runs.
- **GitHub Action**: See [.github/workflows/okf-generator.yml](.github/workflows/okf-generator.yml) to automatically compile `documents/` or `raw_input.md` into `.okf/` on push.

---

## Development & Testing

Install dev dependencies and run the test suite:
```bash
pip install -e ".[dev]"
pytest -v
```

---

## License
Licensed under the MIT License. See [LICENSE](LICENSE) for details.
