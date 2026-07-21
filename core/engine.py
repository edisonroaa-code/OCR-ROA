"""
ROA OCR — Motor OCR Unificado
==============================
Estrategia en cascada con ER296 como Motor Principal:
  1. ER296 Nativo          ← Motor PRINCIPAL (Alto rendimiento, sin dependencias externas)
  2. ocrmypdf + Tesseract  ← Fallback secundario (calidad 97%+)
  3. pytesseract directo    ← Fallback terciario sin ocrmypdf
"""

import os
import sys
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Tuple, Optional

from core.er296_engine import ER296Engine, IDRS15Engine

log = logging.getLogger("roa.engine")


# ──────────────────────────────────────────────────────────────────────────────
# Detección de motores disponibles
# ──────────────────────────────────────────────────────────────────────────────

def _check_ocrmypdf() -> bool:
    """Verifica si ocrmypdf está instalado."""
    return shutil.which("ocrmypdf") is not None


def _check_tesseract() -> bool:
    """Verifica si tesseract está en PATH."""
    return shutil.which("tesseract") is not None


def detect_available_engines(er296_dir: Optional[Path] = None, idrs_dir: Optional[Path] = None) -> dict:
    """Detecta qué motores OCR están disponibles en el sistema."""
    target_dir = er296_dir or idrs_dir
    er296 = ER296Engine(er296_dir=target_dir)
    er296_ok = er296.initialize()
    engines = {
        "er296": er296_ok,
        "idrs15": er296_ok,  # Alias de compatibilidad
        "ocrmypdf": _check_ocrmypdf(),
        "tesseract": _check_tesseract(),
    }
    log.info(f"Motores OCR detectados: {engines}")
    return engines


# ──────────────────────────────────────────────────────────────────────────────
# Motor 2: ocrmypdf (Tesseract + Ghostscript)
# ──────────────────────────────────────────────────────────────────────────────

class OcrmypdfEngine:
    """Motor OCR usando ocrmypdf + Tesseract."""

    def __init__(self):
        self._available = False

    def initialize(self) -> bool:
        self._available = _check_ocrmypdf()
        if self._available:
            log.info("✅ Motor ocrmypdf disponible")
        else:
            log.warning("Motor ocrmypdf no encontrado")
        return self._available

    def process_pdf(self, src: Path, dst: Path, lang: str = "spa+eng",
                    dpi: int = 300, skip_text: bool = True) -> Tuple[bool, str]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        ocr_lang = lang.replace(" ", "+")

        cmd = [
            "ocrmypdf",
            "--language", ocr_lang,
            "--image-dpi", str(dpi),
            "--output-type", "pdf",
            "--jobs", "2",
        ]
        if skip_text:
            cmd.append("--skip-text")
        else:
            cmd.append("--force-ocr")

        cmd.extend([str(src), str(dst)])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if res.returncode == 0:
                log.info(f"✅ ocrmypdf exitoso en {src.name}")
                return True, ""
            elif res.returncode == 6:
                log.info(f"ℹ️  ocrmypdf: {src.name} ya tiene texto. Copiando...")
                shutil.copy2(src, dst)
                return True, "ya_tiene_texto"
            else:
                log.error(f"❌ ocrmypdf error ({res.returncode}): {res.stderr[:300]}")
                return False, res.stderr[:300]
        except subprocess.TimeoutExpired:
            return False, "Timeout (300s) en ocrmypdf"
        except Exception as e:
            return False, str(e)


# ──────────────────────────────────────────────────────────────────────────────
# Motor 3: Tesseract directo (pytesseract + pdf2image)
# ──────────────────────────────────────────────────────────────────────────────

class TesseractDirectEngine:
    """Motor OCR secundario con Tesseract directo."""

    def __init__(self):
        self._available = False

    def initialize(self) -> bool:
        self._available = _check_tesseract()
        if self._available:
            log.info("✅ Motor Tesseract directo disponible")
        else:
            log.warning("Tesseract no encontrado en PATH")
        return self._available

    def process_pdf(self, src: Path, dst: Path, lang: str = "spa+eng",
                    dpi: int = 300) -> Tuple[bool, str]:
        if not self._available:
            return False, "Tesseract no disponible"

        try:
            import pytesseract
            from pdf2image import convert_from_path
            from pypdf import PdfWriter, PdfReader
            import io

            ocr_lang = lang.replace(" ", "+")
            images = convert_from_path(str(src), dpi=dpi)

            writer = PdfWriter()
            dst.parent.mkdir(parents=True, exist_ok=True)

            for i, page_img in enumerate(images):
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    page_img, lang=ocr_lang, extension="pdf"
                )
                reader = PdfReader(io.BytesIO(pdf_bytes))
                for page in reader.pages:
                    writer.add_page(page)

            with open(dst, "wb") as f:
                writer.write(f)

            log.info(f"✅ Tesseract directo procesó {len(images)} págs en {src.name}")
            return True, ""

        except Exception as e:
            log.error(f"❌ Error Tesseract en {src.name}: {e}")
            return False, str(e)


