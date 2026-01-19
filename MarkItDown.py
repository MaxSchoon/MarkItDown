#!/usr/bin/env python3

import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
import argparse
import base64
import io
import asyncio
from datetime import datetime

# Optional imports for OlmOCR
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    from PIL import Image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

# Load environment variables
if DOTENV_AVAILABLE:
    load_dotenv()

# Configuration
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY", "")
DEEPINFRA_API_KEY_2 = os.getenv("DEEPINFRA_API_KEY_2", "")  # Optional second API key
USE_OLMOCR = os.getenv("USE_OLMOCR", "true").lower() == "true"
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
OLMOCR_MODEL = "allenai/olmOCR-2-7B-1025"

# Collect all available API keys
API_KEYS = [k for k in [DEEPINFRA_API_KEY, DEEPINFRA_API_KEY_2] if k]

# OCR settings optimized for annual reports and financial documents
OCR_DPI = int(os.getenv("OCR_DPI", "200"))  # Higher DPI for better text clarity
OCR_MAX_TOKENS = int(os.getenv("OCR_MAX_TOKENS", "8192"))  # More tokens for dense pages
OCR_IMAGE_FORMAT = os.getenv("OCR_IMAGE_FORMAT", "PNG")  # PNG for lossless quality
# With multiple API keys, we can use 100 concurrent per key (200 total for 2 keys)
OCR_CONCURRENCY_PER_KEY = int(os.getenv("OCR_CONCURRENCY_PER_KEY", "100"))
OCR_CONCURRENCY = OCR_CONCURRENCY_PER_KEY * len(API_KEYS) if API_KEYS else 50

# Prompt for extracting table of contents structure
TOC_EXTRACTION_PROMPT = """Look at this page. Does it show a TABLE OF CONTENTS with chapter names and page numbers?

If YES, list ONLY the MAIN CHAPTER TITLES (the top-level sections, not subsections).
Format each chapter on its own line starting with ">>>" like this:
>>> Chapter Name Here

If this is NOT a table of contents page, respond with only: NOT_A_TOC_PAGE

Example good response for a TOC page:
>>> Message from the CEO
>>> Company Overview
>>> Financial Statements
>>> Risk Management
>>> Governance

Remember: Only list the MAIN chapters/sections you see in the table of contents. Start each with >>>"""

# Optimized prompt for financial documents and annual reports
OCR_PROMPT = """Extract all text from this financial document page into well-structured markdown.

Output requirements:
- Headings: Mark section titles with # ## ### based on visual prominence. Large/bold text = #, medium sections = ##, small sections = ###
- Tables: Convert to markdown tables with | separators or HTML tables for complex layouts
- Lists: Use - for bullets, 1. 2. 3. for numbered
- Numbers: Preserve exact values including currency symbols (€, $, £), decimals, percentages
- Structure: Maintain logical reading order and paragraph breaks
- Accuracy: Extract every word and number precisely

Return only the markdown content, no explanations."""

# Extended prompt with document structure context (used when TOC is available)
OCR_PROMPT_WITH_STRUCTURE = """Extract all text from this financial document page into well-structured markdown.

Output requirements:
- Headings: Mark section titles with # ## ### based on visual prominence. Large/bold titles = #, sections = ##, subsections = ###. {heading_context}
- Tables: Convert to markdown tables with | separators or HTML tables for complex layouts
- Lists: Use - for bullets, 1. 2. 3. for numbered
- Numbers: Preserve exact values including currency symbols (€, $, £), decimals, percentages
- Structure: Maintain logical reading order and paragraph breaks
- Accuracy: Extract every word and number precisely

Return only the markdown content, no explanations."""

# Default heading context (without document structure)
DEFAULT_HEADING_CONTEXT = "Use # for major titles, ## for sections, ### for subsections"

# Global flag to disable OCR (set via CLI)
DISABLE_OCR = False


