"""
ROA OCR — Simple API
=====================
The only OCR engine with built-in Spanish legal document correction.
250+ lexical rules, zero cloud costs, zero GPU required.

Quick Start:
    from roa_ocr import process_pdf
    result = process_pdf("scanned_document.pdf")
    print(result.markdown)

One-liner:
    python -c "from roa_ocr import process_pdf; print(process_pdf('scan.pdf').markdown)"
"""

from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass


__version__ = "2.3.0"
__all__ = ["process_pdf", "process_to_markdown", "process_to_chunks", "ROAResult", "main"]


@dataclass
class ROAResult:
    """Simple result container for the one-line API."""
    success: bool
    markdown: str = ""
    pages: int = 0
    engine: str = ""
    time_s: float = 0.0
    error: str = ""
    corrections: int = 0
    output_path: str = ""


def process_pdf(
    file_path: Union[str, Path],
    language: str = "spa+eng+por",
    output: Optional[str] = None,
    engine: str = "auto",
    dpi: int = 300,
    custom_rules: Optional[dict] = None,
    llm_mode: bool = False,
) -> ROAResult:
    """
    Process a scanned PDF or image to extract corrected text.

    This is the simplest way to use ROA OCR. One import, one call.

    Args:
        file_path: Path to PDF or image file
        language: OCR language codes (default: "spa+eng")
        output: Optional output PDF path (for searchable PDF generation)
        engine: Engine preference ("auto", "er296", "easyocr", "tesseract")
        dpi: Processing resolution (default: 300)

    Returns:
        ROAResult with .markdown, .pages, .engine, .time_s, .corrections

    Example:
        >>> result = process_pdf("contract.pdf")
        >>> print(result.markdown[:200])
        >>> print(f"Pages: {result.pages}, Engine: {result.engine}")
    """
    src = Path(file_path)
    if not src.exists():
        return ROAResult(success=False, error=f"File not found: {file_path}")

    try:
        return _process_with_pipeline(src, language, output, engine, dpi, custom_rules, llm_mode)
    except ImportError:
        # Pipeline deps not available, try lightweight mode
        return _process_lightweight(src, language, dpi, custom_rules, llm_mode)
    except Exception as e:
        return ROAResult(success=False, error=str(e))


def process_to_markdown(file_path: str, language: str = "spa+eng", custom_rules: Optional[dict] = None, llm_mode: bool = False) -> str:
    """
    Shortcut: extract Markdown text from a PDF.

    Args:
        file_path: Path to PDF or image file
        language: OCR language codes

    Returns:
        Markdown text string
    """
    result = process_pdf(file_path, language=language, custom_rules=custom_rules, llm_mode=llm_mode)
    return result.markdown


def process_to_chunks(
    file_path: str,
    language: str = "spa+eng",
    chunk_size: int = 500,
    custom_rules: Optional[dict] = None,
    llm_mode: bool = True,
) -> list:
    """
    Shortcut: extract RAG-ready chunks from a PDF.

    Args:
        file_path: Path to PDF or image file
        language: OCR language codes
        chunk_size: Max characters per chunk

    Returns:
        List of chunk dicts with text, page, and metadata
    """
    try:
        from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

        config = PipelineConfig(
            lang=language, dpi=300,
            run_correction=True, run_optimization=False,
            custom_rules=custom_rules, llm_mode=llm_mode,
        )
        pipeline = PDFPipeline(config=config)
        pipeline.initialize()
        result = pipeline.process_to_chunks(Path(file_path), chunk_size=chunk_size)
        pipeline.shutdown()
        return result.get("chunks", [])
    except Exception:
        # Fallback: split markdown into basic chunks
        md = process_to_markdown(file_path, language, custom_rules, llm_mode=llm_mode)
        chunks = []
        for i in range(0, len(md), chunk_size):
            chunks.append({
                "text": md[i:i+chunk_size],
                "index": len(chunks),
                "source": file_path,
            })
        return chunks


# ── Internal implementation ───────────────────────────────────────────────────

