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
from datetime import datetime

# Optional imports for OlmOCR
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

try:
    from openai import OpenAI
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
USE_OLMOCR = os.getenv("USE_OLMOCR", "true").lower() == "true"
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
OLMOCR_MODEL = "allenai/olmOCR-2-7B-1025"

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


def image_to_base64(image, format="JPEG", quality=85):
    """Convert a PIL Image to base64 string"""
    buffer = io.BytesIO()
    if image.mode == "RGBA":
        image = image.convert("RGB")
    image.save(buffer, format=format, quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def convert_pdf_page_with_olmocr(client, image, page_num, verbose=False):
    """Convert a single PDF page image to markdown using OlmOCR"""
    try:
        base64_image = image_to_base64(image)

        response = client.chat.completions.create(
            model=OLMOCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "OCR this document page to markdown. Use # for headings, - for lists. Preserve document structure. Output only the extracted content, no commentary."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
        )

        return response.choices[0].message.content
    except Exception as e:
        if verbose:
            print(f"Error processing page {page_num} with OlmOCR: {str(e)}")
        return None


def convert_pdf_with_olmocr(pdf_path, verbose=False):
    """Convert a PDF file to markdown using OlmOCR"""
    try:
        if verbose:
            print(f"Using OlmOCR for {pdf_path}")

        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=150)

        if verbose:
            print(f"Converted PDF to {len(images)} page images")

        client = get_deepinfra_client()
        markdown_parts = []

        for i, image in enumerate(images):
            page_num = i + 1
            if verbose:
                print(f"Processing page {page_num}/{len(images)}")

            page_content = convert_pdf_page_with_olmocr(client, image, page_num, verbose)

            if page_content:
                if len(images) > 1:
                    markdown_parts.append(f"<!-- Page {page_num} -->\n\n{page_content}")
                else:
                    markdown_parts.append(page_content)
            else:
                markdown_parts.append(f"<!-- Page {page_num}: OCR failed -->")

        return "\n\n---\n\n".join(markdown_parts)
    except Exception as e:
        if verbose:
            print(f"OlmOCR failed for {pdf_path}: {str(e)}")
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