def is_olmocr_available():
    """Check if OlmOCR is available and configured"""
    if DISABLE_OCR:
        return False
    if not USE_OLMOCR:
        return False
    if not DEEPINFRA_API_KEY:
        return False
    if not OPENAI_AVAILABLE:
        return False
    if not PDF2IMAGE_AVAILABLE:
        return False
    return True


def get_deepinfra_client():
    """Create an OpenAI-compatible client for DeepInfra"""
    return OpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url=DEEPINFRA_BASE_URL,
    )


def get_async_deepinfra_client():
    """Create an async OpenAI-compatible client for DeepInfra"""
    return AsyncOpenAI(
        api_key=DEEPINFRA_API_KEY,
        base_url=DEEPINFRA_BASE_URL,
    )


def get_async_deepinfra_clients():
    """Create async clients for all available API keys"""
    return [
        AsyncOpenAI(api_key=key, base_url=DEEPINFRA_BASE_URL)
        for key in API_KEYS
    ]


def image_to_base64(image, format=None, quality=95):
    """Convert a PIL Image to base64 string"""
    if format is None:
        format = OCR_IMAGE_FORMAT
    buffer = io.BytesIO()
    if format == "JPEG" and image.mode == "RGBA":
        image = image.convert("RGB")
    if format == "PNG":
        image.save(buffer, format=format, optimize=True)
    else:
        image.save(buffer, format=format, quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def convert_pdf_page_with_olmocr(client, image, page_num, verbose=False):
    """Convert a single PDF page image to markdown using OlmOCR (sync version)"""
    try:
        base64_image = image_to_base64(image)
        mime_type = "image/png" if OCR_IMAGE_FORMAT == "PNG" else "image/jpeg"

        response = client.chat.completions.create(
            model=OLMOCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": OCR_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=OCR_MAX_TOKENS,
        )

        return response.choices[0].message.content
    except Exception as e:
        if verbose:
            print(f"Error processing page {page_num} with OlmOCR: {str(e)}")
        return None


async def convert_pdf_page_with_olmocr_async(client, base64_image, page_num, semaphore, prompt=None, verbose=False):
    """Convert a single PDF page image to markdown using OlmOCR (async version)"""
    async with semaphore:
        try:
            mime_type = "image/png" if OCR_IMAGE_FORMAT == "PNG" else "image/jpeg"
            ocr_prompt = prompt if prompt else OCR_PROMPT

            response = await client.chat.completions.create(
                model=OLMOCR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": ocr_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=OCR_MAX_TOKENS,
            )

            if verbose:
                print(f"  Completed page {page_num}", flush=True)

            return (page_num, response.choices[0].message.content)
        except Exception as e:
            if verbose:
                print(f"  Error on page {page_num}: {str(e)}", flush=True)
            return (page_num, None)


def get_pdf_page_count(pdf_path):
    """Get the total number of pages in a PDF without loading all pages"""
    from pdf2image.pdf2image import pdfinfo_from_path
    info = pdfinfo_from_path(pdf_path)
    return info["Pages"]


def extract_toc_from_pages(client, images, verbose=False):
    """Extract table of contents from the first few pages of a PDF"""
    toc_content = []

    for i, image in enumerate(images):
        page_num = i + 1
        try:
            base64_image = image_to_base64(image)
            mime_type = "image/png" if OCR_IMAGE_FORMAT == "PNG" else "image/jpeg"

            response = client.chat.completions.create(
                model=OLMOCR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": TOC_EXTRACTION_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=2048,
            )

            result = response.choices[0].message.content.strip()
            # Only include if it contains actual TOC markers (>>>)
            if result and ">>>" in result:
                toc_content.append(result)
                if verbose:
                    print(f"  Found TOC structure on page {page_num}", flush=True)
            elif verbose and "NOT_A_TOC" not in result.upper():
                pass  # Silently skip non-TOC pages

        except Exception as e:
            if verbose:
                print(f"  Error extracting TOC from page {page_num}: {str(e)}", flush=True)

    return "\n".join(toc_content) if toc_content else None


def parse_toc_structure(toc_text):
    """Parse extracted TOC text into a hierarchical structure"""
    if not toc_text:
        return None

    structure = {
        "chapters": [],
        "sections": {},  # Maps section names to their chapter
        "section_pages": {}  # Maps page numbers to section info
    }

    for line in toc_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip non-TOC indicators
        if "NOT_A_TOC" in line.upper() or "NO_TOC" in line.upper():
            continue

        # Parse simple >>> format (primary format)
        if line.startswith(">>>"):
            chapter_name = line.replace(">>>", "").strip()
            if chapter_name and chapter_name not in structure["chapters"]:
                structure["chapters"].append(chapter_name)
            continue

        # Also support MAIN_SECTION format
        if line.startswith("MAIN_SECTION:"):
            chapter_name = line.replace("MAIN_SECTION:", "").strip()
            if chapter_name and chapter_name not in structure["chapters"]:
                structure["chapters"].append(chapter_name)
            continue

        # Support CHAPTER format
        if line.startswith("CHAPTER:"):
            chapter_name = line.replace("CHAPTER:", "").strip()
            if chapter_name and chapter_name not in structure["chapters"]:
                structure["chapters"].append(chapter_name)

    return structure if structure["chapters"] else None


def create_heading_context(toc_structure):
    """Create heading context based on TOC structure"""
    if not toc_structure:
        return DEFAULT_HEADING_CONTEXT

    # Build chapter list for context
    chapters_list = ", ".join(toc_structure["chapters"][:6])

    # Keep the instruction simple - just identify headings normally, post-processing will normalize levels
    return f"Use # for major section titles, ## for subsections, ### for sub-subsections. Document structure reference: {chapters_list}"


def normalize_headings(markdown_text, toc_structure):
    """Post-process markdown to normalize heading levels based on TOC structure.

    This function does two things:
    1. Converts plain text lines that match chapter names into H1 headings
    2. Normalizes existing heading levels based on whether they match chapter names
    """
    if not toc_structure or not markdown_text:
        return markdown_text

    # Create lowercase chapter names for matching
    chapter_names_lower = set(ch.lower().strip() for ch in toc_structure["chapters"])

    lines = markdown_text.split("\n")
    result_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        stripped_lower = stripped.lower()

        # Check if this is a heading line
        if line.startswith("#"):
            # Count heading level
            level = 0
            for char in line:
                if char == "#":
                    level += 1
                else:
                    break

            # Extract heading text
            heading_text = line[level:].strip()
            heading_text_lower = heading_text.lower().strip()

            # Check if this heading matches a chapter name
            is_chapter = heading_text_lower in chapter_names_lower

            if level == 1:  # H1 heading
                if is_chapter:
                    # Keep as H1 - it's a main chapter
                    result_lines.append(line)
                else:
                    # Demote to H2 - it's not a main chapter
                    result_lines.append("## " + heading_text)
            elif level == 2:  # H2 heading
                if is_chapter:
                    # Promote to H1 - it's a main chapter
                    result_lines.append("# " + heading_text)
                else:
                    result_lines.append(line)
            else:
                # Keep other heading levels as-is
                result_lines.append(line)
        # Check if plain text line matches a chapter name (convert to H1)
        elif stripped_lower in chapter_names_lower and len(stripped) < 80:
            result_lines.append("# " + stripped)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)


