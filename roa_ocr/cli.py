"""
ROA OCR v2.3.0 — Modern CLI
==============================
Enterprise-grade local OCR engine for RAG & LLMs.

Commands:
    roa-ocr                     Process all files in PDFS_PENDIENTES/
    roa-ocr process FILE        Process a single file
    roa-ocr markdown FILE       Extract Markdown from a PDF
    roa-ocr chunks FILE         Generate RAG chunks from a PDF
    roa-ocr status              Show engine status
    roa-ocr benchmark DIR       Run accuracy benchmark
    roa-ocr serve               Start the API server
    roa-ocr mcp                 Start MCP server for AI agents
"""
import os
import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Export the 1-line API so `from roa_ocr import process_pdf` works
from roa_ocr import process_pdf, process_to_markdown, process_to_chunks, ROAResult

__all__ = ["process_pdf", "process_to_markdown", "process_to_chunks", "ROAResult", "main"]

# Windows UTF-8 console fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from roa_ocr.config import settings
from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig


# ── Logging ───────────────────────────────────────────────────────────────────
settings.log_dir.mkdir(parents=True, exist_ok=True)
log_file = settings.log_dir / "roa_ocr.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("ROA_OCR")


# ── Banner ────────────────────────────────────────────────────────────────────
BANNER = """\
\033[33m
  ╔══════════════════════════════════════════════╗
  ║  ROA OCR v2.3.0                              ║
  ║  Enterprise Local OCR · ER296 Native Engine  ║
  ╚══════════════════════════════════════════════╝\033[0m"""


def print_banner():
    print(BANNER)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_batch(args):
    """Process all files in PDFS_PENDIENTES/."""
    print_banner()
    print(f"  Input:  {settings.input_dir}")
    print(f"  Output: {settings.output_dir}")
    settings.ensure_dirs()

    pipeline_config = PipelineConfig(
        lang=args.lang or settings.default_lang,
        dpi=args.dpi or settings.ocr_dpi,
        skip_if_has_text=True,
        run_correction=True,
        run_optimization=settings.enable_compression,
        compress_quality=settings.compress_quality,
        ocr_engine=args.engine or settings.ocr_engine,
    )

    pipeline = PDFPipeline(config=pipeline_config, er296_dir=settings.er296_dir)
    try:
        active_engine = pipeline.initialize()
        print(f"  Engine: {active_engine.upper()}")
    except Exception as e:
        print(f"\n  \033[31mError: {e}\033[0m")
        return 1

    input_files = []
    for ext in ["*.pdf", "*.bmp", "*.png", "*.jpg", "*.tiff"]:
        input_files.extend(list(settings.input_dir.glob(ext)))
    input_files = sorted(list(set(input_files)))

    if not input_files:
        print(f"\n  No files found in {settings.input_dir}")
        print(f"  Place your PDFs or images there and re-run.")
        return 0

    print(f"\n  Files: {len(input_files)}\n")
    start_time = time.time()
    ok = 0
    fail = 0

    for i, src in enumerate(input_files, 1):
        rel = src.relative_to(settings.input_dir) if src.is_relative_to(settings.input_dir) else src.name
        dst = settings.output_dir / rel
        if src.suffix.lower() != ".pdf":
            dst = dst.with_suffix(".pdf")

        pct = (i / len(input_files)) * 100
        bar_len = 30
        filled = int(bar_len * i / len(input_files))
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  {src.name[:40]:<40}")
        sys.stdout.flush()

        result = pipeline.process(src, dst)
        if result.success:
            ok += 1
        else:
            fail += 1

    elapsed = time.time() - start_time
    print(f"\n\n  \033[32m✓ Done\033[0m  {ok} succeeded · {fail} failed · {elapsed:.1f}s")
    print(f"  Output: {settings.output_dir}")
    print(f"  Log:    {log_file}")
    return 0 if fail == 0 else 1


def cmd_process(args):
    """Process a single file."""
    src = Path(args.file)
    if not src.exists():
        print(f"  Error: File not found: {src}")
        return 1

    dst = Path(args.output) if args.output else src.parent / f"{src.stem}-roaOcr{src.suffix}"
    print_banner()
    print(f"  Input:  {src}")
    print(f"  Output: {dst}")

    config = PipelineConfig(
        lang=args.lang or "spa+eng",
        dpi=args.dpi or 300,
        run_correction=True,
        run_optimization=True,
        ocr_engine=args.engine or "auto",
    )
    pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
    engine = pipeline.initialize()
    print(f"  Engine: {engine.upper()}\n")

    result = pipeline.process(src, dst)
    if result.success:
        ratio = round((result.size_after / max(result.size_before, 1)) * 100, 1)
        print(f"  \033[32m✓ Success\033[0m")
        print(f"  Pages:       {result.pages}")
        print(f"  Engine:      {result.engine_used}")
        print(f"  Time:        {result.processing_time_s:.1f}s")
        print(f"  Size:        {result.size_before//1024}KB → {result.size_after//1024}KB ({ratio}%)")
        print(f"  Corrections: {result.corrections_applied}")
        print(f"  Output:      {dst}")
    else:
        print(f"  \033[31m✗ Failed: {result.error}\033[0m")
    return 0 if result.success else 1


