#!/usr/bin/env python3

import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
from datetime import datetime

def convert_file_to_markdown(input_file_path, output_file_path):
    """Convert a single file to markdown using MarkItDown"""
    try:
        # Use markitdown command line tool
        result = subprocess.run(['markitdown', input_file_path], 
                               capture_output=True, 
                               text=True, 
                               check=True)
        
        # Write the output to the specified file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
        print(f"Successfully converted {input_file_path} to {output_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file_path}: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error converting {input_file_path}: {str(e)}")
        return False

def process_zip_file(zip_file_path, output_file_path):
    """Extract zip file contents and convert to a single markdown file"""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extract zip contents to temp directory
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Process each file in the extracted directory
        all_markdown_content = []
        
        for root, _, files in os.walk(temp_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Skip hidden files
                if os.path.basename(file_path).startswith('.'):
                    continue
                
                try:
                    # Convert file to markdown
                    result = subprocess.run(['markitdown', file_path], 
                                           capture_output=True, 
                                           text=True, 
                                           check=True)
                    content = result.stdout
                    
                    # Add file header and content
                    relative_path = os.path.relpath(file_path, temp_dir)
                    all_markdown_content.append(f"# {relative_path}\n\n{content}\n\n")
                except subprocess.CalledProcessError as e:
                    all_markdown_content.append(f"# {os.path.relpath(file_path, temp_dir)}\n\nError converting file: {e.stderr}\n\n")
                except Exception as e:
                    all_markdown_content.append(f"# {os.path.relpath(file_path, temp_dir)}\n\nError converting file: {str(e)}\n\n")
        
        # Combine all content and write to output file
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Contents of {os.path.basename(zip_file_path)}\n\n")
            f.write("".join(all_markdown_content))
        
        print(f"Successfully converted zip file {zip_file_path} to {output_file_path}")
        return True
    except Exception as e:
        print(f"Error processing zip file {zip_file_path}: {str(e)}")
        return False
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir)

def process_all_files():
    """Process all files in the input directory"""
    # Get the current script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define input and output directories
    input_dir = os.path.join(script_dir, 'input')
    output_dir = os.path.join(script_dir, 'output')
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get current date for filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Process each file in the input directory
    for filename in os.listdir(input_dir):
        input_file_path = os.path.join(input_dir, filename)
        
        # Skip directories and hidden files
        if os.path.isdir(input_file_path) or filename.startswith('.'):
            continue
        
        # Create output filename with date
        name_without_ext, ext = os.path.splitext(filename)
        output_filename = f"{name_without_ext}_{current_date}.md"
        output_file_path = os.path.join(output_dir, output_filename)
        
        # Process the file based on extension
        if ext.lower() == '.zip':
            process_zip_file(input_file_path, output_file_path)
        else:
            convert_file_to_markdown(input_file_path, output_file_path)

if __name__ == "__main__":
    process_all_files()