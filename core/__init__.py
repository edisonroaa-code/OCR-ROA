"""
ROA OCR Core — Módulos principales del pipeline OCR
"""
from core.engine import (
    UnifiedOCREngine,
    AcrobatOCREngine,
    OcrmypdfEngine,
    TesseractDirectEngine,
    detect_available_engines,
)
from core.pipeline import PDFPipeline, PipelineConfig, PipelineResult
from core.corrector import PostOCRCorrector
from core.optimizer import PDFOptimizer
from core.idrs15_engine import diagnose_idrs15
from core.batch_processor import BatchProcessor, BatchConfig, BatchStats, run_batch

__all__ = [
    # Motores
    "UnifiedOCREngine",
    "AcrobatOCREngine",
    "OcrmypdfEngine",
    "TesseractDirectEngine",
    "detect_available_engines",

    # Pipeline
    "PDFPipeline",
    "PipelineConfig",
    "PipelineResult",

    # Corrector/Optimizador
    "PostOCRCorrector",
    "PDFOptimizer",

    # iDRS15 (diagnóstico solamente)
    "diagnose_idrs15",

    # Batch
    "BatchProcessor",
    "BatchConfig",
    "BatchStats",
    "run_batch",
]

__version__ = "2.1.0"