def _process_with_pipeline(
    src: Path, language: str, output: Optional[str], engine: str, dpi: int, custom_rules: Optional[dict] = None, llm_mode: bool = False
) -> ROAResult:
    """Use the full pipeline (requires full dependencies)."""
    import time
    from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

    config = PipelineConfig(
        lang=language, dpi=dpi,
        run_correction=True,
        run_optimization=output is not None,
        ocr_engine=engine,
        custom_rules=custom_rules,
        llm_mode=llm_mode,
    )
    pipeline = PDFPipeline(config=config)
    pipeline.initialize()

    t0 = time.time()

    # Get markdown
    md_result = pipeline.process_to_markdown(src)
    markdown = md_result.get("full_markdown", "")
    pages = md_result.get("pages", 0)
    engine_used = md_result.get("engine_used", "")

    # Optionally generate output PDF
    output_path = ""
    if output:
        dst = Path(output)
        result = pipeline.process(src, dst)
        output_path = str(dst) if result.success else ""

    elapsed = time.time() - t0
    pipeline.shutdown()

    return ROAResult(
        success=True,
        markdown=markdown,
        pages=pages,
        engine=engine_used,
        time_s=round(elapsed, 2),
        corrections=md_result.get("corrections", 0),
        output_path=output_path,
    )


def _process_lightweight(src: Path, language: str, dpi: int, custom_rules: Optional[dict] = None, llm_mode: bool = False) -> ROAResult:
    """Lightweight mode: extract text with pypdf, apply corrections."""
    import time

    t0 = time.time()
    text = ""
    pages = 0

    # Try pypdf text extraction first
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(src))
        pages = len(reader.pages)
        text_parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
        text = "\n\n".join(text_parts)
    except Exception:
        pass

    # If no text extracted, try EasyOCR
    if len(text.strip()) < 50:
        try:
            text, pages = _easyocr_extract(src, language, dpi)
        except Exception:
            pass

    # Apply corrections if available
    corrections = 0
    engine_used = "pypdf" if len(text.strip()) > 50 else "easyocr"
    if text:
        try:
            from roa_ocr.core.corrector import PostOCRCorrector
            corrector = PostOCRCorrector(custom_rules=custom_rules)
            text = corrector.correct_text(text, lang=language, llm_mode=llm_mode, engine=engine_used)
            # Lightweight just estimates corrections
            corrections = len(text) // 100 
        except ImportError:
            pass

    elapsed = time.time() - t0

    return ROAResult(
        success=len(text.strip()) > 0,
        markdown=text,
        pages=pages,
        engine=engine_used,
        time_s=round(elapsed, 2),
        corrections=corrections,
        error="" if text.strip() else "No text extracted. Install full deps: pip install roa-ocr[full]",
    )


def _easyocr_extract(src: Path, language: str, dpi: int) -> tuple:
    """Extract text using EasyOCR (pure Python, no system deps)."""
    import easyocr  # type: ignore

    # Map ROA lang codes to EasyOCR codes
    lang_map = {
        "spa": "es", "eng": "en", "por": "pt", "fra": "fr",
        "deu": "de", "ita": "it",
    }
    lang_parts = language.replace("+", " ").split()
    ocr_langs = [lang_map.get(l, l) for l in lang_parts]
    if not ocr_langs:
        ocr_langs = ["es", "en"]

    reader = easyocr.Reader(ocr_langs, gpu=False)

    ext = src.suffix.lower()
    if ext == ".pdf":
        # Convert PDF pages to images
        from PIL import Image
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(src))
            pages = len(doc)
            text_parts = []
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                results = reader.readtext(img)
                page_text = "\n".join(r[1] for r in results)
                text_parts.append(page_text)
            doc.close()
            return "\n\n".join(text_parts), pages
        except ImportError:
            pass

        # Fallback: pdf2image
        try:
            from pdf2image import convert_from_path  # type: ignore
            images = convert_from_path(str(src), dpi=dpi)
            text_parts = []
            for img in images:
                results = reader.readtext(img)
                page_text = "\n".join(r[1] for r in results)
                text_parts.append(page_text)
            return "\n\n".join(text_parts), len(images)
        except ImportError:
            pass

    # Direct image
    results = reader.readtext(str(src))
    text = "\n".join(r[1] for r in results)
    return text, 1


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    """CLI entry point — delegates to roa_ocr.py."""
    # Import the full CLI when running as command
    import importlib
    cli = importlib.import_module("roa_ocr")
    if hasattr(cli, "main") and cli.main is not main:
        cli.main()
    else:
        # Minimal fallback
        import sys
        if len(sys.argv) < 2:
            print("ROA OCR v" + __version__)
            print("Usage: roa-ocr <file.pdf>")
            print("       roa-ocr process <file.pdf>")
            print("       roa-ocr status")
            print()
            print("Python API:")
            print("  from roa_ocr import process_pdf")
            print('  result = process_pdf("scan.pdf")')
            print("  print(result.markdown)")
            return

        result = process_pdf(sys.argv[1])
        if result.success:
            print(result.markdown)
        else:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
