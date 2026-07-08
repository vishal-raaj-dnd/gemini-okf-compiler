# OKF Compiler: PDF-to-Markdown to OKF (Open Knowledge Format)

OKF Compiler is a two-layer engine designed to convert unstructured documents (such as corporate handbooks, PDFs, and manuals) into agent-friendly, highly structured **Open Knowledge Format (OKF)** bundles.

By leveraging top-tier open-source document parsers (like **Marker**) for layout extraction (Layer 1) and lightweight LLMs for semantic concept compilation (Layer 2), OKF Compiler produces rich, cross-linked, self-describing markdown directories ready for AI agents at an extremely low token cost.

---

## 🌟 The Two-Layer Architecture

Instead of running a heavy, expensive LLM vision model to read a raw PDF and extract structures directly, this tool uses a hybrid approach:

1. **Layer 1: Structural Parser (External)**
   - Use an advanced layout-aware open-source parser like [Marker](https://github.com/VikParuchuri/marker) or [MinerU](https://github.com/opendatalab/MinerU) to convert raw PDF documents into clean, flat, layout-accurate standard Markdown.
   - Handles multi-column layouts, table extraction, and image extraction at zero cost.

2. **Layer 2: OKF Transformation Engine (This Tool)**
   - **Heuristic Concept Splitter**: Parses the flat Markdown file and splits it along header levels (`#`, `##`).
   - **Semantic Metadata Extractor**: Employs a fast, cost-effective LLM (like Gemini Flash) to parse each chunk, determine its OKF concept type, and generate standard YAML frontmatter.
   - **Semantic Cross-Linker**: Scans the compiled catalog, identifies terms in other documents, and injects relative Markdown links to construct a knowledge graph.
   - **Directory & Index Generator**: Restructures the files into subfolders and generates the `index.md` entry point.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.9+
- A Google Gemini API Key (get one from [Google AI Studio](https://aistudio.google.com/))

### 2. Install Dependencies
Clone this repository and install the dependencies:
```bash
git clone https://github.com/yourusername/OKF-compiler.git
cd OKF-compiler
pip install -r requirements.txt
```

### 3. Configure Credentials
Copy the environment template and set your API key:
```bash
cp .env.template .env
# Edit .env and enter your GEMINI_API_KEY
```

---

## 🛠️ Usage

### Step 1: Convert PDF to Markdown (Layer 1)
To convert raw PDFs into flat Markdown files, we recommend using **Marker** (an advanced layout-aware tool that handles columns, tables, and OCR).

**For a single PDF:**
```bash
# Install marker-pdf (requires PyTorch)
pip install marker-pdf

# Convert a single PDF to flat Markdown
marker_single path/to/your_document.pdf --output_dir ./temp_output
```
*Outputs: `./temp_output/your_document.md`*

**For a directory of hundreds of PDFs:**
```bash
# Convert an entire folder of PDFs in parallel
marker path/to/pdf_folder ./temp_markdown_folder --workers 4
```
*Outputs a folder full of flat `.md` files.*

---

### Step 2: Compile Documents (MD, DOCX) to OKF (Layer 2)
Pass a flat Markdown file, a Word document (`.docx`), or a **directory containing Markdown/DOCX files** to the OKF Compiler. The engine splits the documents, extracts metadata via Gemini, resolves naming collisions, and cross-links all concepts into a unified OKF knowledge graph.

*Note: `.docx` files are dynamically translated to Markdown in memory during processing.*

**Compile a single file (MD or DOCX):**
```bash
python main.py --input ./temp_output/your_document.md --output-dir .okf
# OR
python main.py --input path/to/report.docx --output-dir .okf
```

**Compile a directory (Batch Mode processing all MD and DOCX files):**
```bash
python main.py --input ./temp_markdown_folder --output-dir .okf
```

---

### Command Line Arguments
- `--input`, `-i`: Path to the input Markdown/DOCX file **or** directory containing Markdown and/or DOCX files (required).
- `--output-dir`, `-o`: Directory where the OKF bundle will be created (default: `.okf`).
- `--split-level`, `-s`: The header markdown prefix to split at (default: `##`).

---

## 📂 OKF Bundle Structure

The compiled output follows the Open Knowledge Format specification:
```
.okf/
├── index.md             # Graph index listing all concepts and types
└── concepts/            # Auto-generated concept categories
    ├── incident-response.md
    ├── onboarding-guide.md
    └── table-schema.md
```

Each generated markdown file contains OKF-compliant YAML frontmatter:
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

## 🛠️ GitHub Action Integration

To automate the compilation pipeline on push, place the workflow located in `.github/workflows/okf-generator.yml` in your target repository's `.github/workflows` folder.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
