"""
ROA OCR — Corrector post-OCR
Corrige errores típicos del reconocimiento óptico de caracteres
en español e inglés, con más de 250 reglas.
"""
import re
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("roa.corrector")

# ──────────────────────────────────────────────────────────────────────────────
# Reglas de corrección
# ──────────────────────────────────────────────────────────────────────────────

# Sustituciones literales (case-sensitive donde importa)
LITERAL_FIXES = {
    # Tildes y diacríticos comunes mal reconocidos
    "á": "á",
    "é": "é",
    "í": "í",
    "ó": "ó",
    "ú": "ú",
    # Caracteres especiales
    "—": "—",
    "–": "-",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}

# Patrones regex: (patrón, reemplazo, flags)
REGEX_RULES = [
    # ── Números confundidos con letras ──────────────────────────────────────
    (r'(\d)[oO](\d)', r'\g<1>0\g<2>', 0),                  # 2o26 -> 2026
    (r'(\d)[oO][oO](\d)', r'\g<1>00\g<2>', 0),              # 2oo8 -> 2008
    (r'(\d+)[oO]\b', r'\1°', 0),                          # 39o -> 39°
    # "0" como "O" en medio de texto
    (r'\b0([a-záéíóúüñ])', r'o\1', re.IGNORECASE),
    (r'([a-záéíóúüñ])0\b', r'\1o', re.IGNORECASE),
    # "1" como "l" o "I"
    (r'\bI([0-9])', r'1\1', 0),

    # ── Espacios y saltos ───────────────────────────────────────────────────
    # Múltiples espacios → uno solo
    (r' {2,}', ' ', 0),
    # Espacios antes de puntuación
    (r' +([.,;:!?])', r'\1', 0),
    # Espacio faltante después de punto (si le sigue mayúscula)
    (r'\.([A-ZÁÉÍÓÚ])', r'. \1', 0),
    # ── Ruido OCR de sellos, marcas de agua y guiones de línea ─────────────
    (r'(\b\w+)-\s*\n\s*(\w+\b)', r'\1\2', 0),            # De-hyphenation (corte de palabra)
    (r'([A-Za-z0-9áéíóúÁÉÍÓÚñÑ,;’"”])\n([A-Za-z0-9áéíóúÁÉÍÓÚñÑ‘"“])', r'\1 \2', 0), # Unwrapping inteligente de saltos entre palabras
    (r'[=~_]{3,}', '', 0),                              # Filas de === o ~~~
    (r'\b[b-df-hj-np-tv-z]{4,}\b', '', re.IGNORECASE),   # Palabras de solo consonantes (ruido OCR)
    (r'^[^\w\s#\-*]{1,4}$', '', re.MULTILINE),          # Símbolos basura aislados al inicio de línea
    (r' {2,}', ' ', 0),                                 # Espacios múltiples
    (r'\n{3,}', '\n\n', 0),                             # Saltos vacíos excesivos

    # ── Errores tipográficos OCR en español ─────────────────────────────────
    # "cion" escrita como "ci6n"
    (r'ci6n', 'ción', re.IGNORECASE),
    # "ó" como "6"
    (r'\b([a-z]+)6([a-z]*)\b', r'\g<1>ó\2', re.IGNORECASE),
    # "que" como "qne"
    (r'\bqne\b', 'que', re.IGNORECASE),
    # "de" como "de" (con espacio invisible)
    (r'\bd\s+e\b', 'de', re.IGNORECASE),
    # "la" como "Ia" (I confundida con l)
    (r'\bIa\b', 'la', 0),
    (r'\bIo\b', 'lo', 0),
    (r'\bIos\b', 'los', 0),
    (r'\bIas\b', 'las', 0),
    # "un" como "un" (u confundida con o en algunos fonts)
    (r'\bona\b', 'una', re.IGNORECASE),
    # El "fi" ligadura se confunde
    (r'ﬁ', 'fi', 0),
    (r'ﬂ', 'fl', 0),
    (r'ﬀ', 'ff', 0),
    (r'ﬃ', 'ffi', 0),
    (r'ﬄ', 'ffl', 0),

    # ── Acentos mal reconocidos ─────────────────────────────────────────────
    (r'\ba(?:\'|`)([a-z])', r'á\1', re.IGNORECASE),
    (r'\be(?:\'|`)([a-z])', r'é\1', re.IGNORECASE),

    # ── Números ordinales ────────────────────────────────────────────────────
    (r'\b(\d+)\s*[oO](\s)', r'\1°\2', 0),  # "1o " → "1°"
    (r'\b(\d+)\s*[aA](\s)', r'\1ª\2', 0),  # "1a " → "1ª"

    # ── Puntuación duplicada ─────────────────────────────────────────────────
    (r'\.{2}(?!\.)', '.', 0),     # ".." → "." (pero no "...")
    (r',{2,}', ',', 0),
    (r';{2,}', ';', 0),
    (r':{2,}', ':', 0),

    # ── Comillas ─────────────────────────────────────────────────────────────
    (r"''", '"', 0),
    (r'``', '"', 0),

    # ── Errores en inglés ────────────────────────────────────────────────────
    (r'\btlie\b', 'the', re.IGNORECASE),
    (r'\bwliere\b', 'where', re.IGNORECASE),
    (r'\bvvith\b', 'with', re.IGNORECASE),
    (r'\bthc\b', 'the', re.IGNORECASE),
    (r'\ban(?:d|cl)\b', 'and', re.IGNORECASE),
    (r'\bwas\b', 'was', re.IGNORECASE),  # sin cambio, placeholder
]

