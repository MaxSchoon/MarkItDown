#!/usr/bin/env python3

import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
import argparse
from datetime import datetime

# Add argument parsing
def parse_arguments():
    parser = argparse.ArgumentParser(description="Convert files to Markdown using Microsoft's MarkItDown tool")
    parser.add_argument("-i", "--input", dest="input_dir", default="input",
                        help="Input directory containing files to convert (default: 'input')")
    parser.add_argument("-o", "--output", dest="output_dir", default="output",
                        help="Output directory for converted Markdown files (default: 'output')")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output")
    return parser.parse_args()

def convert_file_to_markdown(input_file_path, output_file_path, verbose=False):
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
        
        if verbose:
            print(f"Successfully converted {input_file_path} to {output_file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file_path}: {e.stderr}")
        return False
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
        
        for root, _, files in os.walk(temp_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Skip hidden files
                if os.path.basename(file_path).startswith('.'):
                    continue
                
                if verbose:
                    print(f"Processing {os.path.relpath(file_path, temp_dir)}")
                
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
        
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            
            if verbose:
                print(f"Processing {filename} in folder {folder_name}")
            
            try:
                # Convert file to markdown
                result = subprocess.run(['markitdown', file_path], 
                                       capture_output=True, 
                                       text=True, 
                                       check=True)
                content = result.stdout
                
                # Add file header and content
                all_markdown_content.append(f"# {filename}\n\n{content}\n\n")
            except subprocess.CalledProcessError as e:
                all_markdown_content.append(f"# {filename}\n\nError converting file: {e.stderr}\n\n")
            except Exception as e:
                all_markdown_content.append(f"# {filename}\n\nError converting file: {str(e)}\n\n")
        
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
    process_all_files(args.input_dir, args.output_dir, args.verbose)