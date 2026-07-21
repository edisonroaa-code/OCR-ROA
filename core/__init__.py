"""
ROA OCR Core — Módulos principales del pipeline OCR
"""
from core.engine import (
    UnifiedOCREngine,
    OcrmypdfEngine,
    TesseractDirectEngine,
    detect_available_engines,
)
from core.pipeline import PDFPipeline, PipelineConfig, PipelineResult
from core.corrector import PostOCRCorrector
from core.optimizer import PDFOptimizer
from core.er296_engine import ER296Engine, IDRS15Engine, diagnose_er296, diagnose_idrs15
from core.batch_processor import BatchProcessor, BatchConfig, BatchStats, run_batch

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
]

__version__ = "2.1.0"
