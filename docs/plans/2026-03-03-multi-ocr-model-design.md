# Multi-OCR Model Support Design

## Goal

Add `--ocr-model` CLI flag to switch between OlmOCR and PaddleOCR-VL for A/B comparison testing of PDF OCR quality.

## CLI Interface

```
python3 MarkItDown.py --ocr-model paddleocr   # PaddleOCR-VL-0.9B
python3 MarkItDown.py --ocr-model olmocr       # OlmOCR (default)
python3 MarkItDown.py --no-ocr                 # disable OCR entirely
```

## Model Config Dictionary

```python
OCR_MODELS = {
    "olmocr": {
        "model_id": "allenai/olmOCR-2-7B-1025",
        "prompt": OCR_PROMPT,
        "prompt_with_structure": OCR_PROMPT_WITH_STRUCTURE,
        "toc_prompt": TOC_EXTRACTION_PROMPT,
        "max_tokens": 8192,
        "two_pass": True,
    },
    "paddleocr": {
        "model_id": "PaddlePaddle/PaddleOCR-VL-0.9B",
        "prompt": "OCR:",
        "prompt_with_structure": None,
        "toc_prompt": None,
        "max_tokens": 4092,
        "two_pass": False,
    },
}
```

`ACTIVE_OCR_CONFIG` global set from CLI args, defaults to `"olmocr"`.

## Conversion Flow

- **OlmOCR:** Two-pass (TOC extraction + structure-aware conversion + heading normalization)
- **PaddleOCR-VL:** Single-pass (straight OCR with `"OCR:"` prompt, no TOC or normalization)

The `convert_pdf_with_olmocr` function becomes `convert_pdf_with_ocr` and checks `active_config["two_pass"]` to skip pass 1 when False.

## Changes Summary

1. Add `OCR_MODELS` dict and `ACTIVE_OCR_CONFIG` variable
2. Add `--ocr-model` CLI arg with `choices=["olmocr", "paddleocr"]`
3. Refactor conversion functions to read from `ACTIVE_OCR_CONFIG` instead of `OLMOCR_MODEL` constant
4. Skip two-pass logic when `two_pass=False`
5. Rename `is_olmocr_available()` → `is_ocr_available()`
6. Update verbose status messages to show active model name
