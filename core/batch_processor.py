"""
ROA OCR — Procesamiento por Lotes Masivo (Batch Processor)
Optimizado para procesar miles de PDFs locales con ER296.
Características:
- Procesamiento paralelo con ThreadPoolExecutor
- Resumible (checkpoint cada N archivos)
- Progreso en tiempo real con barra de progreso
- Logging detallado con estadísticas
- Manejo robusto de errores y reintentos
- Filtrado inteligente (saltar PDFs con texto, duplicados, corruptos)
"""
import os
import time
import logging
import json
import threading
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import hashlib

from core.engine import UnifiedOCREngine, detect_available_engines
from core.pipeline import PDFPipeline, PipelineConfig, PipelineResult
from config import settings

log = logging.getLogger("roa.batch")


# ──────────────────────────────────────────────────────────────────────────────
# Configuración y Estado
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BatchConfig:
    """Configuración del procesamiento por lotes"""
    # Directorios
    input_dir: Path
    output_dir: Path
    processed_log: Path = field(default_factory=lambda: settings.temp_dir / "batch_processed.json")
    error_log: Path = field(default_factory=lambda: settings.temp_dir / "batch_errors.json")
    
    # Paralelismo
    max_workers: int = 2  # ER296 usa muchos recursos, 2 es óptimo
    use_processes: bool = False  # Threads son mejor para ER296 (COM)
    
    # Pipeline
    lang: str = "spa+eng"
    dpi: int = 300
    skip_if_has_text: bool = True
    run_correction: bool = True
    run_optimization: bool = True
    compress_quality: str = "printer"
    ocr_engine: str = "auto"  # "er296", "ocrmypdf", "tesseract", "auto"
    
    # Control de lote
    checkpoint_interval: int = 10  # Guardar estado cada N archivos
    max_retries: int = 2
    retry_delay: float = 2.0  # segundos
    
    # Filtros
    min_file_size_kb: int = 1
    max_file_size_mb: int = 500
    allowed_extensions: tuple = (".pdf",)
    skip_hidden: bool = True
    
    # Salida
    output_prefix: str = "roa_"
    preserve_structure: bool = True  # Mantener subdirectorios
    
    def to_pipeline_config(self) -> PipelineConfig:
        return PipelineConfig(
            lang=self.lang,
            dpi=self.dpi,
            skip_if_has_text=self.skip_if_has_text,
            run_correction=self.run_correction,
            run_optimization=self.run_optimization,
            compress_quality=self.compress_quality,
            ocr_engine=self.ocr_engine,
        )


@dataclass
class BatchStats:
    """Estadísticas del procesamiento por lotes"""
    total_files: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_pages: int = 0
    total_time_s: float = 0.0
    total_size_before_mb: float = 0.0
    total_size_after_mb: float = 0.0
    engine_usage: Dict[str, int] = field(default_factory=dict)
    errors: List[Dict[str, str]] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.succeeded / max(self.processed, 1) * 100
    
    @property
    def avg_time_per_file(self) -> float:
        return self.total_time_s / max(self.processed, 1)
    
    @property
    def compression_ratio(self) -> float:
        return self.total_size_after_mb / max(self.total_size_before_mb, 0.001)


# ──────────────────────────────────────────────────────────────────────────────
# Procesador por Lotes Principal
# ──────────────────────────────────────────────────────────────────────────────

