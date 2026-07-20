"""
ROA OCR — Motor OCR Unificado
===============================
Estrategia en cascada con iDRS15 como Motor Principal:
  1. iDRS15 Nativo         ← Motor PRINCIPAL (Alto rendimiento, sin dependencias externas)
  2. ocrmypdf + Tesseract  ← Fallback secundario (calidad 97%+)
  3. pytesseract directo    ← Fallback terciario sin ocrmypdf
  4. Acrobat COM (Pro)      ← Fallback legacy (si Acrobat Pro está instalado)
"""

import os
import sys
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Tuple, Optional

from core.idrs15_engine import IDRS15Engine

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


def _check_acrobat_pro() -> bool:
    """Verifica si Adobe Acrobat Pro está disponible."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Adobe\Adobe Acrobat\DC\Registration",
            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            name, _ = winreg.QueryValueEx(key, "AppName")
            if "Pro" in name:
                winreg.CloseKey(key)
                return True
        except (FileNotFoundError, OSError):
            pass
        winreg.CloseKey(key)
    except (FileNotFoundError, OSError):
        pass
    return False


def detect_available_engines(idrs_dir: Optional[Path] = None) -> dict:
    """Detecta qué motores OCR están disponibles en el sistema."""
    idrs = IDRS15Engine(idrs_dir=idrs_dir)
    engines = {
        "idrs15": idrs.initialize(),
        "ocrmypdf": _check_ocrmypdf(),
        "tesseract": _check_tesseract(),
        "acrobat_pro": _check_acrobat_pro(),
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
            "--output-type", "pdfa",
            "--optimize", "1",
            "--jobs", "2",
            "--image-dpi", str(dpi),
            "--language", ocr_lang,
            "--rotate-pages",
            "--deskew",
        ]

        if skip_text:
            cmd.append("--skip-text")

        cmd += [str(src), str(dst)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                return True, ""
            else:
                if result.returncode == 6 and skip_text:
                    shutil.copy2(src, dst)
                    return True, "PDF ya tenía texto — copiado sin OCR"
                return False, result.stderr[:500]
        except subprocess.TimeoutExpired:
            return False, "Timeout: PDF demasiado grande o complejo"
        except Exception as e:
            return False, str(e)


# ──────────────────────────────────────────────────────────────────────────────
# Motor 3: pytesseract directo (fallback)
# ──────────────────────────────────────────────────────────────────────────────

class TesseractDirectEngine:
    """Motor de fallback directo vía pytesseract."""

    def __init__(self):
        self._available = False

    def initialize(self) -> bool:
        self._available = _check_tesseract()
        if not self._available:
            log.warning("Tesseract no encontrado en PATH")
            return False
        try:
            import pytesseract  # noqa
            import pdf2image  # noqa
            log.info("✅ Motor Tesseract directo disponible")
            return True
        except ImportError as e:
            log.warning(f"Dependencias faltantes para Tesseract directo: {e}")
            return False

    def process_pdf(self, src: Path, dst: Path, lang: str = "spa+eng",
                    dpi: int = 300) -> Tuple[bool, str]:
        try:
            import pytesseract
            from pdf2image import convert_from_path
            from pypdf import PdfWriter, PdfReader
            import io

            dst.parent.mkdir(parents=True, exist_ok=True)
            images = convert_from_path(str(src), dpi=dpi)
            writer = PdfWriter()

            for img in images:
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    img, lang=lang.replace("+", "+"), extension="pdf"
                )
                reader = PdfReader(io.BytesIO(pdf_bytes))
                writer.add_page(reader.pages[0])

            with open(dst, "wb") as f:
                writer.write(f)

            return True, ""
        except Exception as e:
            log.error(f"Error Tesseract directo en {src.name}: {e}")
            return False, str(e)


# ──────────────────────────────────────────────────────────────────────────────
# Motor 4: Adobe Acrobat COM (Acrobat Pro)
# ──────────────────────────────────────────────────────────────────────────────

class AcrobatOCREngine:
    """Motor OCR usando COM de Adobe Acrobat Pro."""

    def __init__(self):
        self.app = None
        self._initialized = False

    def initialize(self) -> bool:
        if sys.platform != "win32":
            return False
        if not _check_acrobat_pro():
            return False
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            self.app = win32com.client.Dispatch("AcroExch.App")
            self.app.Hide()
            self._initialized = True
            log.info("✅ Motor Acrobat COM inicializado")
            return True
        except Exception as e:
            log.warning(f"Motor Acrobat COM no disponible: {e}")
            return False

    def process_pdf(self, src: Path, dst: Path, lang: str = "spa+eng") -> Tuple[bool, str]:
        if not self._initialized:
            return False, "Motor no inicializado"

        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            dst.parent.mkdir(parents=True, exist_ok=True)
            pd_doc = win32com.client.Dispatch("AcroExch.PDDoc")

            if not pd_doc.Open(str(src)):
                return False, f"No se pudo abrir: {src}"

            js = pd_doc.GetJSObject()

            ocr_done = False
            for ocr_method in ["OCR", "doOCRLater", "RecognizeText"]:
                try:
                    if hasattr(js, ocr_method):
                        method = getattr(js, ocr_method)
                        if ocr_method == "OCR":
                            method("ClearScan", True)
                        elif ocr_method == "doOCRLater":
                            method()
                        ocr_done = True
                        break
                except Exception:
                    continue

            if not ocr_done:
                pd_doc.Close()
                return False, "OCR no disponible en esta versión de Acrobat"

            pd_doc.Save(1, str(dst))
            pd_doc.Close()
            return True, ""

        except Exception as e:
            log.error(f"Error Acrobat OCR en {src.name}: {e}")
            return False, str(e)
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def shutdown(self):
        if self.app and self._initialized:
            try:
                self.app.Exit()
            except Exception:
                pass
        self._initialized = False


# ──────────────────────────────────────────────────────────────────────────────
# Motor Unificado — Orquesta la cascada (Prioridad #1: iDRS15)
# ──────────────────────────────────────────────────────────────────────────────

class UnifiedOCREngine:
    """
    Orquestador de motores OCR en cascada.
    Prioridad: idrs15 → ocrmypdf → tesseract → acrobat_pro
    """

    def __init__(self, preferred: str = "idrs15",
                 idrs_dir: Optional[Path] = None,
                 lang: str = "spa+eng", dpi: int = 300):
        self.preferred = preferred
        self.lang = lang
        self.dpi = dpi

        self._idrs15 = IDRS15Engine(idrs_dir=idrs_dir)
        self._ocrmypdf = OcrmypdfEngine()
        self._tesseract = TesseractDirectEngine()
        self._acrobat = AcrobatOCREngine()

        self._engines: dict = {}
        self._active_engine: Optional[str] = None

    def initialize(self) -> str:
        """Inicializa el mejor motor disponible. Retorna el nombre del motor activo."""
        idrs15_ok = self._idrs15.initialize()
        ocrmypdf_ok = self._ocrmypdf.initialize()
        tesseract_ok = self._tesseract.initialize()
        acrobat_ok = self._acrobat.initialize()

        self._engines = {
            "idrs15": (idrs15_ok, self._idrs15),
            "ocrmypdf": (ocrmypdf_ok, self._ocrmypdf),
            "tesseract": (tesseract_ok, self._tesseract),
            "acrobat_pro": (acrobat_ok, self._acrobat),
        }

        # Determinar orden según preferencia (Default: idrs15)
        priority = ["idrs15", "ocrmypdf", "tesseract", "acrobat_pro"]
        if self.preferred in self._engines and self.preferred != "auto":
            priority = [self.preferred] + [e for e in priority if e != self.preferred]

        for name in priority:
            ok, _ = self._engines.get(name, (False, None))
            if ok:
                self._active_engine = name
                log.info(f"🚀 Motor principal activo: {name.upper()}")
                return name

        raise RuntimeError(
            "❌ No hay motores OCR disponibles. Verifica la carpeta iDRS15 o instala ocrmypdf/tesseract."
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
        cascade = ["idrs15", "ocrmypdf", "tesseract", "acrobat_pro"]

        if self._active_engine:
            cascade = [self._active_engine] + [e for e in cascade if e != self._active_engine]

        for name in cascade:
            ok_init, instance = self._engines.get(name, (False, None))
            if not ok_init or instance is None:
                continue

            log.info(f"⚙️  Procesando {src.name} con motor {name.upper()}")
            try:
                if name == "idrs15":
                    success, err = instance.process_pdf(src, dst, lang=use_lang, dpi=self.dpi)
                elif name == "ocrmypdf":
                    success, err = instance.process_pdf(
                        src, dst, lang=use_lang, dpi=self.dpi, skip_text=skip_text
                    )
                elif name == "tesseract":
                    success, err = instance.process_pdf(
                        src, dst, lang=use_lang, dpi=self.dpi
                    )
                elif name == "acrobat_pro":
                    success, err = instance.process_pdf(src, dst, lang=use_lang)
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
        self._acrobat.shutdown()

    @property
    def active_engine(self) -> Optional[str]:
        return self._active_engine

    def status(self) -> dict:
        return {
            name: {"available": ok, "active": name == self._active_engine}
            for name, (ok, _) in self._engines.items()
        }
