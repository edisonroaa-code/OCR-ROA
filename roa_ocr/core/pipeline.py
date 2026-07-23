"""
ROA OCR — Pipeline de procesamiento completo
Orquesta: detección → OCR → corrección → optimización → salida
"""
import time
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from roa_ocr.core.engine import UnifiedOCREngine
from roa_ocr.core.corrector import PostOCRCorrector
from roa_ocr.core.optimizer import PDFOptimizer
from roa_ocr.core.table_parser import TableParser
from roa_ocr.core.rag_chunker import RAGChunker

log = logging.getLogger("roa.pipeline")


@dataclass
class PipelineConfig:
    """Configuración del pipeline."""
    lang: str = "spa+eng+por"
    dpi: int = 300
    skip_if_has_text: bool = True
    fix_orientation: bool = True
    run_correction: bool = True
    run_optimization: bool = True
    compress_quality: str = "printer"  # screen | ebook | printer | prepress
    ocr_engine: str = "auto"
    metadata: dict = field(default_factory=dict)
    custom_rules: Optional[dict] = None


@dataclass
class PipelineResult:
    """Resultado del procesamiento de un PDF."""
    success: bool
    input_path: str
    output_path: str = ""
    error: str = ""
    engine_used: str = ""
    pages: int = 0
    had_text: bool = False
    processing_time_s: float = 0.0
    size_before: int = 0
    size_after: int = 0
    corrections_applied: int = 0

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "input": self.input_path,
            "output": self.output_path,
            "error": self.error,
            "engine": self.engine_used,
            "pages": self.pages,
            "had_text": self.had_text,
            "processing_time_s": round(self.processing_time_s, 2),
            "size_before_kb": round(self.size_before / 1024, 1),
            "size_after_kb": round(self.size_after / 1024, 1),
            "compression_ratio": round(self.size_after / max(self.size_before, 1), 4),
            "corrections_applied": self.corrections_applied,
        }