class BatchProcessor:
    """
    Procesador masivo de PDFs con ER296.
    
    Uso básico:
        config = BatchConfig(
            input_dir=Path(r"C:\PDFS_PENDIENTES"),
            output_dir=Path(r"C:\PDFS_OCR"),
            max_workers=2,
        )
        processor = BatchProcessor(config)
        processor.run()
    """
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self.stats = BatchStats()
        self._lock = threading.Lock()
        self._processed_files: set = set()
        self._pipeline: Optional[PDFPipeline] = None
        self._engine: Optional[UnifiedOCREngine] = None
        self._stop_event = threading.Event()
        
        # Cargar estado previo si existe
        self._load_state()
    
    def _load_state(self):
        """Carga archivos ya procesados para reanudar"""
        if self.config.processed_log.exists():
            try:
                with open(self.config.processed_log, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._processed_files = set(data.get("processed", []))
                    log.info(f"📂 Estado previo cargado: {len(self._processed_files)} archivos procesados")
            except Exception as e:
                log.warning(f"No se pudo cargar estado previo: {e}")
    
    def _save_state(self):
        """Guarda estado actual (checkpoint)"""
        try:
            data = {
                "processed": list(self._processed_files),
                "timestamp": time.time(),
                "stats": {
                    "processed": self.stats.processed,
                    "succeeded": self.stats.succeeded,
                    "failed": self.stats.failed,
                    "skipped": self.stats.skipped,
                }
            }
            with open(self.config.processed_log, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning(f"No se pudo guardar estado: {e}")
    
    def _log_error(self, file: Path, error: str, engine: str = ""):
        """Registra error en log de errores"""
        try:
            errors = []
            if self.config.error_log.exists():
                with open(self.config.error_log, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            
            errors.append({
                "file": str(file),
                "error": error,
                "engine": engine,
                "timestamp": time.time(),
            })
            
            with open(self.config.error_log, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _get_file_hash(self, path: Path) -> str:
        """Calcula hash rápido del archivo para detectar duplicados"""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            # Leer solo primeros y últimos 64KB para velocidad
            chunk = f.read(65536)
            hasher.update(chunk)
            f.seek(max(0, f.seek(0, 2) - 65536))
            hasher.update(f.read(65536))
        return hasher.hexdigest()[:16]
    
    def _should_process(self, src: Path) -> tuple[bool, str]:
        """Determina si un archivo debe procesarse"""
        name = src.name
        
        # Saltar ocultos
        if self.config.skip_hidden and name.startswith('.'):
            return False, "hidden"
        
        # Extensión permitida
        if src.suffix.lower() not in self.config.allowed_extensions:
            return False, "extension"
        
        # Tamaño
        size_kb = src.stat().st_size / 1024
        if size_kb < self.config.min_file_size_kb:
            return False, "too_small"
        if size_kb > self.config.max_file_size_mb * 1024:
            return False, "too_large"
        
        # Ya procesado (checkpoint)
        rel_path = src.relative_to(self.config.input_dir) if self.config.preserve_structure else src.name
        if str(rel_path) in self._processed_files:
            return False, "already_processed"
        
        return True, ""
    
    def _process_single(self, src: Path) -> PipelineResult:
        """Procesa un solo archivo con reintentos"""
        pipeline_cfg = self.config.to_pipeline_config()
        
        # Determinar ruta de salida
        if self.config.preserve_structure:
            rel = src.relative_to(self.config.input_dir)
            dst = self.config.output_dir / rel
        else:
            dst = self.config.output_dir / f"{self.config.output_prefix}{src.name}"
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        last_error = ""
        last_engine = ""
        
        for attempt in range(self.config.max_retries + 1):
            if self._stop_event.is_set():
                return PipelineResult(
                    success=False,
                    input_path=str(src),
                    output_path=str(dst),
                    error="Procesamiento cancelado",
                )
            
            if attempt > 0:
                log.warning(f"🔄 Reintento {attempt}/{self.config.max_retries} para {src.name}")
                time.sleep(self.config.retry_delay * attempt)
            
            try:
                if self._pipeline is None:
                    # Inicializar pipeline lazily (thread-safe)
                    with self._lock:
                        if self._pipeline is None:
                            self._pipeline = PDFPipeline(
                                config=pipeline_cfg,
                                er296_dir=settings.er296_dir,
                            )
                            self._pipeline.initialize()
                
                result = self._pipeline.process(src, dst, pipeline_cfg)
                
                if result.success:
                    return result
                
                last_error = result.error
                last_engine = result.engine_used
                
            except Exception as e:
                last_error = str(e)
                last_engine = "error"
                log.exception(f"Excepción procesando {src.name}")
        
        return PipelineResult(
            success=False,
            input_path=str(src),
            output_path=str(dst),
            error=f"Falló tras {self.config.max_retries + 1} intentos: {last_error}",
            engine_used=last_engine,
        )
    
    def _update_stats(self, result: PipelineResult, skipped: bool = False, skip_reason: str = ""):
        """Actualiza estadísticas thread-safe"""
        with self._lock:
            self.stats.processed += 1
            self.stats.total_time_s += result.processing_time_s
            
            if skipped:
                self.stats.skipped += 1
                self._processed_files.add(result.input_path)
                log.info(f"⏭️  Saltado: {Path(result.input_path).name} ({skip_reason})")
            elif result.success:
                self.stats.succeeded += 1
                self.stats.total_pages += result.pages
                self.stats.total_size_before_mb += result.size_before / 1024 / 1024
                self.stats.total_size_after_mb += result.size_after / 1024 / 1024
                
                eng = result.engine_used or "unknown"
                self.stats.engine_usage[eng] = self.stats.engine_usage.get(eng, 0) + 1
                
                self._processed_files.add(result.input_path)
                
                log.info(
                    f"✅ [{self.stats.processed}/{self.stats.total_files}] "
                    f"{Path(result.input_path).name} | "
                    f"{result.engine_used} | {result.pages}p | "
                    f"{result.size_before//1024}KB→{result.size_after//1024}KB | "
                    f"{result.processing_time_s:.1f}s"
                )
            else:
                self.stats.failed += 1
                self.stats.errors.append({
                    "file": result.input_path,
                    "error": result.error,
                    "engine": result.engine_used,
                })
                self._log_error(Path(result.input_path), result.error, result.engine_used)
                
                log.error(
                    f"❌ [{self.stats.processed}/{self.stats.total_files}] "
                    f"{Path(result.input_path).name} | {result.error}"
                )
            
            # Checkpoint periódico
            if self.stats.processed % self.config.checkpoint_interval == 0:
                self._save_state()
    
    def _worker(self, src: Path, progress_callback: Optional[Callable] = None):
        """Worker para ThreadPoolExecutor"""
        should_process, reason = self._should_process(src)
        
        if not should_process:
            # Crear resultado de "saltado" para estadísticas
            result = PipelineResult(
                success=True,
                input_path=str(src),
                output_path="",
                engine_used="skipped",
            )
            self._update_stats(result, skipped=True, skip_reason=reason)
        else:
            result = self._process_single(src)
            self._update_stats(result)
        
        if progress_callback:
            try:
                progress_callback(self.stats.processed, self.stats.total_files, self.stats)
            except Exception:
                pass
        
        return result
    
    def run(self, progress_callback: Optional[Callable[[int, int, BatchStats], None]] = None) -> BatchStats:
        """
        Ejecuta el procesamiento por lotes.
        
        Args:
            progress_callback: función(current, total, stats) llamada tras cada archivo
            
        Returns:
            BatchStats con resultados finales
        """
        log.info("=" * 60)
        log.info(f"  📦 INICIANDO PROCESAMIENTO POR LOTES")
        log.info(f"  📂 Entrada: {self.config.input_dir}")
        log.info(f"  📂 Salida:  {self.config.output_dir}")
        log.info(f"  ⚙️  Workers: {self.config.max_workers}")
        log.info(f"  🔧 Engine:  {self.config.ocr_engine}")
        log.info("=" * 60)
        
        self.stats.start_time = time.time()
        
        # Descubrir archivos
        files = []
        for ext in self.config.allowed_extensions:
            files.extend(self.config.input_dir.rglob(f"*{ext}"))
        
        self.stats.total_files = len(files)
        
        if not files:
            log.warning("⚠️  No se encontraron archivos PDF para procesar")
            return self.stats
        
        log.info(f"📄 Archivos encontrados: {len(files)}")
        
        # Detectar motores disponibles
        engines = detect_available_engines(settings.er296_dir)
        log.info(f"🔧 Motores disponibles: {engines}")
        
        if self.config.ocr_engine == "auto":
            # El pipeline elegirá automáticamente
            pass
        elif self.config.ocr_engine not in engines or not engines[self.config.ocr_engine]:
            log.warning(f"⚠️  Motor solicitado '{self.config.ocr_engine}' no disponible, usando auto")
        
        # Procesar en paralelo
        try:
            executor_class = ThreadPoolExecutor
            
            with executor_class(max_workers=self.config.max_workers) as executor:
                # Enviar todas las tareas
                futures = {
                    executor.submit(self._worker, f, progress_callback): f
                    for f in files
                }
                
                # Recoger resultados conforme completan
                for future in as_completed(futures):
                    if self._stop_event.is_set():
                        break
                    try:
                        future.result()
                    except Exception as e:
                        src = futures[future]
                        log.exception(f"Error en worker para {src.name}: {e}")
        
        except KeyboardInterrupt:
            log.warning("⚠️  Interrumpido por usuario")
            self._stop_event.set()
        
        finally:
            self.stats.end_time = time.time()
            self._save_state()
            
            # Guardar log de errores si los hay
            if self.stats.errors:
                log.info(f"📝 Errores guardados en: {self.config.error_log}")
        
        # Resumen final
        self._print_summary()
        
        return self.stats
    
    def _print_summary(self):
        log.info("=" * 60)
        log.info(f"  📊 RESUMEN FINAL")
        log.info(f"{'=' * 60}")
        log.info(f"  📄 Total archivos:     {self.stats.total_files}")
        log.info(f"  ✅ Procesados OK:      {self.stats.succeeded}")
        log.info(f"  ❌ Fallidos:           {self.stats.failed}")
        log.info(f"  ⏭️  Saltados:           {self.stats.skipped}")
        log.info(f"  📝 Páginas totales:    {self.stats.total_pages}")
        log.info(f"  ⏱️  Tiempo total:       {self.stats.total_time_s/60:.1f} min")
        log.info(f"  ⚡ Promedio/archivo:    {self.stats.avg_time_per_file:.1f}s")
        log.info(f"  📦 Tamaño antes:       {self.stats.total_size_before_mb:.1f} MB")
        log.info(f"  📦 Tamaño después:     {self.stats.total_size_after_mb:.1f} MB")
        log.info(f"  🗜️  Ratio compresión:    {self.stats.compression_ratio:.1%}")
        log.info(f"  📈 Tasa éxito:         {self.stats.success_rate:.1f}%")
        
        if self.stats.engine_usage:
            log.info(f"  🔧 Motores usados:")
            for eng, count in sorted(self.stats.engine_usage.items(), key=lambda x: -x[1]):
                log.info(f"      {eng}: {count}")
        
        log.info(f"  📂 Salida: {self.config.output_dir}")
        log.info(f"  📝 Log: {self.config.error_log}")
        log.info(f"{'=' * 60}")
    
    def stop(self):
        """Detiene el procesamiento graceful"""
        log.info("🛑 Deteniendo procesamiento...")
        self._stop_event.set()
    
    def shutdown(self):
        """Limpia recursos"""
        if self._pipeline:
            self._pipeline.shutdown()
            self._pipeline = None
        if self._engine:
            self._engine.shutdown()
            self._engine = None


# ──────────────────────────────────────────────────────────────────────────────
# Función de conveniencia para CLI
# ──────────────────────────────────────────────────────────────────────────────

def run_batch(
    input_dir: str,
    output_dir: str,
    workers: int = 2,
    lang: str = "spa+eng",
    dpi: int = 300,
    engine: str = "auto",
    **kwargs
) -> BatchStats:
    """
    Función helper para ejecutar batch desde CLI o scripts.
    
    Args:
        input_dir: Directorio con PDFs de entrada
        output_dir: Directorio para PDFs con OCR
        workers: Hilos paralelos (2 recomendado para ER296)
        lang: Idiomas OCR (ej: "spa+eng")
        dpi: Resolución para conversión a imagen
        engine: "auto" | "er296" | "ocrmypdf" | "tesseract"
    
    Returns:
        BatchStats con resultados
    """
    config = BatchConfig(
        input_dir=Path(input_dir),
        output_dir=Path(output_dir),
        max_workers=workers,
        lang=lang,
        dpi=dpi,
        ocr_engine=engine,
    )
    
    # Aplicar kwargs adicionales
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    processor = BatchProcessor(config)
    try:
        return processor.run()
    finally:
        processor.shutdown()


if __name__ == "__main__":
    import sys
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    
    if len(sys.argv) < 3:
        print("Uso: python -m core.batch_processor <input_dir> <output_dir> [workers] [engine]")
        print("Ejemplo: python -m core.batch_processor C:\\PDFS_IN C:\\PDFS_OUT 2 er296_direct")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    engine = sys.argv[4] if len(sys.argv) > 4 else "auto"
    
    stats = run_batch(input_dir, output_dir, workers=workers, engine=engine)
    
    print(f"\n✅ Completado: {stats.succeeded}/{stats.total_files} OK")
    sys.exit(0 if stats.failed == 0 else 1)