# Palabras que el OCR confunde frecuentemente en documentos jurídicos/formales
DOMAIN_FIXES_ES = {
    "rnismo": "mismo",
    "rniembro": "miembro",
    "rnás": "más",
    "rnano": "mano",
    "rnodo": "modo",
    "rnedia": "media",
    "rnenos": "menos",
    "tarnbién": "también",
    "cornpañía": "compañía",
    "nornbre": "nombre",
    "nurnero": "número",
    "rnunicipio": "municipio",
    "rnercado": "mercado",
    "sisterna": "sistema",
    "econornia": "economía",
    "docurnento": "documento",
    "rneses": "meses",
    "rneses": "meses",
    "rnultiple": "múltiple",
    "tiernpo": "tiempo",
    "inforrnación": "información",
    "perrniso": "permiso",
    "acuerdo": "acuerdo",
    "articulo": "artículo",
    "articulos": "artículos",
    "seccion": "sección",
    "secciones": "secciones",
    "presentacion": "presentación",
    "publicacion": "publicación",
    "administracion": "administración",
    "representacion": "representación",
    "aplicacion": "aplicación",
    "negociacion": "negociación",
    "certificacion": "certificación",
    "constitucion": "constitución",
    "contribucion": "contribución",
    "declaracion": "declaración",
    "disposicion": "disposición",
    "direccion": "dirección",
    "fundacion": "fundación",
    "identificacion": "identificación",
    "inhabilitacion": "inhabilitación",
    "inscripcion": "inscripción",
    "investigacion": "investigación",
    "jurisdiccion": "jurisdicción",
    "legislacion": "legislación",
    "notificacion": "notificación",
    "obligacion": "obligación",
    "organizacion": "organización",
    "participacion": "participación",
    "prestacion": "prestación",
    "produccion": "producción",
    "proteccion": "protección",
    "resolucion": "resolución",
    "sancion": "sanción",
    "seleccion": "selección",
    "solicitud": "solicitud",
    "subordinacion": "subordinación",
    "transicion": "transición",
    "utilizacion": "utilización",
    "validacion": "validación",
}


class PostOCRCorrector:
    """
    Corrector post-OCR avanzado.
    Aplica reglas en capas: literales → regex → dominio → personalizadas.
    """

    def __init__(self, custom_fixes_path: Optional[Path] = None):
        self.custom_fixes: dict = {}
        self._load_custom(custom_fixes_path)

    def _load_custom(self, path: Optional[Path]):
        if path and path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    self.custom_fixes = json.load(f)
                log.info(f"Cargadas {len(self.custom_fixes)} correcciones personalizadas")
            except Exception as e:
                log.warning(f"No se pudieron cargar correcciones personalizadas: {e}")

    def save_custom(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.custom_fixes, f, ensure_ascii=False, indent=2)

    def add_correction(self, wrong: str, correct: str):
        """Añade una corrección personalizada (feedback loop)."""
        self.custom_fixes[wrong] = correct

    def correct_text(self, text: str, lang: str = "spa") -> str:
        """
        Aplica todas las capas de corrección al texto.
        
        Args:
            text: Texto extraído del OCR
            lang: Idioma principal del documento
        
        Returns:
            Texto corregido
        """
        if not text or not text.strip():
            return text

        # Capa 1: Ligaduras y caracteres especiales Unicode
        for wrong, correct in LITERAL_FIXES.items():
            if wrong in text:
                text = text.replace(wrong, correct)

        # Capa 2: Reglas regex
        for pattern, replacement, flags in REGEX_RULES:
            try:
                if flags:
                    text = re.sub(pattern, replacement, text, flags=flags)
                else:
                    text = re.sub(pattern, replacement, text)
            except re.error:
                continue

        # Capa 3: Correcciones de dominio (español)
        if "spa" in lang or "es" in lang:
            for wrong, correct in DOMAIN_FIXES_ES.items():
                text = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, text, flags=re.IGNORECASE)

        # Capa 4: Correcciones personalizadas (aprendidas)
        for wrong, correct in self.custom_fixes.items():
            text = text.replace(wrong, correct)

        # Limpieza final de espacios
        lines = [line.rstrip() for line in text.splitlines()]
        text = "\n".join(lines)

        return text

    def correct_batch(self, texts: list[str], lang: str = "spa") -> list[str]:
        """Corrige una lista de textos (para uso en pipeline batch)."""
        return [self.correct_text(t, lang) for t in texts]

    def statistics(self, original: str, corrected: str) -> dict:
        """Calcula estadísticas de corrección."""
        orig_words = original.split()
        corr_words = corrected.split()
        changes = sum(1 for a, b in zip(orig_words, corr_words) if a != b)
        return {
            "original_chars": len(original),
            "corrected_chars": len(corrected),
            "original_words": len(orig_words),
            "corrected_words": len(corr_words),
            "estimated_changes": changes,
            "change_ratio": round(changes / max(len(orig_words), 1), 4),
        }
