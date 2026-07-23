"""
ROA OCR — End-to-End (E2E) Test & Quality Benchmark Script
"""
import sys
import time
import json
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pypdf import PdfReader
from PIL import Image

from config import settings
from core.engine import UnifiedOCREngine, ER296Engine
from core.pipeline import PDFPipeline, PipelineConfig

def analyze_pdf(pdf_path: Path) -> dict:
    if not pdf_path.exists():
        return {"error": "File not found"}
    
    size_bytes = pdf_path.stat().st_size
    try:
        reader = PdfReader(str(pdf_path))
        num_pages = len(reader.pages)
        full_text = ""
        page_texts = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            page_texts.append({"page": i + 1, "char_count": len(txt), "sample": txt[:150].strip()})
            full_text += txt + "\n"
        
        return {
            "path": str(pdf_path),
            "size_kb": round(size_bytes / 1024, 2),
            "num_pages": num_pages,
            "total_chars": len(full_text),
            "page_details": page_texts,
            "has_extractable_text": len(full_text.strip()) > 50,
            "full_text_sample": full_text[:300].strip(),
        }
    except Exception as e:
        return {"path": str(pdf_path), "size_kb": round(size_bytes / 1024, 2), "error": str(e)}

def run_e2e_test():
    print("=" * 70)
    print(" INICIANDO PRUEBA E2E DE CALIDAD Y FUNCIONAMIENTO ROA OCR (ER296)")
    print("=" * 70)
    
    # 1. Seleccionar archivo de entrada
    sample_pdf = settings.input_dir / "40587.pdf"
    if not sample_pdf.exists():
        sample_pdf = settings.base_dir / "test_prueba.pdf"
    
    print(f"\n[ENTRADA] Archivo Seleccionado: {sample_pdf.name}")
    
    # 2. Análisis de Calidad de Entrada
    input_metrics = analyze_pdf(sample_pdf)
    print("\n--- [EVALUACIÓN DE ENTRADA] ---")
    print(f"  - Ruta: {input_metrics['path']}")
    print(f"  - Tamaño Inicial: {input_metrics['size_kb']} KB")
    print(f"  - Cantidad de Páginas: {input_metrics['num_pages']}")
    print(f"  - Caracteres extraídos pre-OCR: {input_metrics['total_chars']}")
    print(f"  - Muestra de texto pre-OCR:\n    \"{input_metrics.get('full_text_sample', '')[:120]}...\"")

    # 3. Prueba directa del motor ER296 Nativo
    print("\n--- [PRUEBA 1: Motor ER296 Nativo Directo] ---")
    er296 = ER296Engine(er296_dir=settings.er296_dir)
    er296_init = er296.initialize()
    print(f"  - Inicialización ER296: {'[OK]' if er296_init else '[FALLO]'}")
    
    test_out_direct = settings.temp_dir / "e2e_direct_er296.pdf"
    t0_direct = time.time()
    direct_ok, direct_err = er296.process_pdf(sample_pdf, test_out_direct, lang="spa+eng", dpi=300)
    t1_direct = time.time()
    
    print(f"  - Procesamiento directo ER296: {'[OK]' if direct_ok else '[ERROR]: ' + direct_err}")
    print(f"  - Tiempo Motor Nativo: {t1_direct - t0_direct:.2f} segundos")
    print(f"  - Archivo generado: {test_out_direct.name} ({round(test_out_direct.stat().st_size/1024, 2)} KB)")

    # 4. Prueba del Pipeline Completo (OCR + Corrección + Compresión/Optimización)
    print("\n--- [PRUEBA 2: PDFPipeline Completo E2E (skip_if_has_text=False)] ---")
    config = PipelineConfig(
        lang="spa+eng",
        dpi=300,
        skip_if_has_text=False,  # Forzar OCR completo para medir ER296 + corrector
        run_correction=True,
        run_optimization=True,
        compress_quality="printer",
        ocr_engine="er296",
    )
    pipeline = PDFPipeline(config=config, er296_dir=settings.er296_dir)
    active_engine = pipeline.initialize()
    print(f"  - Motor Activo en Pipeline: {active_engine.upper()}")
    
    output_pdf = settings.output_dir / "e2e_output_40587.pdf"
    
    t0_pipe = time.time()
    result = pipeline.process(sample_pdf, output_pdf)
    t1_pipe = time.time()
    
    print("\n--- [RESULTADO DE EJECUCIÓN PIPELINE] ---")
    print(f"  - Estado: {'[OK EXITOSO]' if result.success else '[FALLIDO]'}")
    print(f"  - Motor Utilizado: {result.engine_used.upper()}")
    print(f"  - Tiempo Total Pipeline: {result.processing_time_s:.2f} s")
    print(f"  - Correcciones Léxicas Aplicadas: {result.corrections_applied}")
    print(f"  - Peso Antes: {result.size_before // 1024} KB")
    print(f"  - Peso Después: {result.size_after // 1024} KB")
    ratio = (result.size_after / max(result.size_before, 1)) * 100
    print(f"  - Ratio de Tamaño Final: {ratio:.1f}% respecto al original")

    # 5. Análisis de Calidad de Salida
    print("\n--- [EVALUACIÓN DE SALIDA Y VALIDACIÓN DE INTEGRIDAD] ---")
    output_metrics = analyze_pdf(output_pdf)
    print(f"  - Validez del PDF de salida: {'[VÁLIDO]' if 'error' not in output_metrics else '[CORRUPTO]: ' + output_metrics.get('error', '')}")
    print(f"  - Páginas en Salida: {output_metrics.get('num_pages', 0)} / {input_metrics['num_pages']}")
    print(f"  - Caracteres extraíbles post-OCR: {output_metrics.get('total_chars', 0)}")
    print(f"  - Muestra de texto post-OCR y Corrección:\n    \"{output_metrics.get('full_text_sample', '')[:180]}...\"")

    # 6. Evaluación Comparativa
    quality_report = {
        "input_pdf": str(sample_pdf.name),
        "input_size_kb": input_metrics["size_kb"],
        "input_pages": input_metrics["num_pages"],
        "input_text_length": input_metrics["total_chars"],
        "output_pdf": str(output_pdf.name),
        "output_size_kb": output_metrics["size_kb"],
        "output_pages": output_metrics.get("num_pages", 0),
        "output_text_length": output_metrics.get("total_chars", 0),
        "engine_used": result.engine_used,
        "processing_time_s": result.processing_time_s,
        "corrections_applied": result.corrections_applied,
        "compression_pct": round(100 - ratio, 1),
        "e2e_status": "PASSED" if result.success and output_metrics.get("num_pages") == input_metrics["num_pages"] else "FAILED"
    }

    report_path = settings.temp_dir / "e2e_quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f" PRUEBA E2E EVALUACIÓN FINAL: {quality_report['e2e_status']}")
    print(f" Reporte guardado en: {report_path}")
    print("=" * 70)
    return quality_report

if __name__ == "__main__":
    run_e2e_test()
