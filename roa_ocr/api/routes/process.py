"""
ROA OCR — Rutas de procesamiento individual
POST /api/v1/process  — Sube un PDF y retorna el PDF mejorado
"""
import uuid
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from roa_ocr.api.auth import require_api_key
from roa_ocr.api.models import ProcessOptions, OCREngine, CompressQuality
from worker.tasks import submit_process_job
from roa_ocr.config import settings

log = logging.getLogger("roa.routes.process")
router = APIRouter(prefix="/api/v1", tags=["process"])

MAX_BYTES = settings.max_upload_mb * 1024 * 1024


@router.post(
    "/process",
    summary="Procesa un PDF (sincrónico)",
    description=(
        "Sube un PDF, aplica OCR+corrección+optimización y retorna el PDF mejorado. "
        "Ideal para archivos individuales. Para lotes grandes usa /batch."
    ),
    response_class=FileResponse,
)
async def process_pdf(
    file: UploadFile = File(..., description="PDF a procesar"),
    lang: str = Form(default="spa+eng", description="Idioma(s) OCR"),
    engine: OCREngine = Form(default=OCREngine.AUTO),
    dpi: int = Form(default=300, ge=72, le=600),
    skip_if_has_text: bool = Form(default=True),
    run_correction: bool = Form(default=True),
    optimize: bool = Form(default=True),
    compress_quality: CompressQuality = Form(default=CompressQuality.PRINTER),
    _key: str = Depends(require_api_key),
):
    """Procesa un PDF de forma sincrónica y retorna el resultado."""
    # Validar tipo de archivo
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    # Leer contenido
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {settings.max_upload_mb}MB"
        )

    # Guardar temporalmente
    tmp_input = settings.temp_dir / f"in_{uuid.uuid4().hex}.pdf"
    tmp_output = settings.temp_dir / f"out_{uuid.uuid4().hex}.pdf"

    try:
        tmp_input.write_bytes(content)

        options = ProcessOptions(
            lang=lang,
            engine=engine,
            dpi=dpi,
            skip_if_has_text=skip_if_has_text,
            run_correction=run_correction,
            optimize=optimize,
            compress_quality=compress_quality,
        )

        result = await _run_pipeline(tmp_input, tmp_output, options)

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Error desconocido"))

        return FileResponse(
            path=str(tmp_output),
            media_type="application/pdf",
            filename=f"roa_{file.filename}",
            headers={
                "X-Engine-Used": result.get("engine", "unknown"),
                "X-Pages": str(result.get("pages", 0)),
                "X-Processing-Time": str(result.get("processing_time_s", 0)),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Error procesando {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpiar input (output se limpiará cuando FileResponse lo envíe)
        try:
            tmp_input.unlink(missing_ok=True)
        except Exception:
            pass


@router.post(
    "/process/async",
    summary="Procesa un PDF (asíncrono)",
    description="Encola el procesamiento y retorna un job_id para consultar el estado.",
)
async def process_pdf_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = Form(default="spa+eng"),
    engine: OCREngine = Form(default=OCREngine.AUTO),
    dpi: int = Form(default=300, ge=72, le=600),
    skip_if_has_text: bool = Form(default=True),
    run_correction: bool = Form(default=True),
    optimize: bool = Form(default=True),
    compress_quality: CompressQuality = Form(default=CompressQuality.PRINTER),
    _key: str = Depends(require_api_key),
):
    """Encola el procesamiento de un PDF y retorna un job_id."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Máximo {settings.max_upload_mb}MB")

    job_id = uuid.uuid4().hex
    tmp_input = settings.temp_dir / f"in_{job_id}.pdf"
    tmp_input.write_bytes(content)

    options = ProcessOptions(
        lang=lang, engine=engine, dpi=dpi,
        skip_if_has_text=skip_if_has_text,
        run_correction=run_correction,
        optimize=optimize,
        compress_quality=compress_quality,
    )

    # Encolar en Celery (si disponible) o en background task
    job_info = submit_process_job(
        job_id=job_id,
        src_path=str(tmp_input),
        dst_path=str(settings.output_dir / f"roa_{file.filename}"),
        options=options.model_dump(),
        original_filename=file.filename,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Job encolado. Consulta: GET /api/v1/jobs/{job_id}",
        "download_url": f"/api/v1/jobs/{job_id}/download",
    }


@router.post(
    "/process/markdown",
    summary="Procesa un PDF y retorna Markdown estructurado para LLMs y RAG",
    description="Sube un PDF/Imagen y retorna el contenido estructurado en Markdown con tablas formateadas.",
)
async def process_markdown_endpoint(
    file: UploadFile = File(...),
    lang: str = Form(default="spa+eng"),
    engine: OCREngine = Form(default=OCREngine.AUTO),
    dpi: int = Form(default=300),
    _key: str = Depends(require_api_key),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Se requiere un archivo")

    content = await file.read()
    tmp_input = settings.temp_dir / f"in_md_{uuid.uuid4().hex}.pdf"
    tmp_input.write_bytes(content)

    try:
        import asyncio
        from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

        loop = asyncio.get_event_loop()

        def _run():
            cfg = PipelineConfig(lang=lang, dpi=dpi, skip_if_has_text=False, ocr_engine=engine.value)
            pipe = PDFPipeline(config=cfg, er296_dir=settings.er296_dir)
            pipe.initialize()
            return pipe.process_to_markdown(tmp_input, original_filename=file.filename)

        return await loop.run_in_executor(None, _run)
    finally:
        try:
            tmp_input.unlink(missing_ok=True)
        except Exception:
            pass


@router.post(
    "/process/chunks",
    summary="Procesa un PDF y retorna Chunks de Vectores para Qdrant y Meilisearch",
    description="Sube un PDF/Imagen y retorna fragmentos segmentados con payloads listos para Qdrant, Meilisearch y LangChain.",
)
async def process_chunks_endpoint(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=50),
    lang: str = Form(default="spa+eng"),
    engine: OCREngine = Form(default=OCREngine.AUTO),
    dpi: int = Form(default=300),
    _key: str = Depends(require_api_key),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Se requiere un archivo")

    content = await file.read()
    tmp_input = settings.temp_dir / f"in_chk_{uuid.uuid4().hex}.pdf"
    tmp_input.write_bytes(content)

    try:
        import asyncio
        from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

        loop = asyncio.get_event_loop()

        def _run():
            cfg = PipelineConfig(lang=lang, dpi=dpi, skip_if_has_text=False, ocr_engine=engine.value)
            pipe = PDFPipeline(config=cfg, er296_dir=settings.er296_dir)
            pipe.initialize()
            return pipe.process_to_chunks(tmp_input, chunk_size=chunk_size, chunk_overlap=chunk_overlap, original_filename=file.filename)

        return await loop.run_in_executor(None, _run)
    finally:
        try:
            tmp_input.unlink(missing_ok=True)
        except Exception:
            pass


async def _run_pipeline(src: Path, dst: Path, options: ProcessOptions) -> dict:
    """Ejecuta el pipeline de forma asíncrona (en thread pool)."""
    import asyncio
    from roa_ocr.core.pipeline import PDFPipeline, PipelineConfig

    loop = asyncio.get_event_loop()

    def _run():
        config = PipelineConfig(
            lang=options.lang,
            dpi=options.dpi,
            skip_if_has_text=options.skip_if_has_text,
            run_correction=options.run_correction,
            run_optimization=options.optimize,
            compress_quality=options.compress_quality.value,
            ocr_engine=options.engine.value,
            metadata=options.metadata,
        )
        pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
        pipeline.initialize()
        result = pipeline.process(src, dst)
        return result.as_dict()

    return await loop.run_in_executor(None, _run)

