"""
ROA OCR — Modelos Pydantic (schemas API)
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class OCREngine(str, Enum):
    AUTO = "auto"
    ER296 = "er296"
    IDRS15 = "idrs15"
    OCRMYPDF = "ocrmypdf"
    TESSERACT = "tesseract"


class CompressQuality(str, Enum):
    SCREEN = "screen"       # 72 dpi — para pantalla
    EBOOK = "ebook"         # 150 dpi — ebooks
    PRINTER = "printer"     # 300 dpi — impresión
    PREPRESS = "prepress"   # 300 dpi + colores CMYK
    DEFAULT = "default"


class ProcessOptions(BaseModel):
    """Opciones de procesamiento de un PDF."""
    lang: str = Field(
        default="spa+eng",
        description="Idioma(s) para OCR. Ej: 'spa+eng', 'fra', 'por'",
        examples=["spa+eng", "eng", "fra+eng"]
    )
    engine: OCREngine = Field(
        default=OCREngine.AUTO,
        description="Motor OCR a usar"
    )
    dpi: int = Field(
        default=300,
        ge=72, le=600,
        description="Resolución para procesamiento de imágenes"
    )
    skip_if_has_text: bool = Field(
        default=True,
        description="Si True, omite el OCR en páginas que ya tienen texto"
    )
    run_correction: bool = Field(
        default=True,
        description="Aplica corrección post-OCR al texto reconocido"
    )
    optimize: bool = Field(
        default=True,
        description="Comprime y optimiza el PDF de salida"
    )
    compress_quality: CompressQuality = Field(
        default=CompressQuality.PRINTER,
        description="Calidad de compresión del PDF"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Metadatos a inyectar: Title, Author, Subject, Keywords"
    )


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessResponse(BaseModel):
    """Respuesta de un job de procesamiento."""
    job_id: str
    status: JobStatus
    message: str = ""


class JobStatusResponse(BaseModel):
    """Estado detallado de un job."""
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    result: Optional[dict] = None
    error: Optional[str] = None


class BatchRequest(BaseModel):
    """Solicitud de procesamiento por lotes usando rutas locales."""
    paths: List[str] = Field(
        description="Lista de rutas absolutas a PDFs en el servidor"
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Directorio de salida. Si None, usa el configurado."
    )
    options: ProcessOptions = Field(default_factory=ProcessOptions)


class BatchResponse(BaseModel):
    """Respuesta a un request de batch."""
    batch_id: str
    total_files: int
    job_ids: List[str]
    status: str = "queued"


class HealthResponse(BaseModel):
    """Estado de salud del servicio."""
    status: str
    version: str
    engines: dict
    queue_available: bool
    uptime_s: float


class StatsResponse(BaseModel):
    """Estadísticas globales."""
    total_processed: int
    total_success: int
    total_failed: int
    avg_processing_time_s: float
    total_pages_processed: int
    total_mb_processed: float
    engine_usage: dict