async def process_batch_async(clients, images, batch_start, total_pages, semaphore, toc_structure=None, verbose=False):
    """Process a batch of images concurrently using multiple API clients"""
    # Convert images to base64 first (this is CPU-bound, done synchronously)
    base64_images = []
    for i, image in enumerate(images):
        page_num = batch_start + i
        base64_images.append((page_num, image_to_base64(image)))

    # Create prompt based on whether we have TOC structure
    if toc_structure:
        heading_context = create_heading_context(toc_structure)
        page_prompt = OCR_PROMPT_WITH_STRUCTURE.format(heading_context=heading_context)
    else:
        page_prompt = OCR_PROMPT

    # Create async tasks distributed across clients (round-robin)
    tasks = []
    for idx, (page_num, b64_img) in enumerate(base64_images):
        # Distribute requests across clients
        client = clients[idx % len(clients)]

        tasks.append(
            convert_pdf_page_with_olmocr_async(client, b64_img, page_num, semaphore, page_prompt, verbose)
        )

    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)

    return results


def convert_pdf_with_olmocr(pdf_path, verbose=False, batch_size=100):
    """Convert a PDF file to markdown using OlmOCR with parallel API calls and structure-aware headings"""
    try:
        if verbose:
            print(f"Using OlmOCR for {pdf_path}", flush=True)
            print(f"  Settings: DPI={OCR_DPI}, Format={OCR_IMAGE_FORMAT}, MaxTokens={OCR_MAX_TOKENS}", flush=True)
            print(f"  API keys: {len(API_KEYS)}, Parallel requests: {OCR_CONCURRENCY} concurrent", flush=True)

        # Get total page count without loading all pages
        total_pages = get_pdf_page_count(pdf_path)

        if verbose:
            print(f"PDF has {total_pages} pages (processing in batches of {batch_size} with {OCR_CONCURRENCY} parallel API calls)", flush=True)

        # ========== PASS 1: Extract Table of Contents ==========
        toc_structure = None
        toc_pages_to_scan = min(10, total_pages)  # Scan first 10 pages for TOC

        if verbose:
            print(f"Pass 1: Extracting document structure from first {toc_pages_to_scan} pages...", flush=True)

        try:
            # Load first few pages to extract TOC
            toc_images = convert_from_path(
                pdf_path,
                dpi=OCR_DPI,
                first_page=1,
                last_page=toc_pages_to_scan
            )

            # Extract TOC using sync client
            sync_client = get_deepinfra_client()
            toc_text = extract_toc_from_pages(sync_client, toc_images, verbose)

            if toc_text:
                toc_structure = parse_toc_structure(toc_text)
                if toc_structure and verbose:
                    print(f"  Found {len(toc_structure['chapters'])} chapters in document structure", flush=True)
                    for ch in toc_structure['chapters'][:5]:
                        print(f"    - {ch}", flush=True)
                    if len(toc_structure['chapters']) > 5:
                        print(f"    ... and {len(toc_structure['chapters']) - 5} more", flush=True)
            elif verbose:
                print("  No table of contents found, using default heading rules", flush=True)

            del toc_images
        except Exception as e:
            if verbose:
                print(f"  TOC extraction failed: {str(e)}, using default heading rules", flush=True)

        # ========== PASS 2: Convert Pages with Structure Context ==========
        if verbose:
            print(f"Pass 2: Converting pages with {'structure-aware' if toc_structure else 'default'} heading rules...", flush=True)

        # Results dictionary to maintain page order
        results_dict = {}

        # Create async clients and semaphore
        async def run_parallel_conversion():
            clients = get_async_deepinfra_clients()
            semaphore = asyncio.Semaphore(OCR_CONCURRENCY)

            try:
                # Process pages in batches to manage memory
                for batch_start in range(1, total_pages + 1, batch_size):
                    batch_end = min(batch_start + batch_size - 1, total_pages)

                    if verbose:
                        print(f"Loading pages {batch_start}-{batch_end}...", flush=True)

                    # Load this batch of pages
                    images = convert_from_path(
                        pdf_path,
                        dpi=OCR_DPI,
                        first_page=batch_start,
                        last_page=batch_end
                    )

                    if verbose:
                        print(f"Processing pages {batch_start}-{batch_end} in parallel...", flush=True)

                    # Process batch with parallel API calls across multiple clients
                    # Pass TOC structure for heading context
                    batch_results = await process_batch_async(
                        clients, images, batch_start, total_pages, semaphore, toc_structure, verbose
                    )

                    # Store results
                    for page_num, content in batch_results:
                        results_dict[page_num] = content

                    # Clear images from memory
                    del images

                    if verbose:
                        print(f"Completed pages {batch_start}-{batch_end} ({batch_end}/{total_pages})", flush=True)
            finally:
                # Close async clients to avoid event loop warnings
                for client in clients:
                    await client.close()

        # Run the async conversion
        asyncio.run(run_parallel_conversion())

        # Build markdown output in page order
        markdown_parts = []
        for page_num in range(1, total_pages + 1):
            content = results_dict.get(page_num)
            if content:
                if total_pages > 1:
                    markdown_parts.append(f"<!-- Page {page_num} -->\n\n{content}")
                else:
                    markdown_parts.append(content)
            else:
                markdown_parts.append(f"<!-- Page {page_num}: OCR failed -->")

        final_output = "\n\n---\n\n".join(markdown_parts)

        # Post-process to normalize heading levels based on TOC structure
        if toc_structure:
            if verbose:
                print("Normalizing heading levels based on document structure...", flush=True)
            final_output = normalize_headings(final_output, toc_structure)

        return final_output
    except Exception as e:
        if verbose:
            print(f"OlmOCR failed for {pdf_path}: {str(e)}", flush=True)
        return None


