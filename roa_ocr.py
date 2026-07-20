"""
ROA OCR v2.0 — Sistema Inteligente de Procesamiento & OCR
=========================================================
Motor principal: iDRS15 Nativo
Motor secundario: Cascadas (ocrmypdf -> Tesseract -> Acrobat COM)
"""
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Configurar encoding de salida UTF-8 para consola de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from core.pipeline import PDFPipeline, PipelineConfig

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
settings.log_dir.mkdir(parents=True, exist_ok=True)
log_file = settings.log_dir / "roa_ocr.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("ROA_OCR")


def main():
    print("=" * 65)
    print("  ROA OCR v2.0 — Sistema Inteligente de Procesamiento & OCR")
    print("  Motor Principal: iDRS15 Nativo (x64 Engine)")
    print("=" * 65)
    print(f"📁 Directorio Trabajo: {settings.base_dir}")
    print(f"📁 PDFS Pendientes:   {settings.input_dir}")
    print(f"📁 PDFS Salida:       {settings.output_dir}")

    # Asegurar existencia de carpetas
    settings.ensure_dirs()

    # Inicializar pipeline de procesamiento
    pipeline_config = PipelineConfig(
        lang=settings.default_lang,
        dpi=settings.ocr_dpi,
        skip_if_has_text=True,
        run_correction=True,
        run_optimization=settings.enable_compression,
        compress_quality=settings.compress_quality,
        ocr_engine=settings.ocr_engine,
    )

    pipeline = PDFPipeline(config=pipeline_config, idrs_dir=settings.idrs_dir)

    try:
        active_engine = pipeline.initialize()
        print(f"🚀 Motor activo en pipeline: {active_engine.upper()}")
    except Exception as e:
        print(f"❌ Error al inicializar motores OCR: {e}")
        return

    # Buscar PDFs e imágenes pendientes
    input_files = []
    for ext in ["*.pdf", "*.bmp", "*.png", "*.jpg", "*.tiff"]:
        input_files.extend(list(settings.input_dir.glob(ext)))
        input_files.extend(list(settings.input_dir.rglob(ext)))

    input_files = sorted(list(set(input_files)))

    if not input_files:
        print("\n✅ No hay archivos pendientes en PDFS_PENDIENTES.")
        print(f"   Coloca tus PDFs o imágenes en: {settings.input_dir}")
        return

    print(f"\n📄 Archivos a procesar: {len(input_files)}")
    start_time = time.time()
    successful = 0
    failed = 0

    for i, src_file in enumerate(input_files, 1):
        rel_path = src_file.relative_to(settings.input_dir) if src_file.is_relative_to(settings.input_dir) else src_file.name
        dst_file = settings.output_dir / rel_path

        if src_file.suffix.lower() != ".pdf":
            dst_file = dst_file.with_suffix(".pdf")

        pct = (i / len(input_files)) * 100
        print(f"\n[{i}/{len(input_files)}] ({pct:.1f}%) Procesando: {src_file.name}")

        result = pipeline.process(src_file, dst_file)

        if result.success:
            successful += 1
            print(f"   ✅ OK | Motor: {result.engine_used.upper()} | {result.size_before//1024} KB → {result.size_after//1024} KB ({result.processing_time_s:.1f}s)")
        else:
            failed += 1
            print(f"   ❌ Fallido: {result.error}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(" 📊 RESUMEN DE PROCESAMIENTO ROA OCR")
    print("=" * 65)
    print(f" ✅ Exitosos:          {successful}")
    print(f" ❌ Fallidos:          {failed}")
    print(f" ⏱️  Tiempo Total:      {elapsed/60:.2f} minutos ({elapsed:.1f} segundos)")
    print(f" 📝 Log de Ejecución:  {log_file}")
    print(f" 📂 Carpeta Resultado: {settings.output_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