def cmd_markdown(args):
    """Extract Markdown from a file."""
    src = Path(args.file)
    if not src.exists():
        print(f"Error: File not found: {src}", file=sys.stderr)
        return 1

    config = PipelineConfig(
        lang=args.lang or "spa+eng", dpi=args.dpi or 300,
        run_correction=True, run_optimization=False,
        ocr_engine=args.engine or "auto",
    )
    pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
    pipeline.initialize()

    result = pipeline.process_to_markdown(src)
    md = result.get("full_markdown", "")

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"Saved to {args.output} ({len(md)} chars, {result.get('pages',0)} pages)")
    else:
        print(md)
    return 0


def cmd_chunks(args):
    """Generate RAG chunks from a file."""
    import json
    src = Path(args.file)
    if not src.exists():
        print(f"Error: File not found: {src}", file=sys.stderr)
        return 1

    config = PipelineConfig(
        lang=args.lang or "spa+eng", dpi=args.dpi or 300,
        run_correction=True, run_optimization=False,
        ocr_engine=args.engine or "auto",
    )
    pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
    pipeline.initialize()

    result = pipeline.process_to_chunks(
        src, chunk_size=args.chunk_size or 500
    )

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Saved {result.get('total_chunks',0)} chunks to {args.output}")
    else:
        print(output)
    return 0


def cmd_status(args):
    """Show engine and system status."""
    from roa_ocr.core.engine import detect_available_engines
    print_banner()
    engines = detect_available_engines(settings.er296_dir)
    print(f"\n  Engine Status:")
    for name, available in engines.items():
        icon = "\033[32m●\033[0m" if available else "\033[31m○\033[0m"
        status = "available" if available else "not found"
        print(f"    {icon} {name:<12} {status}")

    print(f"\n  Configuration:")
    print(f"    Language:    {settings.default_lang}")
    print(f"    DPI:         {settings.ocr_dpi}")
    print(f"    Engine:      {settings.ocr_engine}")
    print(f"    Input dir:   {settings.input_dir}")
    print(f"    Output dir:  {settings.output_dir}")
    print(f"    API port:    {settings.api_port}")
    return 0


def cmd_serve(args):
    """Start the API server."""
    print_banner()
    print(f"  Starting API server on port {args.port or settings.api_port}...")
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        reload=args.reload,
    )
    return 0


def cmd_mcp(args):
    """Start MCP server for AI agents."""
    from roa_ocr.integrations.mcp_server import main as mcp_main
    mcp_main()
    return 0


def cmd_benchmark(args):
    """Run accuracy benchmark."""
    from benchmarks.benchmark import run_benchmark
    run_benchmark(
        input_dir=args.dir,
        ground_truth_dir=args.ground_truth,
        output_report=args.output or "benchmarks/report.json",
        language=args.lang or "spa+eng",
        engine=args.engine or "auto",
    )
    return 0


# ── Argument Parser ───────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="roa-ocr",
        description="ROA OCR — Enterprise Local OCR Engine for RAG & LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  roa-ocr                              Process all files in PDFS_PENDIENTES/
  roa-ocr process invoice.pdf          Process a single PDF
  roa-ocr markdown scan.pdf -o out.md  Extract Markdown
  roa-ocr chunks scan.pdf              Generate RAG chunks
  roa-ocr status                       Show engine status
  roa-ocr serve                        Start API server
  roa-ocr mcp                          Start MCP server
  roa-ocr benchmark samples/           Run accuracy benchmark
""",
    )

    # Global options
    parser.add_argument("--engine", "-e", help="OCR engine (auto|er296|ocrmypdf|tesseract)")
    parser.add_argument("--lang", "-l", help="Language codes (e.g. spa+eng)")
    parser.add_argument("--dpi", type=int, help="Processing DPI (default: 300)")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    # process
    p_process = sub.add_parser("process", help="Process a single file")
    p_process.add_argument("file", help="PDF or image file to process")
    p_process.add_argument("-o", "--output", help="Output file path")

    # markdown
    p_md = sub.add_parser("markdown", help="Extract Markdown from a file")
    p_md.add_argument("file", help="PDF or image file")
    p_md.add_argument("-o", "--output", help="Output .md file")

    # chunks
    p_chunks = sub.add_parser("chunks", help="Generate RAG chunks")
    p_chunks.add_argument("file", help="PDF or image file")
    p_chunks.add_argument("-o", "--output", help="Output .json file")
    p_chunks.add_argument("--chunk-size", type=int, default=500, help="Chunk size")

    # status
    sub.add_parser("status", help="Show engine and system status")

    # serve
    p_serve = sub.add_parser("serve", help="Start API server")
    p_serve.add_argument("--host", help="Bind host")
    p_serve.add_argument("--port", type=int, help="Bind port")
    p_serve.add_argument("--reload", action="store_true", help="Auto-reload on changes")

    # mcp
    sub.add_parser("mcp", help="Start MCP server for AI agents")

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Run accuracy benchmark")
    p_bench.add_argument("dir", help="Directory with test files")
    p_bench.add_argument("-g", "--ground-truth", help="Ground truth .txt directory")
    p_bench.add_argument("-o", "--output", help="Report output path")

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    command_map = {
        "process": cmd_process,
        "markdown": cmd_markdown,
        "chunks": cmd_chunks,
        "status": cmd_status,
        "serve": cmd_serve,
        "mcp": cmd_mcp,
        "benchmark": cmd_benchmark,
    }

    if args.command:
        handler = command_map.get(args.command)
        if handler:
            sys.exit(handler(args))
        else:
            parser.print_help()
    else:
        # Default: batch process
        sys.exit(cmd_batch(args))


if __name__ == "__main__":
    main()
