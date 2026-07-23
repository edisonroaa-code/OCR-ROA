"""
ROA OCR Core — Módulos principales del pipeline OCR
"""
from roa_ocr.core.engine import (
    UnifiedOCREngine,
    OcrmypdfEngine,
    TesseractDirectEngine,
    detect_available_engines,
)
from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig, PipelineResult
from roa_ocr.core.corrector import PostOCRCorrector
from roa_ocr.core.optimizer import PDFOptimizer
from roa_ocr.core.er296_engine import ER296Engine, IDRS15Engine, diagnose_er296, diagnose_idrs15
from roa_ocr.core.batch_processor import BatchProcessor, BatchConfig, BatchStats, run_batch
from roa_ocr.core.table_parser import TableParser
from roa_ocr.core.format_converter import convert_to_pdf, is_supported, needs_conversion

__all__ = [
    # Motores
    "UnifiedOCREngine",
    "OcrmypdfEngine",
    "TesseractDirectEngine",
    "ER296Engine",
    "IDRS15Engine",
    "detect_available_engines",

    # Pipeline
    "PDFPipeline",
    "PipelineConfig",
    "PipelineResult",

    # Corrector/Optimizador
    "PostOCRCorrector",
    "PDFOptimizer",

    # ER296 / iDRS15 (diagnóstico)
    "diagnose_er296",
    "diagnose_idrs15",

    # Batch
    "BatchProcessor",
    "BatchConfig",
    "BatchStats",
    "run_batch",

    # Table Parser v2
    "TableParser",

    # Format Converter
    "convert_to_pdf",
    "is_supported",
    "needs_conversion",
]

__version__ = "2.4.2"
