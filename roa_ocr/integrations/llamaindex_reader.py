"""
ROA OCR — LlamaIndex Reader
=============================
LlamaIndex-compatible reader that converts scanned PDFs and images into
LlamaIndex Document objects using the ROA OCR pipeline.

Usage:
    from roa_ocr.integrations.llamaindex_reader import ROAOCRReader

    reader = ROAOCRReader(language="spa+eng")
    documents = reader.load_data("scanned_contract.pdf")

    # Use with any LlamaIndex index
    from llama_index.core import VectorStoreIndex
    index = VectorStoreIndex.from_documents(documents)
"""

import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))


class ROAOCRReader:
    """
    LlamaIndex-compatible reader for ROA OCR.

    Converts scanned PDFs and images into LlamaIndex Document objects
    using the ROA OCR pipeline (ER296 native + lexical correction).

    Args:
        language: OCR language codes (default: "spa+eng")
        run_correction: Apply post-OCR lexical correction
        dpi: Processing resolution
        per_page: If True, creates one Document per page; otherwise one per file
    """

    def __init__(
        self,
        language: str = "spa+eng",
        run_correction: bool = True,
        dpi: int = 300,
        per_page: bool = True,
    ):
        self.language = language
        self.run_correction = run_correction
        self.dpi = dpi
        self.per_page = per_page

    def load_data(self, file_path: str, extra_info: Optional[dict] = None) -> List:
        """
        Load a PDF/image file and return LlamaIndex Documents.

        Args:
            file_path: Path to the PDF or image file
            extra_info: Additional metadata to attach to each document

        Returns:
            List of LlamaIndex Document objects
        """
        try:
            from llama_index.core.schema import Document
        except ImportError:
            try:
                from llama_index.schema import Document
            except ImportError:
                raise ImportError(
                    "LlamaIndex is required. Install with: pip install llama-index-core"
                )

        from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

        src = Path(file_path)
        config = PipelineConfig(
            lang=self.language,
            dpi=self.dpi,
            run_correction=self.run_correction,
            run_optimization=False,
        )
        pipeline = PDFPipeline(config=config)
        pipeline.initialize()

        result = pipeline.process_to_markdown(src)
        documents = []

        base_meta = {
            "source": str(src),
            "engine_used": result.get("engine_used", "unknown"),
            "total_pages": result.get("pages", 0),
            "reader": "ROAOCRReader",
        }
        if extra_info:
            base_meta.update(extra_info)

        if self.per_page:
            for page_data in result.get("page_details", []):
                meta = {**base_meta, "page": page_data.get("page", 0)}
                documents.append(Document(
                    text=page_data.get("markdown", ""),
                    metadata=meta,
                ))
        else:
            documents.append(Document(
                text=result.get("full_markdown", ""),
                metadata=base_meta,
            ))

        pipeline.shutdown()
        return documents
