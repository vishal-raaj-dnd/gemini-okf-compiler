# 🌌 OmniOKF: The Universal Open Knowledge Format Compiler

[![OKF BundleDex](https://bundledex.net/static-badge.svg)](https://bundledex.net)

> Turn unstructured document mess into clean, semantic, cross-linked Knowledge Graphs designed for AI Agents and RAG pipelines.

**OmniOKF** is a high-performance, zero-system-dependency compiler that transforms raw, fragmented enterprise documentation (PDFs, Word files, Excel sheets, PowerPoints, HTML web pages, and Markdown) into agent-ready **Open Knowledge Format (OKF)** bundles. 

By utilizing Microsoft's `markitdown` for in-memory document parsing and Gemini Flash for rapid semantic structuring, OmniOKF compiles structured, cross-linked "LLM Wikis" at a fraction of standard API token costs.

---

## 💡 Why This Tool Helps

Traditional AI systems (RAG) suffer from three major bottlenecks when working with corporate documents:

1. **The "Garbage In, Garbage Out" Problem**: Messy PDFs, scanned documents, and spreadsheets break standard text splitters. OmniOKF cleans, infers structural headers, and filters out noise *before* the AI sees it.
2. **Context Window Clutter**: Sending a massive 100-page document or retrieving 10 giant chunks into an LLM context is extremely expensive and slow. OmniOKF splits your database into **atomic concept files (200-500 tokens each)**, reducing token consumption by **75% to 95%** per query.
3. **Loss of Interconnected Context**: Standard search indexes treat chunks like isolated text blocks. OmniOKF builds a **zero-database Knowledge Graph** using relative Markdown links, allowing AI Agents to traverse related specifications (e.g., following `[Celery SSL]` back to `[Redis Message Broker]`) naturally.
4. **Offline and Compliance Safe**: Enterprise teams with sensitive data can run the compiler **100% offline** using the built-in Heuristic Classifier, ensuring zero data is sent to cloud APIs.

---

## ✨ Features

- **🚀 Universal Ingestion**: Compiles `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.html`, and `.md` files natively.
- **⚡ Zero System Dependencies**: Powered by Microsoft's Python-native `markitdown`—no complex system binaries (like Pandoc or heavy PyTorch GPU dependencies) required.
- **🧠 Semantic Concept Splitting**: Heuristically partitions files at header boundaries (`#`, `##`), then uses LLM intelligence to refine, label, and categorize chunks.
- **🔗 Automatic Cross-Linking**: Automatically scans the compiled library and constructs a Markdown-based knowledge graph using relative links (e.g., `[Incident Response](../processes/incident-response.md)`).
- **📂 Unified Graph Indexing**: Automatically compiles a master root `index.md` containing category mappings and description snapshots of your entire knowledge catalog.
- **⚙️ Naming Collision Resolution**: Implements automated numbering and suffixing to handle duplicate topic names across separate source files.

---

## 🛠️ How AI Agents Read an OmniOKF Bundle

When you load an OmniOKF directory into an AI agent (such as Claude Code, a custom RAG chatbot, or a developer agent), the agent traverses the catalog systematically:

```
[Agent Starts] ➔ Reads root index.md (Gets a map of all concepts and categories)
                      │
                      ▼
[Target Selection] ➔ Fetches only the specific concept file (Saves token cost!)
                      │
                      ▼
[Graph Traversal] ➔ Follows auto-generated relative Markdown links to related files
```

Instead of feeding a giant 100-page document to the LLM (wasting thousands of context tokens), the agent selectively loads and traverses only the exact nodes of the graph it needs.

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.9+
- A Google Gemini API Key (get one at [Google AI Studio](https://aistudio.google.com/))

### 2. Install
```bash
git clone https://github.com/vishal-raaj-dnd/gemini-okf-compiler.git
cd gemini-okf-compiler
pip install -r requirements.txt
```

### 3. Configure Credentials
```bash
cp .env.template .env
# Open .env and set your GEMINI_API_KEY
```

---

## 💻 Usage

### 1. Guided Interactive Mode (Recommended)
If you do not want to use command line flags, simply run the tool directly. It will guide you step-by-step:
```bash
python main.py
```
This guided mode only requires two quick inputs:
1. **The path to your file or folder** (you can drag and drop it into the terminal).
2. **Your Gemini API Key** (it will auto-detect it if set in `.env`, or prompt you to paste it temporarily).

OmniOKF compiles everything automatically using default configurations (output folder `.okf`, heading split `##`).

---

### 2. CLI Mode (For Advanced Users)
You can also bypass the prompts and compile files directly using command line flags:

**Ingest single documents:**
```bash
# Compile a PDF
python main.py --input manuals/onboarding.pdf --output-dir .okf

# Compile a Word File
python main.py --input specifications/spec_doc.docx --output-dir .okf

# Compile a Spreadsheet
python main.py --input finance/pl-report.xlsx --output-dir .okf
```

**Ingest a directory of mixed files:**
```bash
python main.py --input ./raw_corporate_documents --output-dir .okf
```
*OmniOKF will scan, convert, split, and cross-link all `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.html`, and `.md` files in the folder.*

---

### Command Line Arguments
- `--input`, `-i`: Path to the input file or directory containing files (required).
- `--output-dir`, `-o`: Directory where the OKF bundle will be created (default: `.okf`).
- `--split-level`, `-s`: The header markdown prefix to split at (default: `##`).

---

## 📂 OKF Bundle Structure

The compiler structures your documents into this specification:
```
.okf/
├── index.md             # Graph index listing all concepts and types
├── guides/              # Category directories
│   ├── onboarding.md
│   └── setup.md
└── processes/
    └── incident-response.md
```

Each concept file is output with OKF-compliant YAML frontmatter:
```markdown
---
type: process
title: Incident Response Protocol
description: Steps to take when an alert is triggered in the production environment.
tags: [ops, incident, engineering]
timestamp: 2026-07-09T03:20:00Z
---
# Incident Response Protocol

Content of the document goes here...
```

---

## ⚡ Premium Features

### 1. Incremental Compilation (Caching)
To save LLM tokens and make compilation instant for large knowledge bases, OmniOKF features native caching:
- The compiler computes a cryptographic MD5 hash of each document.
- It stores this layout and concept metadata in a local `.okf/manifest.json` file.
- On subsequent runs, if a file has not changed, it skips splitting and LLM parsing entirely and loads it instantly from the cache, reducing execution time to milliseconds and API cost to zero!

### 2. Live Knowledge Graph Visualization
Every compilation automatically generates a visual network flowchart of your knowledge base:
- The relationships are extracted from relative markdown cross-links.
- A native **Mermaid** flowchart block is injected directly into `.okf/index.md`.
- GitHub and most markdown viewers will automatically render this block as an interactive graphical network, letting developers see their document dependencies visually!

---

## 🤖 GitHub Action Integration

To automate compilation on push events in your repository, configure the workflow located in `.github/workflows/okf-generator.yml`. Pushing new documents to GitHub will automatically compile them and commit the updated `.okf/` folder.

---

## 📄 License
Licensed under the MIT License. See [LICENSE](LICENSE) for details.
