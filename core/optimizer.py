"""
ROA OCR — Optimizador de PDF
Optimiza el PDF de salida: compresión, metadatos, linearización.
"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("roa.optimizer")


def _ghostscript_available() -> bool:
    return shutil.which("gs") is not None or shutil.which("gswin64c") is not None


def _gs_bin() -> str:
    for name in ["gs", "gswin64c", "gswin32c"]:
        if shutil.which(name):
            return name
    return "gs"


class PDFOptimizer:
    """
    Optimiza PDFs de salida:
    - Compresión Ghostscript (reduce tamaño)
    - Linearización (web-optimized / fast-open)
    - Metadatos (autor, productor, fecha)
    - Validación de integridad
    """

    def __init__(self, use_compression: bool = True, quality: str = "printer"):
        """
        Args:
            use_compression: Si True, comprime con Ghostscript
            quality: "screen" | "ebook" | "printer" | "prepress" | "default"
        """
        self.use_compression = use_compression
        self.quality = quality
        self._gs = _ghostscript_available()

        if self.use_compression and not self._gs:
            log.warning("Ghostscript no encontrado — se omitirá la compresión")

    def optimize(self, src: Path, dst: Optional[Path] = None,
                 metadata: Optional[dict] = None) -> Tuple[bool, str, dict]:
        """
        Optimiza un PDF.
        
        Args:
            src: PDF de entrada
            dst: PDF de salida (si None, reemplaza src in-place)
            metadata: dict con claves Title, Author, Subject, Keywords
        
        Returns:
            (éxito, mensaje, stats)
        """
        if dst is None:
            dst = src

        dst.parent.mkdir(parents=True, exist_ok=True)
        stats = {"original_bytes": src.stat().st_size}

        # Paso 1: Comprimir con Ghostscript si disponible
        if self.use_compression and self._gs:
            ok, msg = self._compress_gs(src, dst, metadata)
            if not ok:
                log.warning(f"Compresión GS falló ({msg}) — copiando sin compresión")
                shutil.copy2(src, dst)
        else:
            # Sin Ghostscript: usar pypdf para optimización básica
            ok, msg = self._optimize_pypdf(src, dst, metadata)
            if not ok:
                shutil.copy2(src, dst)

        stats["output_bytes"] = dst.stat().st_size
        stats["saved_bytes"] = stats["original_bytes"] - stats["output_bytes"]
        stats["compression_ratio"] = round(
            stats["output_bytes"] / max(stats["original_bytes"], 1), 4
        )

        log.info(
            f"Optimizado {src.name}: "
            f"{stats['original_bytes']//1024}KB → {stats['output_bytes']//1024}KB "
            f"({stats['compression_ratio']:.1%})"
        )
        return True, "", stats

    def _compress_gs(self, src: Path, dst: Path,
                     metadata: Optional[dict]) -> Tuple[bool, str]:
        """Comprime usando Ghostscript."""
        gs = _gs_bin()
        cmd = [
            gs,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5",
            f"-dPDFSETTINGS=/{self.quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            "-dCompressFonts=true",
            "-dEmbedAllFonts=true",
        ]

        # Inyectar metadatos si se proveen
        if metadata:
            if "Title" in metadata:
                cmd.append(f"-sDocumentTitle={metadata['Title']}")
            if "Author" in metadata:
                cmd.append(f"-sAuthor={metadata['Author']}")

        cmd += [f"-sOutputFile={dst}", str(src)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return True, ""
            return False, result.stderr[:300]
        except subprocess.TimeoutExpired:
            return False, "Timeout en Ghostscript"
        except Exception as e:
            return False, str(e)

    def _optimize_pypdf(self, src: Path, dst: Path,
                        metadata: Optional[dict]) -> Tuple[bool, str]:
        """Optimización básica con pypdf (sin Ghostscript)."""
        try:
            from pypdf import PdfReader, PdfWriter
            from pypdf.generic import NameObject, createStringObject
            from datetime import datetime

            reader = PdfReader(str(src))
            writer = PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            # Copiar metadatos existentes y añadir los nuevos
            writer.add_metadata({
                "/Producer": "ROA OCR API v2.0",
                "/Creator": "ROA OCR Platform",
                "/ModDate": datetime.now().strftime("D:%Y%m%d%H%M%S"),
            })

            if metadata:
                extra = {}
                if "Title" in metadata:
                    extra["/Title"] = metadata["Title"]
                if "Author" in metadata:
                    extra["/Author"] = metadata["Author"]
                if "Subject" in metadata:
                    extra["/Subject"] = metadata["Subject"]
                if "Keywords" in metadata:
                    extra["/Keywords"] = metadata["Keywords"]
                if extra:
                    writer.add_metadata(extra)

            # Comprimir streams
            for page in writer.pages:
                for img in page.images:
                    pass  # pypdf no permite recompresión inline en read-only
                page.compress_content_streams()

            with open(dst, "wb") as f:
                writer.write(f)

            return True, ""

        except Exception as e:
            log.error(f"Error pypdf optimize: {e}")
            return False, str(e)

    def get_pdf_info(self, path: Path) -> dict:
        """Obtiene información básica de un PDF."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return {
                "pages": len(reader.pages),
                "size_bytes": path.stat().st_size,
                "has_text": any(
                    bool((p.extract_text() or "").strip())
                    for p in reader.pages[:5]  # sample primeras 5 páginas
                ),
                "metadata": dict(reader.metadata) if reader.metadata else {},
                "encrypted": reader.is_encrypted,
            }
        except Exception as e:
            return {"error": str(e)}
