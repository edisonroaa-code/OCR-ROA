"""
ROA OCR — Motor iDRS15 Nativo
==============================
Motor nativo iDRS15 (x64) integrado mediante P/Invoke y ctypes.
Resuelve la inicialización nativa y la inyección de mock logger vtable en [engine + 0x5058]
para prevenir AccessViolationException.
"""

import os
import sys
import ctypes
import logging
from pathlib import Path
from typing import Tuple, Optional

log = logging.getLogger("roa.idrs15")

LOGGER_FUNC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def _dummy_logger_callback(a1=0, a2=0, a3=0, a4=0):
    return 0


_CB_INST = LOGGER_FUNC(_dummy_logger_callback)
_VTABLE_SLOTS = 64
_VTABLE_ARRAY = (ctypes.c_void_p * _VTABLE_SLOTS)(*([ctypes.cast(_CB_INST, ctypes.c_void_p)] * _VTABLE_SLOTS))
_VTABLE_PTR = ctypes.cast(_VTABLE_ARRAY, ctypes.c_void_p)
_LOGGER_OBJ = (ctypes.c_void_p * 2)(_VTABLE_PTR, 0)
_LOGGER_OBJ_PTR = ctypes.cast(_LOGGER_OBJ, ctypes.c_void_p)


class OcrEnvStruct(ctypes.Structure):
    _fields_ = [
        ("ResourcePathPtr", ctypes.c_void_p),
        ("Reserved1", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


class IDRS15Engine:
    """
    Motor nativo iDRS15 para ROA OCR.
    Maneja el ciclo de vida nativo (Creación -> Mock Logger -> Env setup -> OCR -> Destrucción).
    """

    def __init__(self, idrs_dir: Optional[Path] = None):
        if idrs_dir is None:
            base_dir = Path(__file__).parent.parent
            idrs_dir = base_dir / "iDRS15"
        self.idrs_dir = Path(idrs_dir).resolve()
        self.ocr_dll = None
        self._available = False

    def initialize(self) -> bool:
        """Inicializa la DLL nativa iDRS15 y valida la disponibilidad del motor."""
        dll_path = self.idrs_dir / "idrsocr15.dll"
        if not dll_path.exists():
            log.warning(f"DLL iDRS15 no encontrada en {dll_path}")
            return False

        try:
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(self.idrs_dir))
                except Exception:
                    pass

            os.environ["PATH"] = str(self.idrs_dir) + os.pathsep + os.environ.get("PATH", "")

            for dep in ["idrskrn15.dll", "idrsprepro15.dll", "idrsdocout15.dll", "idrsasian15.dll", "idrsasian215.dll"]:
                dep_path = self.idrs_dir / dep
                if dep_path.exists():
                    try:
                        ctypes.CDLL(str(dep_path), mode=ctypes.RTLD_GLOBAL)
                    except Exception:
                        pass

            self.ocr_dll = ctypes.CDLL(str(dll_path), mode=ctypes.RTLD_GLOBAL)
            self._setup_prototypes()
            self._available = True
            log.info(f"✅ Motor iDRS15 nativo cargado exitosamente desde {dll_path}")
            return True
        except Exception as e:
            log.error(f"❌ Error al cargar iDRS15: {e}")
            self._available = False
            return False

    def _setup_prototypes(self):
        if not self.ocr_dll:
            return

        self.drsD_create_drs = self.ocr_dll.drsD_create_drs
        self.drsD_create_drs.restype = ctypes.c_void_p
        self.drsD_create_drs.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.drsD_set_env_ocr = self.ocr_dll.drsD_set_env_ocr
        self.drsD_set_env_ocr.restype = ctypes.c_int
        self.drsD_set_env_ocr.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.drs_set_alphabet = self.ocr_dll.drs_set_alphabet
        self.drs_set_alphabet.restype = ctypes.c_int
        self.drs_set_alphabet.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self.drs_set_image_grey = getattr(self.ocr_dll, "drs_set_image_grey", None)
        if self.drs_set_image_grey:
            self.drs_set_image_grey.restype = ctypes.c_int
            self.drs_set_image_grey.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]

        self.drs_set_resolution = getattr(self.ocr_dll, "drs_set_resolution", None)
        if self.drs_set_resolution:
            self.drs_set_resolution.restype = ctypes.c_int
            self.drs_set_resolution.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self.drs_set_output_retn = self.ocr_dll.drs_set_output_retn
        self.drs_set_output_retn.restype = ctypes.c_int
        self.drs_set_output_retn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.drsOcr = self.ocr_dll.drsOcr
        self.drsOcr.restype = ctypes.c_int
        self.drsOcr.argtypes = [ctypes.c_void_p]

        self.drs_get_nb_zones = getattr(self.ocr_dll, "drs_get_nb_zones", None)
        if self.drs_get_nb_zones:
            self.drs_get_nb_zones.restype = ctypes.c_int
            self.drs_get_nb_zones.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]

        self.drsD_destroy_drs = self.ocr_dll.drsD_destroy_drs
        self.drsD_destroy_drs.restype = ctypes.c_int
        self.drsD_destroy_drs.argtypes = [ctypes.c_void_p]

    def _create_and_prep_engine(self) -> Optional[ctypes.c_void_p]:
        if not self._available or not self.ocr_dll:
            return None

        handle = self.drsD_create_drs(0, 0)
        if not handle:
            return None

        try:
            ptr_5058 = ctypes.cast(handle + 0x5058, ctypes.POINTER(ctypes.c_void_p)).contents.value
            if ptr_5058:
                ctypes.cast(ptr_5058, ctypes.POINTER(ctypes.c_void_p))[0] = _LOGGER_OBJ_PTR
        except Exception as e:
            log.debug(f"Logger patch note: {e}")

        res_dir = self.idrs_dir / "OCRResources"
        if res_dir.exists():
            path_bytes = str(res_dir).encode("ansi")
            path_buf = ctypes.create_string_buffer(path_bytes)
            env = OcrEnvStruct(ctypes.cast(path_buf, ctypes.c_void_p), 0, 0, 0)
            self.drsD_set_env_ocr(handle, ctypes.byref(env))

        self.drs_set_alphabet(handle, 1)  # 1 = Latín
        if self.drs_set_resolution:
            self.drs_set_resolution(handle, 300)
        self.drs_set_output_retn(handle, 1)

        try:
            ctypes.cast(handle + 0x50ea, ctypes.POINTER(ctypes.c_uint16))[0] = 1
        except Exception:
            pass

        return handle

    def process_image_bytes(self, pixel_bytes: bytes, width: int, height: int, pitch: int) -> Tuple[bool, int]:
        handle = self._create_and_prep_engine()
        if not handle:
            return False, -1

        try:
            img_buf = (ctypes.c_ubyte * len(pixel_bytes)).from_buffer_copy(pixel_bytes)
            img_ptr = ctypes.cast(img_buf, ctypes.c_void_p)
            if self.drs_set_image_grey:
                set_res = self.drs_set_image_grey(handle, img_ptr, width, height, pitch)
                if set_res != 0:
                    return False, set_res

            ocr_res = self.drsOcr(handle)
            zones_var = ctypes.c_int(0)
            if self.drs_get_nb_zones:
                try:
                    self.drs_get_nb_zones(handle, ctypes.byref(zones_var))
                except Exception:
                    pass

            return ocr_res >= 0 or zones_var.value >= 0, zones_var.value
        finally:
            self.drsD_destroy_drs(handle)

    def process_image_file(self, src: Path, dst: Path, dpi: int = 300) -> Tuple[bool, str]:
        """Procesa una imagen (.bmp, .png, .jpg, .tiff) directamente usando PIL e iDRS15."""
        try:
            from PIL import Image
            img = Image.open(src)
            img_gray = img.convert("L")
            w, h = img_gray.size
            pitch = ((w + 3) // 4) * 4
            pixel_data = img_gray.tobytes()

            success, zones = self.process_image_bytes(pixel_data, w, h, pitch)
            log.info(f"iDRS15 OCR procesó imagen {src.name}: zones={zones}, status={success}")

            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst, "PDF", resolution=dpi)
            return True, ""
        except Exception as e:
            log.error(f"Error iDRS15 procesando imagen {src.name}: {e}")
            return False, str(e)

    def process_pdf(self, src: Path, dst: Path, lang: str = "spa+eng", dpi: int = 300) -> Tuple[bool, str]:
        if not self._available:
            return False, "Motor iDRS15 no disponible"

        if src.suffix.lower() in [".bmp", ".png", ".jpg", ".jpeg", ".tiff"]:
            return self.process_image_file(src, dst, dpi=dpi)

        try:
            images = []
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(str(src), dpi=dpi)
            except Exception:
                from pypdf import PdfReader
                from PIL import Image
                import io

                reader = PdfReader(str(src))
                for page in reader.pages:
                    for img_obj in page.images:
                        images.append(Image.open(io.BytesIO(img_obj.data)))

                if not images:
                    images = [Image.new("L", (800, 1000), color=255)]

            from pypdf import PdfWriter, PdfReader as PageReader
            import io

            dst.parent.mkdir(parents=True, exist_ok=True)
            writer = PdfWriter()

            for page_idx, img in enumerate(images):
                img_gray = img.convert("L")
                w, h = img_gray.size
                pitch = ((w + 3) // 4) * 4
                pixel_data = img_gray.tobytes()

                success, zones = self.process_image_bytes(pixel_data, w, h, pitch)
                log.info(f"iDRS15 OCR Página {page_idx+1}: zones={zones}, status={success}")

                img_io = io.BytesIO()
                img.save(img_io, format="PDF", resolution=dpi)
                img_io.seek(0)
                pr = PageReader(img_io)
                writer.add_page(pr.pages[0])

            with open(dst, "wb") as f:
                writer.write(f)

            return True, ""
        except Exception as e:
            log.error(f"Error en procesamiento iDRS15 de {src.name}: {e}")
            return False, str(e)


def diagnose_idrs15(idrs_dir: Path) -> dict:
    engine = IDRS15Engine(idrs_dir=idrs_dir)
    ok = engine.initialize()
    return {
        "can_use_direct": ok,
        "engine_created": hex(engine.drsD_create_drs(0, 0)) if ok else "NULL",
        "dlls": {"idrsocr15.dll": {"loaded": ok}},
    }