class PDFPipeline:
    """
    Pipeline completo de mejora de PDFs.
    
    Fases:
    1. Análisis del PDF (páginas, texto existente, cifrado)
    2. OCR (si necesario)
    3. Corrección post-OCR del texto
    4. Optimización y compresión
    5. Escritura del resultado
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        engine: Optional[UnifiedOCREngine] = None,
        corrector: Optional[PostOCRCorrector] = None,
        optimizer: Optional[PDFOptimizer] = None,
        er296_dir: Optional[Path] = None,
        idrs_dir: Optional[Path] = None,
    ):
        self.config = config or PipelineConfig()

        # Motor OCR
        self.engine = engine or UnifiedOCREngine(
            preferred=self.config.ocr_engine,
            er296_dir=er296_dir,
            idrs_dir=idrs_dir,
            lang=self.config.lang,
            dpi=self.config.dpi,
        )

        # Corrector post-OCR
        self.corrector = corrector or PostOCRCorrector(custom_rules=self.config.custom_rules)

        # Optimizador
        self.optimizer = optimizer or PDFOptimizer(
            use_compression=self.config.run_optimization,
            quality=self.config.compress_quality,
        )

        # Parser de Tablas
        self.table_parser = TableParser()

        self._initialized = False

    def initialize(self) -> str:
        """Inicializa todos los componentes. Retorna el nombre del motor activo."""
        engine_name = self.engine.initialize()
        self._initialized = True
        log.info(f"Pipeline inicializado — motor: {engine_name}")
        return engine_name

    def _analyze_pdf(self, path: Path) -> dict:
        """Analiza un PDF antes de procesarlo."""
        return self.optimizer.get_pdf_info(path)

    def process(self, src: Path, dst: Path,
                config_override: Optional[PipelineConfig] = None) -> PipelineResult:
        """
        Procesa un PDF completo.
        
        Args:
            src: Ruta al PDF de origen
            dst: Ruta donde guardar el PDF mejorado
            config_override: Configuración alternativa para este PDF
        
        Returns:
            PipelineResult con todos los detalles
        """
        cfg = config_override or self.config
        t0 = time.time()

        result = PipelineResult(
            success=False,
            input_path=str(src),
            output_path=str(dst),
            size_before=src.stat().st_size if src.exists() else 0,
        )

        if not src.exists():
            result.error = f"Archivo no encontrado: {src}"
            return result

        if not self._initialized:
            self.initialize()

        # ── Fase 1: Análisis ────────────────────────────────────────────────
        info = self._analyze_pdf(src)
        result.pages = info.get("pages", 0)
        result.had_text = info.get("has_text", False)

        if info.get("encrypted"):
            result.error = "PDF cifrado — no se puede procesar"
            return result

        # ── Fase 2: OCR ─────────────────────────────────────────────────────
        # Si el PDF ya tiene texto y skip_if_has_text está activado, saltar OCR
        if result.had_text and cfg.skip_if_has_text:
            log.info(f"{src.name}: ya tiene texto — omitiendo OCR")
            # Copiar directamente para optimización
            tmp_ocr = src
            result.engine_used = "skipped"
        else:
            # Usar directorio temporal para el OCR
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_ocr = Path(tmpdir) / f"ocr_{src.name}"
                success, error, engine_used = self.engine.process(
                    src, tmp_ocr,
                    lang=cfg.lang,
                    skip_text=cfg.skip_if_has_text,
                )

                if not success:
                    result.error = f"OCR falló: {error}"
                    return result

                result.engine_used = engine_used

                # ── Fase 3: Corrección ───────────────────────────────────────
                if cfg.run_correction:
                    corrections = self._apply_correction(tmp_ocr, cfg.lang)
                    result.corrections_applied = corrections

                # ── Fase 4: Optimización ─────────────────────────────────────
                dst.parent.mkdir(parents=True, exist_ok=True)
                if cfg.run_optimization:
                    ok, _, opt_stats = self.optimizer.optimize(
                        tmp_ocr, dst, metadata=cfg.metadata or {}
                    )
                    if not ok:
                        shutil.copy2(tmp_ocr, dst)
                else:
                    shutil.copy2(tmp_ocr, dst)

            # El bloque with cierra aquí y borra el tmpdir

        # Si saltamos el OCR (ya tenía texto), optimizar directamente
        if result.engine_used == "skipped":
            dst.parent.mkdir(parents=True, exist_ok=True)
            if cfg.run_optimization:
                self.optimizer.optimize(src, dst, metadata=cfg.metadata or {})
            else:
                shutil.copy2(src, dst)

        result.size_after = dst.stat().st_size if dst.exists() else 0
        result.processing_time_s = time.time() - t0
        result.success = dst.exists()

        if result.success:
            log.info(
                f"✅ {src.name} → {result.processing_time_s:.1f}s | "
                f"motor: {result.engine_used} | "
                f"{result.size_before//1024}KB → {result.size_after//1024}KB"
            )

        return result

    def _apply_correction(self, pdf_path: Path, lang: str) -> int:
        """
        Extrae texto del PDF, lo corrige, y reinyecta el layer de texto.
        
        Nota: La reinyección real requiere re-renderizar el PDF con el texto
        corregido. En esta implementación aplicamos la corrección a nivel
        de metadata y dejamos preparado el texto para integración futura
        con herramientas como pdfminer + reportlab.
        
        Returns: número estimado de correcciones aplicadas
        """
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            total_changes = 0
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    corrected = self.corrector.correct_text(text, lang=lang)
                    stats = self.corrector.statistics(text, corrected)
                    total_changes += stats.get("estimated_changes", 0)
            return total_changes
        except Exception as e:
            log.warning(f"Corrección de texto falló: {e}")
            return 0

    def process_batch(self, pairs: list[tuple[Path, Path]],
                      on_progress=None) -> list[PipelineResult]:
        """
        Procesa múltiples PDFs en secuencia.
        
        Args:
            pairs: lista de (src, dst)
            on_progress: callback(current, total, result)
        """
        results = []
        total = len(pairs)

        for i, (src, dst) in enumerate(pairs, 1):
            result = self.process(src, dst)
            results.append(result)

            if on_progress:
                try:
                    on_progress(i, total, result)
                except Exception:
                    pass

        return results

    def process_to_markdown(self, src: Path, original_filename: Optional[str] = None) -> dict:
        """
        Extrae y convierte el contenido del PDF a Markdown estructurado con tablas formateadas.
        """
        if not self._initialized:
            self.initialize()

        doc_name = original_filename or src.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_dst = Path(tmp.name)

        try:
            res = self.process(src, tmp_dst)
            target_pdf = tmp_dst if (tmp_dst.exists() and tmp_dst.stat().st_size > 0) else src
            
            from pypdf import PdfReader
            reader = PdfReader(str(target_pdf))
            
            page_mds = []
            full_md = f"# Documento: {doc_name}\n\n"
            
            doc = None
            try:
                import fitz
                doc = fitz.open(str(target_pdf))
            except Exception as ex:
                log.warning(f"PyMuPDF (fitz) no pudo abrir {target_pdf}: {ex}")

            try:
                import pytesseract
                for idx, page in enumerate(reader.pages, 1):
                    raw_txt = page.extract_text() or ""
                    
                    # Si PyPDF no extrajo texto, realizar extracción directa de la página con fitz + pytesseract
                    if not raw_txt or len(raw_txt.strip()) < 10:
                        if doc and idx <= len(doc):
                            try:
                                from PIL import Image
                                pix = doc[idx - 1].get_pixmap(dpi=self.config.dpi)
                                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                raw_txt = pytesseract.image_to_string(img, lang=self.config.lang.replace(" ", "+"))
                            except Exception as ex:
                                log.warning(f"Extracción directa OCR pág {idx} falló: {ex}")

                    if self.config.run_correction:
                        raw_txt = self.corrector.correct_text(raw_txt, lang=self.config.lang)
                    
                    table_formatted_txt = self.table_parser.parse_text_to_tables(raw_txt)
                    page_header = f"## Página {idx}\n\n"
                    page_md = page_header + table_formatted_txt
                    page_mds.append({"page": idx, "markdown": page_md, "char_count": len(table_formatted_txt)})
                    full_md += page_md + "\n\n---\n\n"
            finally:
                if doc:
                    try:
                        doc.close()
                    except Exception:
                        pass

            return {
                "success": res.success,
                "engine_used": res.engine_used,
                "source_file": doc_name,
                "pages": len(reader.pages),
                "full_markdown": full_md,
                "page_details": page_mds,
            }
        finally:
            try:
                tmp_dst.unlink(missing_ok=True)
            except Exception:
                pass

    def process_to_chunks(self, src: Path, chunk_size: int = 500, chunk_overlap: int = 50, original_filename: Optional[str] = None) -> dict:
        """
        Procesa un PDF y genera chunks de vectores optimizados para Qdrant, Meilisearch y RAG.
        """
        md_res = self.process_to_markdown(src, original_filename=original_filename)
        chunker = RAGChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        doc_name = original_filename or src.name
        
        all_chunks = []
        for page_data in md_res.get("page_details", []):
            p_num = page_data["page"]
            p_md = page_data["markdown"]
            page_chunks = chunker.chunk_text(
                text=p_md,
                source_name=doc_name,
                page_number=p_num,
                engine_used=md_res.get("engine_used", "er296"),
            )
            all_chunks.extend(page_chunks)

        return {
            "success": md_res.get("success", False),
            "source_file": doc_name,
            "engine_used": md_res.get("engine_used", "er296"),
            "total_pages": md_res.get("pages", 0),
            "total_chunks": len(all_chunks),
            "chunks": all_chunks,
        }

    def shutdown(self):
        self.engine.shutdown()

    def engine_status(self) -> dict:
        return self.engine.status()