def convert_file_to_markdown_string(input_file_path, verbose=False):
    """Convert a single file to markdown and return as string"""
    ext = os.path.splitext(input_file_path)[1].lower()

    # Use OlmOCR for PDFs if available
    if ext == ".pdf" and is_olmocr_available():
        result = convert_pdf_with_olmocr(input_file_path, verbose)
        if result is not None:
            return result
        if verbose:
            print(f"Falling back to markitdown for {input_file_path}")

    # Fall back to markitdown CLI
    try:
        result = subprocess.run(['markitdown', input_file_path],
                               capture_output=True,
                               text=True,
                               check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise Exception(f"markitdown error: {e.stderr}")
    except Exception as e:
        raise Exception(str(e))

# Add argument parsing
def parse_arguments():
    parser = argparse.ArgumentParser(description="Convert files to Markdown using Microsoft's MarkItDown tool")
    parser.add_argument("-i", "--input", dest="input_dir", default="input",
                        help="Input directory containing files to convert (default: 'input')")
    parser.add_argument("-o", "--output", dest="output_dir", default="output",
                        help="Output directory for converted Markdown files (default: 'output')")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output")
    parser.add_argument("--no-ocr", action="store_true",
                        help="Disable OlmOCR and use markitdown for all files including PDFs")
    return parser.parse_args()

def convert_file_to_markdown(input_file_path, output_file_path, verbose=False):
    """Convert a single file to markdown using OlmOCR for PDFs or MarkItDown for other formats"""
    try:
        content = convert_file_to_markdown_string(input_file_path, verbose)

        # Write the output to the specified file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        if verbose:
            print(f"Successfully converted {input_file_path} to {output_file_path}")
        return True
    except Exception as e:
        print(f"Error converting {input_file_path}: {str(e)}")
        return False

def process_zip_file(zip_file_path, output_file_path, verbose=False):
    """Extract zip file contents and convert to a single markdown file"""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extract zip contents to temp directory
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        if verbose:
            print(f"Extracted {zip_file_path} to temporary directory")
        
        # Process each file in the extracted directory
        all_markdown_content = []
        file_list = []
        for root, _, files in os.walk(temp_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Skip hidden files
                if os.path.basename(file_path).startswith('.'):
                    continue
                file_list.append((file_path, os.path.relpath(file_path, temp_dir)))
        for idx, (file_path, relative_path) in enumerate(file_list):
            if verbose:
                print(f"Processing {relative_path}")
            try:
                # Convert file to markdown using the helper
                content = convert_file_to_markdown_string(file_path, verbose)
                # Add file header and content
                all_markdown_content.append(f"# file {idx+1} - {relative_path}\n\n{content}\n\n")
            except Exception as e:
                all_markdown_content.append(f"# file {idx+1} - {relative_path}\n\nError converting file: {str(e)}\n\n")
        
        # Combine all content and write to output file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Contents of {os.path.basename(zip_file_path)}\n\n")
            f.write("".join(all_markdown_content))
        
        if verbose:
            print(f"Successfully converted zip file {zip_file_path} to {output_file_path}")
        return True
    except Exception as e:
        print(f"Error processing zip file {zip_file_path}: {str(e)}")
        return False
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir)

def combine_files_to_markdown(folder_path, output_file_path, verbose=False):
    """Convert all files in a folder to a single markdown file"""
    try:
        # Process each file in the folder
        all_markdown_content = []
        folder_name = os.path.basename(folder_path)
        
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith('.')]
        
        if not files:
            if verbose:
                print(f"No files found in {folder_path}")
            return False
        
        for idx, filename in enumerate(files):
            file_path = os.path.join(folder_path, filename)
            
            if verbose:
                print(f"Processing {filename} in folder {folder_name}")
            
            try:
                # Convert file to markdown using the helper
                content = convert_file_to_markdown_string(file_path, verbose)

                # Add file header and content
                all_markdown_content.append(f"# file {idx+1} - {filename}\n\n{content}\n\n")
            except Exception as e:
                all_markdown_content.append(f"# file {idx+1} - {filename}\n\nError converting file: {str(e)}\n\n")
            # Add delimiter if not the last file
            if idx < len(files) - 1:
                all_markdown_content.append('---\n\n')
        
        # Combine all content and write to output file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Contents of folder: {folder_name}\n\n")
            f.write("".join(all_markdown_content))
        
        if verbose:
            print(f"Successfully combined folder {folder_path} to {output_file_path}")
        return True
    except Exception as e:
        print(f"Error processing folder {folder_path}: {str(e)}")
        return False

