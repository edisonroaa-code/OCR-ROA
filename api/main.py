"""
ROA OCR — FastAPI Application Principal
"""
import time
import logging
import logging.config
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes.process import router as process_router
from api.routes.batch import router as batch_router
from api.routes.jobs import router as jobs_router
from api.auth import require_api_key
from api.models import HealthResponse, StatsResponse
from config import settings
from worker.tasks import get_global_stats

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

settings.log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(settings.log_dir / "api.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("roa.api")

# ──────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ──────────────────────────────────────────────────────────────────────────────

_START_TIME = time.time()
_ENGINE_STATUS: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa componentes al arrancar y los limpia al cerrar."""
    global _ENGINE_STATUS
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    log.info("=" * 60)
    log.info("  🐺 ROA OCR API v2.0 — Iniciando...")
    log.info("=" * 60)

    # Detectar motores en un thread separado (no bloquea el event loop)
    def _detect():
        try:
            from core.engine import detect_available_engines
            return detect_available_engines()
        except Exception as e:
            log.warning(f"No se pudieron detectar motores: {e}")
            return {}

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            _ENGINE_STATUS = await asyncio.wait_for(
                loop.run_in_executor(pool, _detect), timeout=5.0
            )
        log.info(f"Motores detectados: {_ENGINE_STATUS}")
    except Exception as e:
        log.warning(f"No se pudieron detectar motores: {e}")
        _ENGINE_STATUS = {}

    log.info(f"📂 Input dir:  {settings.input_dir}")
    log.info(f"📂 Output dir: {settings.output_dir}")
    log.info(f"🌐 API Keys configuradas: {len(settings.api_keys_list)}")
    log.info(f"✅ ROA OCR API lista en http://{settings.api_host}:{settings.api_port}")

    yield  # ← Servidor corriendo aquí

    log.info("👋 ROA OCR API cerrando...")


# ──────────────────────────────────────────────────────────────────────────────
# App FastAPI
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ROA OCR API",
    description=(
        "## 🐺 ROA OCR — PDF Enhancement & Correction API\n\n"
        "Plataforma especializada en mejora y corrección masiva de PDFs.\n\n"
        "### Características\n"
        "- **OCR de alta precisión**: Motor iDRS15 via Acrobat COM + Tesseract fallback\n"
        "- **Corrección post-OCR**: 250+ reglas para español e inglés\n"
        "- **Optimización**: Compresión Ghostscript, metadatos, linearización\n"
        "- **Procesamiento masivo**: Queue async con Celery+Redis o threading\n"
        "- **84 idiomas**: Español, inglés, árabe, chino, japonés, y más\n\n"
        "### Autenticación\n"
        "Incluye el header `X-API-Key: <tu-key>` en todas las requests.\n"
        "Default para desarrollo: `roa-dev-key-2024`"
    ),
    version="2.0.0",
    contact={"name": "ROA OCR", "email": "soporte@roa.ai"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middlewares
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Engine-Used", "X-Pages", "X-Processing-Time"],
)

# Routers
app.include_router(process_router)
app.include_router(batch_router)
app.include_router(jobs_router)

# Dashboard estático (carpeta dashboard/ está en la raíz del proyecto, no en api/)
dashboard_dir = Path(__file__).parent.parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints de sistema
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Redirige al dashboard."""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/dashboard" />
        <title>ROA OCR API</title>
    </head>
    <body><p>Redirigiendo al <a href="/dashboard">Dashboard</a>...</p></body>
    </html>
    """)


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    """Sirve el panel de monitoreo."""
    html_path = Path(__file__).parent.parent / "dashboard" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard no encontrado</h1>", status_code=404)


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check",
)
async def health():
    """Verifica el estado del servicio. No requiere autenticación."""
    from worker.tasks import _try_init_celery
    queue_ok = _try_init_celery() is not None

    return HealthResponse(
        status="ok",
        version="2.0.0",
        engines=_ENGINE_STATUS,
        queue_available=queue_ok,
        uptime_s=round(time.time() - _START_TIME, 1),
    )


@app.get(
    "/api/v1/stats",
    response_model=StatsResponse,
    tags=["system"],
    summary="Estadísticas globales",
)
async def stats(_key: str = Depends(require_api_key)):
    """Estadísticas de procesamiento de la sesión actual."""
    return StatsResponse(**get_global_stats())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Error no manejado en {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor", "error": str(exc)},
    )
