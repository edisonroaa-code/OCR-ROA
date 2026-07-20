"""
ROA OCR — Configuración centralizada
Lee valores de variables de entorno con fallbacks seguros.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR = Path(__file__).parent.resolve()


class Settings(BaseSettings):
    # ── Rutas ─────────────────────────────────────────────────────────────
    base_dir: Path = BASE_DIR
    idrs_dir: Path = BASE_DIR / "iDRS15"
    soporte_dir: Path = BASE_DIR / "Soporte"
    ocr_resources_dir: Path = BASE_DIR / "iDRS15" / "OCRResources"

    input_dir: Path = BASE_DIR / "PDFS_PENDIENTES"
    output_dir: Path = BASE_DIR / "PDFS_OCR"
    temp_dir: Path = BASE_DIR / "tmp"
    log_dir: Path = BASE_DIR / "logs"

    # ── OCR ───────────────────────────────────────────────────────────────
    default_lang: str = Field(default="spa+eng", env="ROA_LANG")
    # Motor preferido: "idrs15" | "ocrmypdf" | "tesseract" | "acrobat_pro" | "auto"
    ocr_engine: str = Field(default="idrs15", env="ROA_ENGINE")
    ocr_dpi: int = Field(default=300, env="ROA_DPI")
    ocr_threads: int = Field(default=2, env="ROA_THREADS")
    max_retries: int = Field(default=2, env="ROA_RETRIES")

    # ── API ───────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", env="ROA_HOST")
    api_port: int = Field(default=8000, env="ROA_PORT")
    api_keys: str = Field(default="roa-dev-key-2024", env="ROA_API_KEYS")
    max_upload_mb: int = Field(default=100, env="ROA_MAX_MB")

    # ── Celery / Redis ────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", env="ROA_REDIS_URL")

    # ── Optimización ──────────────────────────────────────────────────────
    compress_quality: str = Field(default="printer", env="ROA_COMPRESS_QUALITY")
    enable_compression: bool = Field(default=True, env="ROA_COMPRESS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    def ensure_dirs(self):
        for d in [self.input_dir, self.output_dir, self.temp_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)


# Instancia global
settings = Settings()
settings.ensure_dirs()
