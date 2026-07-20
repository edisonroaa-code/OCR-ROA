"""
ROA OCR — Rutas de gestión de jobs
GET    /api/v1/jobs/{job_id}          — Estado de un job
GET    /api/v1/jobs/{job_id}/download — Descargar resultado
DELETE /api/v1/jobs/{job_id}          — Cancelar/eliminar job
GET    /api/v1/jobs                   — Listar todos los jobs
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.auth import require_api_key
from worker.tasks import get_job_store, cancel_job
from config import settings

log = logging.getLogger("roa.routes.jobs")
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get(
    "",
    summary="Listar todos los jobs",
)
async def list_jobs(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    _key: str = Depends(require_api_key),
):
    """Lista todos los jobs con paginación y filtrado opcional por estado."""
    store = get_job_store()
    jobs = list(store.values())

    if status:
        jobs = [j for j in jobs if j.get("status") == status]

    # Ordenar por fecha de creación (más reciente primero)
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    total = len(jobs)
    page = jobs[offset: offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "jobs": page,
    }


@router.get(
    "/{job_id}",
    summary="Estado de un job",
)
async def job_status(
    job_id: str,
    _key: str = Depends(require_api_key),
):
    """Retorna el estado completo de un job."""
    store = get_job_store()
    job = store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job no encontrado: {job_id}")

    return job


@router.get(
    "/{job_id}/download",
    summary="Descargar PDF procesado",
    response_class=FileResponse,
)
async def download_result(
    job_id: str,
    _key: str = Depends(require_api_key),
):
    """Descarga el PDF resultante de un job completado."""
    store = get_job_store()
    job = store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job no encontrado: {job_id}")

    if job.get("status") != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Job no completado (estado: {job.get('status')})"
        )

    output_path = job.get("output_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(
            status_code=404,
            detail="Archivo de resultado no encontrado"
        )

    filename = f"roa_{job.get('original_filename', job_id + '.pdf')}"
    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=filename,
        headers={
            "X-Engine-Used": job.get("engine_used", "unknown"),
            "X-Pages": str(job.get("pages", 0)),
            "X-Processing-Time": str(job.get("processing_time_s", 0)),
        }
    )


@router.delete(
    "/{job_id}",
    summary="Cancelar o eliminar un job",
)
async def delete_job(
    job_id: str,
    _key: str = Depends(require_api_key),
):
    """Cancela un job pendiente o elimina un job completado del registro."""
    store = get_job_store()
    job = store.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job no encontrado: {job_id}")

    cancelled = cancel_job(job_id)

    # Limpiar archivos temporales
    for path_key in ("src_path", "output_path"):
        path_str = job.get(path_key)
        if path_str:
            p = Path(path_str)
            if p.exists() and str(settings.temp_dir) in str(p):
                try:
                    p.unlink()
                except Exception:
                    pass

    return {
        "job_id": job_id,
        "cancelled": cancelled,
        "message": "Job eliminado del registro",
    }