# ──────────────────────────────────────────────────────────────────────────────
# Motor Unificado — Orquesta la cascada (Prioridad #1: ER296)
# ──────────────────────────────────────────────────────────────────────────────

class UnifiedOCREngine:
    """
    Orquestador de motores OCR en cascada.
    Prioridad: er296 → ocrmypdf → tesseract
    """

    def __init__(self, preferred: str = "er296",
                 er296_dir: Optional[Path] = None,
                 idrs_dir: Optional[Path] = None,
                 lang: str = "spa+eng", dpi: int = 300):
        # Mapeo de alias para mantener compatibilidad con peticiones existentes
        pref_clean = preferred.lower() if preferred else "er296"
        if pref_clean in ("idrs15", "idrs15_direct", "er296_direct"):
            pref_clean = "er296"

        self.preferred = pref_clean
        self.lang = lang
        self.dpi = dpi

        target_dir = er296_dir or idrs_dir
        self._er296 = ER296Engine(er296_dir=target_dir)
        self._idrs15 = self._er296  # Alias
        self._ocrmypdf = OcrmypdfEngine()
        self._tesseract = TesseractDirectEngine()

        self._engines: dict = {}
        self._active_engine: Optional[str] = None

    def initialize(self) -> str:
        """Inicializa el mejor motor disponible. Retorna el nombre del motor activo."""
        er296_ok = self._er296.initialize()
        ocrmypdf_ok = self._ocrmypdf.initialize()
        tesseract_ok = self._tesseract.initialize()

        self._engines = {
            "er296": (er296_ok, self._er296),
            "idrs15": (er296_ok, self._er296),  # Alias
            "ocrmypdf": (ocrmypdf_ok, self._ocrmypdf),
            "tesseract": (tesseract_ok, self._tesseract),
        }

        # Determinar orden según preferencia (Default: er296)
        priority = ["er296", "ocrmypdf", "tesseract"]
        if self.preferred in self._engines and self.preferred != "auto":
            priority = [self.preferred] + [e for e in priority if e != self.preferred]

        for name in priority:
            ok, _ = self._engines.get(name, (False, None))
            if ok:
                self._active_engine = name
                log.info(f"🚀 Motor principal activo: {name.upper()}")
                return name

        raise RuntimeError(
            "❌ No hay motores OCR disponibles. Verifica la carpeta ER296 o instala ocrmypdf/tesseract."
        )

    def process(self, src: Path, dst: Path,
                lang: Optional[str] = None,
                skip_text: bool = True) -> Tuple[bool, str, str]:
        """
        Procesa un PDF con el motor activo y hace fallback si falla.

        Returns:
            (éxito, mensaje_error, motor_usado)
        """
        use_lang = lang or self.lang
        cascade = ["er296", "ocrmypdf", "tesseract"]

        if self._active_engine:
            cascade = [self._active_engine] + [e for e in cascade if e != self._active_engine]

        for name in cascade:
            ok_init, instance = self._engines.get(name, (False, None))
            if not ok_init or instance is None:
                continue

            log.info(f"⚙️  Procesando {src.name} con motor {name.upper()}")
            try:
                if name in ("er296", "idrs15"):
                    success, err = instance.process_pdf(src, dst, lang=use_lang, dpi=self.dpi)
                elif name == "ocrmypdf":
                    success, err = instance.process_pdf(
                        src, dst, lang=use_lang, dpi=self.dpi, skip_text=skip_text
                    )
                elif name == "tesseract":
                    success, err = instance.process_pdf(
                        src, dst, lang=use_lang, dpi=self.dpi
                    )
                else:
                    continue

                if success:
                    log.info(f"✅ {src.name} procesado exitosamente con {name.upper()}")
                    return True, "", name
                else:
                    log.warning(f"Motor {name} falló en {src.name}: {err} — intentando fallback")

            except Exception as e:
                log.error(f"Excepción en motor {name}: {e}")
                continue

        return False, "Todos los motores fallaron", "none"

    def process_image(self, src: Path, dst: Path,
                      lang: Optional[str] = None) -> Tuple[bool, str, str]:
        """Procesa una imagen directamente con OCR."""
        use_lang = lang or self.lang
        try:
            from PIL import Image

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            img = Image.open(src)
            img.save(tmp_path, "PDF", resolution=self.dpi)

            result = self.process(tmp_path, dst, lang=use_lang)
            tmp_path.unlink(missing_ok=True)

            return result
        except Exception as e:
            return False, str(e), "none"

    def shutdown(self):
        pass

    @property
    def active_engine(self) -> Optional[str]:
        return self._active_engine

    def status(self) -> dict:
        return {
            name: {"available": ok, "active": name == self._active_engine}
            for name, (ok, _) in self._engines.items()
        }