def has_subfolders(folder_path):
    """Check if a folder contains any subfolders"""
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            return True
    return False

def process_directory(input_dir, output_dir, base_input_dir, base_output_dir, current_date, verbose=False):
    """Recursively process a directory"""
    # Check if directory has subfolders
    has_children = has_subfolders(input_dir)
    
    if has_children:
        # Process each subfolder recursively
        for item in os.listdir(input_dir):
            item_path = os.path.join(input_dir, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                # Check if this subfolder is a leaf directory
                if not has_subfolders(item_path):
                    # This is a leaf directory, skip creating a subfolder and process it directly
                    folder_name = os.path.basename(item_path)
                    output_filename = f"{folder_name}_{current_date}.md"
                    output_file_path = os.path.join(output_dir, output_filename)
                    
                    if verbose:
                        print(f"Processing nested leaf folder {folder_name} -> {output_filename} (directly in parent)")
                    
                    combine_files_to_markdown(item_path, output_file_path, verbose)
                else:
                    # Create relative output path for non-leaf folders
                    rel_path = os.path.relpath(item_path, base_input_dir)
                    output_subdir = os.path.join(base_output_dir, rel_path)
                    os.makedirs(output_subdir, exist_ok=True)
                    
                    # Process this subfolder
                    process_directory(item_path, output_subdir, base_input_dir, base_output_dir, current_date, verbose)
                
        # Also process individual files in this directory
        for filename in os.listdir(input_dir):
            input_file_path = os.path.join(input_dir, filename)
            
            # Skip directories and hidden files
            if os.path.isdir(input_file_path) or filename.startswith('.'):
                continue
            
            # Create output filename with date
            name_without_ext, ext = os.path.splitext(filename)
            output_filename = f"{name_without_ext}_{current_date}.md"
            
            # Determine relative path for output
            rel_dir = os.path.relpath(input_dir, base_input_dir)
            output_subdir = os.path.join(base_output_dir, rel_dir)
            os.makedirs(output_subdir, exist_ok=True)
            
            output_file_path = os.path.join(output_subdir, output_filename)
            
            if verbose:
                print(f"Processing individual file {filename} -> {output_filename}")
            
            # Process the file based on extension
            if ext.lower() == '.zip':
                process_zip_file(input_file_path, output_file_path, verbose)
            else:
                convert_file_to_markdown(input_file_path, output_file_path, verbose)
                
    else:
        # This is a leaf directory, combine all files into one markdown file
        # Get the parent directory path to place the file one level up
        parent_dir = os.path.dirname(output_dir)
        folder_name = os.path.basename(input_dir)
        output_filename = f"{folder_name}_{current_date}.md"
        
        # Place the output file in the parent directory instead of the leaf directory
        output_file_path = os.path.join(parent_dir, output_filename)
        
        if verbose:
            print(f"Processing leaf folder {folder_name} -> {output_filename} (placing in parent directory)")
        
        combine_files_to_markdown(input_dir, output_file_path, verbose)

def process_all_files(input_dir, output_dir, verbose=False):
    """Process all files in the input directory"""
    # Get the current script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Handle relative paths
    if not os.path.isabs(input_dir):
        input_dir = os.path.join(script_dir, input_dir)
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(script_dir, output_dir)
    
    # Verify input directory exists
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return False
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    if verbose:
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")
    
    # Get current date for filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Check if input directory is empty
    if not os.listdir(input_dir):
        print(f"Warning: Input directory '{input_dir}' is empty.")
        return False
    
    # Process root level items
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        
        # Skip hidden files/directories
        if item.startswith('.'):
            if verbose:
                print(f"Skipping hidden item: {item}")
            continue
        
        if os.path.isdir(item_path):
            # Check if this is a leaf directory (no subfolders)
            if not has_subfolders(item_path):
                # This is a leaf directory, process it directly
                folder_name = os.path.basename(item_path)
                output_filename = f"{folder_name}_{current_date}.md"
                output_file_path = os.path.join(output_dir, output_filename)
                
                if verbose:
                    print(f"Processing leaf folder {folder_name} -> {output_filename} (directly in parent)")
                
                combine_files_to_markdown(item_path, output_file_path, verbose)
            else:
                # Create corresponding output directory for non-leaf folders
                output_subdir = os.path.join(output_dir, item)
                os.makedirs(output_subdir, exist_ok=True)
                
                # Process this directory
                process_directory(item_path, output_subdir, input_dir, output_dir, current_date, verbose)
        else:
            # Process single file
            name_without_ext, ext = os.path.splitext(item)
            output_filename = f"{name_without_ext}_{current_date}.md"
            output_file_path = os.path.join(output_dir, output_filename)
            
            if verbose:
                print(f"Processing root file {item} -> {output_filename}")
            
            # Process the file based on extension
            if ext.lower() == '.zip':
                process_zip_file(item_path, output_file_path, verbose)
            else:
                convert_file_to_markdown(item_path, output_file_path, verbose)
    
    return True

if __name__ == "__main__":
    args = parse_arguments()

    # Set OCR flag based on CLI argument
    if args.no_ocr:
        DISABLE_OCR = True

    # Print OCR status in verbose mode
    if args.verbose:
        if is_olmocr_available():
            print("OlmOCR is available and will be used for PDFs")
        else:
            reasons = []
            if DISABLE_OCR:
                reasons.append("disabled via --no-ocr")
            elif not USE_OLMOCR:
                reasons.append("USE_OLMOCR=false in .env")
            elif not DEEPINFRA_API_KEY:
                reasons.append("DEEPINFRA_API_KEY not set")
            elif not OPENAI_AVAILABLE:
                reasons.append("openai package not installed")
            elif not PDF2IMAGE_AVAILABLE:
                reasons.append("pdf2image/Pillow not installed")
            print(f"OlmOCR not available ({', '.join(reasons)}), using markitdown for PDFs")

    process_all_files(args.input_dir, args.output_dir, args.verbose)