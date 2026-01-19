# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MarkItDown is a Python utility that batch-converts documents (PDF, DOCX, PPTX, XLSX) and ZIP archives to Markdown using Microsoft's `markitdown` CLI tool. It adds directory structure handling and file combining logic on top of the base tool.

## Commands

```bash
# Run with defaults (input/ → output/)
python MarkItDown.py

# Custom directories
python MarkItDown.py -i /path/to/input -o /path/to/output

# Verbose mode
python MarkItDown.py -v
```

**Dependencies**: `pip install -r requirements.txt`

## Development Setup

```bash
# Install Python LSP for better code intelligence
pip install python-lsp-server

# Install all dependencies
pip install -r requirements.txt

# For OlmOCR PDF support, also install poppler
brew install poppler  # macOS
# apt install poppler-utils  # Ubuntu/Debian
```

## Architecture

Single-file script (`MarkItDown.py`) with these core functions:

### Core Processing
- `process_all_files()` - Entry point, validates paths, iterates root-level items
- `process_directory()` - Recursive directory processor, decides between combining vs preserving structure
- `combine_files_to_markdown()` - Merges all files in a leaf folder into one output file
- `process_zip_file()` - Extracts ZIP to temp dir, converts all contents, combines with headers
- `convert_file_to_markdown()` - Writes converted content to file
- `convert_file_to_markdown_string()` - Core conversion helper, routes to OlmOCR or markitdown
- `has_subfolders()` - Determines if a folder is a "leaf" (no subfolders)

### OlmOCR Integration
- `is_olmocr_available()` - Checks if API key and dependencies are configured
- `get_deepinfra_client()` - Creates OpenAI-compatible client for DeepInfra
- `image_to_base64()` - Converts PIL Image to base64 for API
- `convert_pdf_page_with_olmocr()` - Processes single page via vision API
- `convert_pdf_with_olmocr()` - Orchestrates full PDF conversion with page-by-page OCR

## Key Design Decisions

**Leaf folder detection**: Folders with no subfolders get all their files combined into a single Markdown file. Folders with subfolders preserve structure recursively.

**Machine-readable headers**: Combined files use `# file N - filename` headers (1-indexed) to allow programmatic extraction. Regex pattern: `^# file (\d+) - (.+)$`

**Output naming**: All outputs include date stamp: `{name}_{YYYY-MM-DD}.md`

**ZIP handling**: Extracted to temp directory, processed recursively, cleaned up after. All contents combined into single output with relative paths preserved in headers.

**Hidden files**: Items starting with `.` are skipped throughout.

**OlmOCR for PDFs**: When configured, PDFs are converted using OlmOCR via DeepInfra API for better OCR quality. Falls back to markitdown if OlmOCR fails or isn't configured. Other formats (DOCX, PPTX, XLSX) always use markitdown.

## OlmOCR Configuration

OlmOCR is optional and requires:
1. DeepInfra API key in `.env` file
2. Python packages: `openai`, `pdf2image`, `Pillow`
3. System dependency: `poppler` (for PDF to image conversion)

```bash
# Create .env from example
cp .env.example .env
# Edit .env and add your DeepInfra API key
```

Disable OlmOCR temporarily with `--no-ocr` flag or permanently by setting `USE_OLMOCR=false` in `.env`.

## Documentation Maintenance

**Keep README.md in sync with the codebase.** When making changes to MarkItDown.py, update README.md to reflect:
- New or changed CLI flags (update the options table)
- New features or capabilities
- Changed prerequisites or dependencies
- Modified directory structure handling behavior
- Updated usage examples if workflows change
