"""
ROA OCR — Rutas de procesamiento por lotes
POST /api/v1/batch  — Encola múltiples PDFs
GET  /api/v1/batch/{batch_id}  — Estado del lote
"""
import uuid
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks

from roa_ocr.api.auth import require_api_key
from roa_ocr.api.models import BatchRequest, BatchResponse, ProcessOptions
from worker.tasks import submit_process_job, get_job_store
from roa_ocr.config import settings

log = logging.getLogger("roa.routes.batch")
router = APIRouter(prefix="/api/v1/batch", tags=["batch"])

MAX_BYTES = settings.max_upload_mb * 1024 * 1024


@router.post(
    "",
    response_model=BatchResponse,
    summary="Procesa múltiples PDFs (upload de archivos)",
    description=(
        "Sube múltiples PDFs como multipart y los encola para procesamiento. "
        "Retorna un batch_id y lista de job_ids individuales."
    ),
)
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Archivos PDF a procesar"),
    lang: str = "spa+eng",
    optimize: bool = True,
    run_correction: bool = True,
    _key: str = Depends(require_api_key),
):
    """Procesa múltiples PDFs subidos via multipart."""
    if not files:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo")

    batch_id = uuid.uuid4().hex
    job_ids = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            log.warning(f"Omitiendo archivo no-PDF: {file.filename}")
            continue

        content = await file.read()
        if len(content) > MAX_BYTES:
            log.warning(f"Omitiendo {file.filename}: demasiado grande ({len(content)//1024}KB)")
            continue

        job_id = uuid.uuid4().hex
        tmp_input = settings.temp_dir / f"in_{job_id}.pdf"
        tmp_input.write_bytes(content)

        options = ProcessOptions(
            lang=lang,
            optimize=optimize,
            run_correction=run_correction,
        )

        submit_process_job(
            job_id=job_id,
            src_path=str(tmp_input),
            dst_path=str(settings.output_dir / f"roa_{file.filename}"),
            options=options.model_dump(),
            original_filename=file.filename,
            batch_id=batch_id,
        )
        job_ids.append(job_id)

    if not job_ids:
        raise HTTPException(status_code=400, detail="No se pudo encolar ningún archivo válido")

    return BatchResponse(
        batch_id=batch_id,
        total_files=len(job_ids),
        job_ids=job_ids,
        status="queued",
    )


@router.post(
    "/paths",
    response_model=BatchResponse,
    summary="Procesa PDFs por rutas locales",
    description=(
        "Encola PDFs especificando sus rutas en el servidor. "
        "Útil para procesamiento masivo de archivos ya en el disco."
    ),
)
async def batch_by_paths(
    request: BatchRequest,
    _key: str = Depends(require_api_key),
):
    """Encola PDFs por rutas del servidor."""
    if not request.paths:
        raise HTTPException(status_code=400, detail="Se requiere al menos una ruta")

    batch_id = uuid.uuid4().hex
    job_ids = []
    output_dir = Path(request.output_dir) if request.output_dir else settings.output_dir

    for path_str in request.paths:
        src = Path(path_str)
        if not src.exists():
            log.warning(f"Archivo no encontrado: {src}")
            continue
        if not src.suffix.lower() == ".pdf":
            log.warning(f"No es PDF: {src}")
            continue

        job_id = uuid.uuid4().hex
        dst = output_dir / f"roa_{src.name}"

        submit_process_job(
            job_id=job_id,
            src_path=str(src),
            dst_path=str(dst),
            options=request.options.model_dump(),
            original_filename=src.name,
            batch_id=batch_id,
        )
        job_ids.append(job_id)

    if not job_ids:
        raise HTTPException(status_code=400, detail="No se encontraron archivos válidos")

    return BatchResponse(
        batch_id=batch_id,
        total_files=len(job_ids),
        job_ids=job_ids,
        status="queued",
    )


@router.get(
    "/{batch_id}",
    summary="Estado de un lote",
)
async def batch_status(
    batch_id: str,
    _key: str = Depends(require_api_key),
):
    """Retorna el estado de todos los jobs de un lote."""
    store = get_job_store()
    batch_jobs = {
        jid: info
        for jid, info in store.items()
        if info.get("batch_id") == batch_id
    }

    if not batch_jobs:
        raise HTTPException(status_code=404, detail=f"Lote no encontrado: {batch_id}")

    statuses = [j["status"] for j in batch_jobs.values()]
    total = len(statuses)
    done = sum(1 for s in statuses if s in ("done", "failed"))

    return {
        "batch_id": batch_id,
        "total": total,
        "done": done,
        "pending": sum(1 for s in statuses if s == "pending"),
        "processing": sum(1 for s in statuses if s == "processing"),
        "success": sum(1 for s in statuses if s == "done"),
        "failed": sum(1 for s in statuses if s == "failed"),
        "progress": round(done / max(total, 1), 4),
        "jobs": batch_jobs,
    }
