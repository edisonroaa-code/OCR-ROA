"""
ROA OCR — MCP Server (Model Context Protocol)
==============================================
Exposes ROA OCR as an MCP tool server so AI agents (Claude, Gemini, GPT, etc.)
can discover and invoke OCR capabilities via the standard MCP protocol.

Usage:
    python integrations/mcp_server.py

Protocol: JSON-RPC 2.0 over stdio
Spec: https://modelcontextprotocol.io
"""

import sys
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

# Ensure parent is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

log = logging.getLogger("roa.mcp")

# ── MCP Tool Definitions ──────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "ocr_to_markdown",
        "description": (
            "Convert a scanned PDF or image to clean, structured Markdown text. "
            "Uses the ROA OCR ER296 native engine with 250+ lexical correction rules "
            "optimized for Spanish and English documents. Returns Markdown with tables "
            "formatted as | col | col | syntax. 100% local, no cloud APIs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the PDF or image file to process"
                },
                "language": {
                    "type": "string",
                    "description": "OCR language codes (e.g. 'spa+eng', 'eng', 'spa', 'por', 'fra')",
                    "default": "spa+eng"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "ocr_to_chunks",
        "description": (
            "Convert a scanned PDF or image into RAG-ready text chunks with metadata. "
            "Each chunk includes page number, character/word counts, and pre-built payloads "
            "for Qdrant and Meilisearch vector databases. Ideal for building RAG pipelines."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the PDF or image file to process"
                },
                "chunk_size": {
                    "type": "integer",
                    "description": "Maximum characters per chunk",
                    "default": 500
                },
                "chunk_overlap": {
                    "type": "integer",
                    "description": "Characters of overlap between chunks",
                    "default": 50
                },
                "language": {
                    "type": "string",
                    "description": "OCR language codes",
                    "default": "spa+eng"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "ocr_enhance_pdf",
        "description": (
            "Process a scanned PDF to make it searchable and compressed. "
            "Applies OCR, lexical correction, and Ghostscript optimization. "
            "Returns the path to the enhanced PDF file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the input PDF file"
                },
                "output_path": {
                    "type": "string",
                    "description": "Absolute path for the output PDF. If omitted, appends '-roaOcr' suffix."
                },
                "language": {
                    "type": "string",
                    "description": "OCR language codes",
                    "default": "spa+eng"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "ocr_engine_status",
        "description": "Check which OCR engines are available (ER296, OCRmyPDF, Tesseract) and their status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# ── Pipeline singleton ────────────────────────────────────────────────────────

_pipeline = None

def _get_pipeline(lang: str = "spa+eng") -> PDFPipeline:
    global _pipeline
    if _pipeline is None:
        config = PipelineConfig(
            lang=lang, dpi=300,
            run_correction=True, run_optimization=True,
        )
        _pipeline = PDFPipeline(config=config)
        _pipeline.initialize()
    return _pipeline


# ── Tool Handlers ─────────────────────────────────────────────────────────────

def handle_ocr_to_markdown(args: dict) -> dict:
    file_path = Path(args["file_path"])
    lang = args.get("language", "spa+eng")

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    pipeline = _get_pipeline(lang)
    result = pipeline.process_to_markdown(file_path)

    return {
        "markdown": result.get("full_markdown", ""),
        "pages": result.get("pages", 0),
        "engine_used": result.get("engine_used", "unknown"),
        "source_file": result.get("source_file", str(file_path.name)),
    }


def handle_ocr_to_chunks(args: dict) -> dict:
    file_path = Path(args["file_path"])
    lang = args.get("language", "spa+eng")
    chunk_size = args.get("chunk_size", 500)
    chunk_overlap = args.get("chunk_overlap", 50)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    pipeline = _get_pipeline(lang)
    result = pipeline.process_to_chunks(
        file_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    return {
        "total_chunks": result.get("total_chunks", 0),
        "total_pages": result.get("total_pages", 0),
        "engine_used": result.get("engine_used", "unknown"),
        "chunks": result.get("chunks", []),
    }


def handle_ocr_enhance_pdf(args: dict) -> dict:
    file_path = Path(args["file_path"])
    lang = args.get("language", "spa+eng")

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    output_path = args.get("output_path")
    if output_path:
        dst = Path(output_path)
    else:
        dst = file_path.parent / f"{file_path.stem}-roaOcr{file_path.suffix}"

    pipeline = _get_pipeline(lang)
    result = pipeline.process(file_path, dst)

    return {
        "success": result.success,
        "output_path": str(dst),
        "engine_used": result.engine_used,
        "pages": result.pages,
        "processing_time_s": round(result.processing_time_s, 2),
        "size_before_kb": round(result.size_before / 1024, 1),
        "size_after_kb": round(result.size_after / 1024, 1),
        "corrections_applied": result.corrections_applied,
    }


def handle_engine_status(args: dict) -> dict:
    from roa_ocr.core.engine import detect_available_engines
    engines = detect_available_engines()
    active = next((name for name, ok in engines.items() if ok), "none")
    return {"engines": engines, "active_engine": active}


HANDLERS = {
    "ocr_to_markdown": handle_ocr_to_markdown,
    "ocr_to_chunks": handle_ocr_to_chunks,
    "ocr_enhance_pdf": handle_ocr_enhance_pdf,
    "ocr_engine_status": handle_engine_status,
}

# ── JSON-RPC 2.0 over stdio ──────────────────────────────────────────────────

SERVER_INFO = {
    "name": "roa-ocr",
    "version": "2.3.0",
}

SERVER_CAPABILITIES = {
    "tools": {}
}


def make_response(id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def make_error(id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return make_response(id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": SERVER_CAPABILITIES,
        })

    elif method == "notifications/initialized":
        return None  # No response needed

    elif method == "tools/list":
        return make_response(id, {"tools": TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = HANDLERS.get(tool_name)
        if not handler:
            return make_error(id, -32601, f"Unknown tool: {tool_name}")

        try:
            result = handler(tool_args)
            content_text = json.dumps(result, ensure_ascii=False, indent=2)
            return make_response(id, {
                "content": [{"type": "text", "text": content_text}],
                "isError": "error" in result,
            })
        except Exception as e:
            return make_response(id, {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "isError": True,
            })

    elif method == "ping":
        return make_response(id, {})

    else:
        return make_error(id, -32601, f"Method not found: {method}")


def main():
    """Run MCP server over stdio (JSON-RPC 2.0)."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    log.info("ROA OCR MCP Server starting...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = make_error(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
