"""
ROA OCR — Sistema de Workers y cola de jobs
Soporta dos modos:
  1. Redis + Celery (modo producción — instalar Redis primero)
  2. In-process threading (modo desarrollo — sin dependencias externas)
"""
import uuid
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("roa.worker")

# ──────────────────────────────────────────────────────────────────────────────
# Job Store en memoria (para modo desarrollo / sin Redis)
# ──────────────────────────────────────────────────────────────────────────────

_JOB_STORE: dict = {}
_STORE_LOCK = threading.Lock()

# Thread pool para procesamiento async en modo dev
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="roa-worker")


def get_job_store() -> dict:
    """Retorna el store de jobs actual (dict compartido)."""
    return _JOB_STORE


def _update_job(job_id: str, **kwargs):
    with _STORE_LOCK:
        if job_id in _JOB_STORE:
            _JOB_STORE[job_id].update(kwargs)
            _JOB_STORE[job_id]["updated_at"] = datetime.now().isoformat()


def _create_job(job_id: str, src_path: str, dst_path: str, options: dict,
                original_filename: str, batch_id: Optional[str] = None) -> dict:
    job = {
        "job_id": job_id,
        "status": "pending",
        "src_path": src_path,
        "output_path": dst_path,
        "original_filename": original_filename,
        "options": options,
        "batch_id": batch_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "progress": 0.0,
        "engine_used": None,
        "pages": 0,
        "had_text": False,
        "processing_time_s": 0.0,
        "size_before_kb": 0.0,
        "size_after_kb": 0.0,
        "compression_ratio": 1.0,
        "corrections_applied": 0,
        "error": None,
    }
    with _STORE_LOCK:
        _JOB_STORE[job_id] = job
    return job


# ──────────────────────────────────────────────────────────────────────────────
# Tarea de procesamiento
# ──────────────────────────────────────────────────────────────────────────────

def _execute_job(job_id: str):
    """Ejecuta el pipeline de OCR para un job. Corre en thread pool."""
    with _STORE_LOCK:
        job = _JOB_STORE.get(job_id)
    if not job:
        return

    _update_job(job_id, status="processing", progress=0.05)

    src = Path(job["src_path"])
    dst = Path(job["output_path"])
    options = job.get("options", {})

    try:
        from core.pipeline import PDFPipeline, PipelineConfig
        from config import settings

        config = PipelineConfig(
            lang=options.get("lang", "spa+eng"),
            dpi=options.get("dpi", 300),
            skip_if_has_text=options.get("skip_if_has_text", True),
            run_correction=options.get("run_correction", True),
            run_optimization=options.get("optimize", True),
            compress_quality=options.get("compress_quality", "printer"),
            ocr_engine=options.get("engine", "auto"),
            metadata=options.get("metadata", {}),
        )

        _update_job(job_id, progress=0.1)

        pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
        pipeline.initialize()

        _update_job(job_id, progress=0.2)

        result = pipeline.process(src, dst)
        pipeline.shutdown()

        if result.success:
            _update_job(
                job_id,
                status="done",
                progress=1.0,
                engine_used=result.engine_used,
                pages=result.pages,
                had_text=result.had_text,
                processing_time_s=result.processing_time_s,
                size_before_kb=round(result.size_before / 1024, 1),
                size_after_kb=round(result.size_after / 1024, 1),
                compression_ratio=round(result.size_after / max(result.size_before, 1), 4),
                corrections_applied=result.corrections_applied,
            )
            log.info(f"✅ Job {job_id[:8]}... completado en {result.processing_time_s:.1f}s")
        else:
            _update_job(
                job_id,
                status="failed",
                error=result.error,
            )
            log.error(f"❌ Job {job_id[:8]}... falló: {result.error}")

    except Exception as e:
        log.exception(f"Error fatal en job {job_id}: {e}")
        _update_job(job_id, status="failed", error=str(e))
    finally:
        # Limpiar archivo de entrada temporal
        try:
            if src.exists() and "tmp" in str(src):
                src.unlink()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Celery (opcional — modo producción)
# ──────────────────────────────────────────────────────────────────────────────

_celery_app = None

def _try_init_celery():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from celery import Celery  # type: ignore[import-untyped]
        from config import settings
        app = Celery("roa_ocr", broker=settings.redis_url, backend=settings.redis_url)
        app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="America/Argentina/Buenos_Aires",
            task_track_started=True,
        )
        # Probar conexión
        app.control.ping(timeout=1)
        _celery_app = app
        log.info("✅ Celery + Redis conectado")
    except Exception as e:
        log.info(f"Redis/Celery no disponible ({e}) — usando modo threading")
        _celery_app = None
    return _celery_app


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def submit_process_job(
    job_id: str,
    src_path: str,
    dst_path: str,
    options: dict,
    original_filename: str,
    batch_id: Optional[str] = None,
) -> dict:
    """
    Encola un job de procesamiento.
    Si Celery+Redis disponible → usa Celery.
    Si no → usa ThreadPoolExecutor interno.
    """
    job = _create_job(job_id, src_path, dst_path, options, original_filename, batch_id)

    celery = _try_init_celery()
    if celery:
        # Encolar en Celery
        celery.send_task(
            "worker.tasks.celery_execute_job",
            args=[job_id],
            task_id=job_id,
        )
    else:
        # Encolar en thread pool local
        _EXECUTOR.submit(_execute_job, job_id)

    return job


def cancel_job(job_id: str) -> bool:
    """Cancela un job pendiente."""
    with _STORE_LOCK:
        job = _JOB_STORE.get(job_id)
        if not job:
            return False
        if job["status"] in ("pending",):
            job["status"] = "cancelled"
            job["updated_at"] = datetime.now().isoformat()
            return True
    return False


def get_global_stats() -> dict:
    """Retorna estadísticas globales de todos los jobs."""
    with _STORE_LOCK:
        jobs = list(_JOB_STORE.values())

    done = [j for j in jobs if j["status"] == "done"]
    failed = [j for j in jobs if j["status"] == "failed"]

    engine_usage = {}
    total_pages = 0
    total_mb = 0.0
    total_time = 0.0

    for j in done:
        eng = j.get("engine_used") or "unknown"
        engine_usage[eng] = engine_usage.get(eng, 0) + 1
        total_pages += j.get("pages", 0)
        total_mb += j.get("size_before_kb", 0) / 1024
        total_time += j.get("processing_time_s", 0)

    return {
        "total_processed": len(done) + len(failed),
        "total_success": len(done),
        "total_failed": len(failed),
        "avg_processing_time_s": round(total_time / max(len(done), 1), 2),
        "total_pages_processed": total_pages,
        "total_mb_processed": round(total_mb, 2),
        "engine_usage": engine_usage,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Celery task (solo se registra si Celery está disponible)
# ──────────────────────────────────────────────────────────────────────────────

try:
    from celery import shared_task  # type: ignore[import-untyped]

    @shared_task(name="worker.tasks.celery_execute_job", bind=True, max_retries=2)
    def celery_execute_job(self, job_id: str):
        """Celery task wrapper."""
        _execute_job(job_id)

except ImportError:
    pass
