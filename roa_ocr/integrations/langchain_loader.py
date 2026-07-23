"""
ROA OCR — LangChain Document Loader
=====================================
Drop-in LangChain loader that converts scanned PDFs and images into
LangChain Document objects using the ROA OCR pipeline.

Usage:
    from roa_ocr.integrations.langchain_loader import ROAOCRLoader

    loader = ROAOCRLoader("scanned_contract.pdf", language="spa+eng")
    docs = loader.load()

    # Use with any LangChain chain
    for doc in docs:
        print(doc.page_content[:200])
        print(doc.metadata)
"""

import sys
from pathlib import Path
from typing import List, Optional, Iterator

sys.path.insert(0, str(Path(__file__).parent.parent))


class ROAOCRLoader:
    """
    LangChain-compatible document loader for ROA OCR.

    Converts scanned PDFs and images into structured text using the ROA OCR
    pipeline (ER296 native engine + lexical correction + table parsing).

    Each page becomes a separate Document with metadata including:
    - source: original filename
    - page: page number
    - engine_used: which OCR engine processed the document
    - char_count: characters in the page

    Args:
        file_path: Path to the PDF or image file
        language: OCR language codes (default: "spa+eng")
        mode: "page" for one Document per page, "single" for entire doc as one Document
        run_correction: Whether to apply post-OCR lexical correction
        dpi: Processing resolution (default: 300)
    """

    def __init__(
        self,
        file_path: str,
        language: str = "spa+eng",
        mode: str = "page",
        run_correction: bool = True,
        dpi: int = 300,
    ):
        self.file_path = Path(file_path)
        self.language = language
        self.mode = mode
        self.run_correction = run_correction
        self.dpi = dpi

    def load(self) -> List:
        """Load and return Documents."""
        return list(self.lazy_load())

    def lazy_load(self) -> Iterator:
        """Lazily load Documents one at a time."""
        try:
            from langchain_core.documents import Document
        except ImportError:
            try:
                from langchain.schema import Document
            except ImportError:
                raise ImportError(
                    "LangChain is required. Install with: pip install langchain-core"
                )

        from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

        config = PipelineConfig(
            lang=self.language,
            dpi=self.dpi,
            run_correction=self.run_correction,
            run_optimization=False,
        )
        pipeline = PDFPipeline(config=config)
        pipeline.initialize()

        result = pipeline.process_to_markdown(self.file_path)

        if self.mode == "single":
            yield Document(
                page_content=result.get("full_markdown", ""),
                metadata={
                    "source": str(self.file_path),
                    "engine_used": result.get("engine_used", "unknown"),
                    "pages": result.get("pages", 0),
                    "loader": "ROAOCRLoader",
                },
            )
        else:
            for page_data in result.get("page_details", []):
                yield Document(
                    page_content=page_data.get("markdown", ""),
                    metadata={
                        "source": str(self.file_path),
                        "page": page_data.get("page", 0),
                        "char_count": page_data.get("char_count", 0),
                        "engine_used": result.get("engine_used", "unknown"),
                        "loader": "ROAOCRLoader",
                    },
                )

        pipeline.shutdown()
