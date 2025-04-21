# MarkItDown File Converter

A Python utility for converting documents (including ZIP archives) to Markdown format using Microsoft's MarkItDown tool.

## Features

- Convert various document formats to Markdown
- Automatically handle ZIP files by extracting and converting all contents to a single Markdown file
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

### Command-Line Options

You can customize the input and output directories using command-line flags:

```bash
python MarkItDown.py -i /path/to/input/folder -o /path/to/output/folder
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
python MarkItDown.py --input documents --output markdown

# Use absolute paths
python MarkItDown.py -i /Users/username/Documents -o /Users/username/Markdown

# Enable verbose mode
python MarkItDown.py -v
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

For example, if you process `example.zip` on April 21, 2025, the output file will be named `example_2025-04-21.md`.

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