# MarkItDown File Converter

A Python utility for converting documents (including ZIP archives) to Markdown format using Microsoft's MarkItDown tool.

## Features

- Convert various document formats to Markdown
- Automatically handle ZIP files by extracting and converting all contents to a single Markdown file
- Process folders and maintain directory structure in output
- Combine all files in a leaf folder (folder with no subfolders) into a single Markdown file
- Preserve file organization within ZIP archives in the output Markdown
- Add date to output filenames for easy versioning
- Simple, directory-based workflow
- Customizable input and output directory paths via command-line arguments

## Prerequisites

- Python 3.6 or higher
- Microsoft MarkItDown tool installed (`pip install markitdown`)

## Installation

1. Clone this repository or download the script
2. Ensure MarkItDown is installed and available in your PATH:
   ```bash
   pip install markitdown
   ```
3. Create the input and output directories if they don't exist:
   ```bash
   mkdir -p input output
   ```

## Usage

### Basic Usage

1. Place the files you want to convert in the `input` directory
2. Run the script:
   ```bash
   python MarkItDown.py
   ```
3. Find the converted Markdown files in the `output` directory

### Directory Structure Handling

The tool processes directories with the following rules:

- Individual files at any level are converted to individual Markdown files
- The directory structure from input is preserved in the output
- For each "leaf folder" (folder with no subfolders), all files are combined into a single Markdown file named after the folder
- For folders with subfolders, each subfolder is processed recursively
- All output files include the current date in their filename

Example:
```
input/
├── file1.pdf                   → output/file1_2025-04-21.md
├── folder1/                    → output/folder1/
│   ├── subfolder1/             → output/folder1/subfolder1/
│   │   ├── doc1.docx           
│   │   └── doc2.docx           
│   │   (combined into)         → output/folder1/subfolder1/subfolder1_2025-04-21.md
│   ├── subfolder2/             → output/folder1/subfolder2/
│   │   └── report.pptx         → output/folder1/subfolder2/report_2025-04-21.md
│   └── file2.xlsx              → output/folder1/file2_2025-04-21.md
└── archive.zip                 → output/archive_2025-04-21.md
```

### Command-Line Options

You can customize the input and output directories using command-line flags:

```bash
python3 MarkItDown.py -i /path/to/input/folder -o /path/to/output/folder
```

Available options:

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-i` | `--input` | Specify custom input directory (default: `input`) |
| `-o` | `--output` | Specify custom output directory (default: `output`) |
| `-v` | `--verbose` | Enable verbose output for detailed processing information |

Examples:

```bash
# Use custom folders
python3 MarkItDown.py --input documents --output markdown

# Use absolute paths
python3 MarkItDown.py -i /Users/username/Documents -o /Users/username/Markdown

# Enable verbose mode
python3 MarkItDown.py -v
```

### Supported File Types

The tool supports all file types that Microsoft's MarkItDown can handle, including:
- PDF documents (.pdf)
- Microsoft Word documents (.docx)
- Microsoft PowerPoint presentations (.pptx)
- Microsoft Excel spreadsheets (.xlsx)
- ZIP files containing any of the above formats

### ZIP File Handling

When a ZIP file is processed:
- All files within the ZIP are extracted to a temporary directory
- Each file is converted to Markdown
- The results are combined into a single Markdown file with headers showing the original file structure
- The output file is named after the original ZIP file with the current date appended

## Output Format

Output files follow this naming convention:
```
original_filename_YYYY-MM-DD.md
```

For leaf folders (folders with no subfolders), the output is a single file:
```
foldername_YYYY-MM-DD.md
```

For example, if you process `example.zip` on April 21, 2025, the output file will be named `example_2025-04-21.md`.

## Machine-Readable File Headers

When multiple files are combined into a single Markdown file (such as when processing a folder or ZIP archive), each file's content is preceded by a machine-readable header:

```
# file n - filename
```

- `n` is the 1-based index of the file within the combined output.
- `filename` is the name of the file (or relative path for files inside ZIPs).

This scheme allows other programs or scripts to easily locate and extract individual files using regular expressions. For example, you can use the following regex to find each file section:

```
^# file (\d+) - (.+)$
```

This makes it easy to parse, split, or analyze the combined Markdown files programmatically.

## Troubleshooting

If you encounter errors:

1. Ensure MarkItDown is properly installed and in your PATH
2. Check that the input and output directories exist
3. Verify that you have appropriate permissions to read from input and write to output
4. For ZIP files, ensure they're not corrupted and contain supported file types
5. Use the `-v` flag to enable verbose mode for detailed logging

## License

MIT License (MIT)

## Acknowledgments

- Microsoft for creating the MarkItDown tool