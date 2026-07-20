# 🐺 ROA OCR API v2.0

**Plataforma especializada en mejora y corrección masiva de PDFs con salida API REST.**

## ¿Qué es esto?

ROA OCR API transforma el motor OCR de alta precisión **iDRS15** (que opera detrás de Adobe Acrobat) en un servicio API accesible para cualquier software o IA. Aplica OCR, corrige errores, optimiza y retorna PDFs mejorados en escala.

## Arquitectura

```
ROA OCR/
├── api/
│   ├── main.py              ← FastAPI app principal
│   ├── auth.py              ← Autenticación por API Key
│   ├── models.py            ← Schemas Pydantic
│   └── routes/
│       ├── process.py       ← /api/v1/process (individual)
│       ├── batch.py         ← /api/v1/batch (masivo)
│       └── jobs.py          ← /api/v1/jobs (gestión)
├── core/
│   ├── engine.py            ← Motor OCR (iDRS15 → ocrmypdf → tesseract)
│   ├── pipeline.py          ← Pipeline completo
│   ├── corrector.py         ← Corrector post-OCR (250+ reglas)
│   └── optimizer.py         ← Optimizador PDF (Ghostscript)
├── worker/
│   └── tasks.py             ← Cola async (Celery+Redis o Threading)
├── dashboard/
│   └── index.html           ← Panel web de monitoreo
├── iDRS15/                  ← Motor OCR (DLLs originales)
├── Soporte/                 ← DLLs de soporte
├── config.py                ← Configuración centralizada
├── start.bat                ← Script de inicio Windows
└── .env.example             ← Variables de entorno de ejemplo
```

## Inicio rápido

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

O usar el script todo-en-uno:
```
start.bat   (doble clic)
```

### 2. (Opcional) Configurar variables de entorno
```bash
copy .env.example .env
# Editar .env con tu editor favorito
```

### 3. Iniciar el servidor
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Abrir el dashboard
```
http://localhost:8000/dashboard
```

### 5. Ver la documentación API
```
http://localhost:8000/docs      ← Swagger UI interactivo
http://localhost:8000/redoc     ← ReDoc
```

---

## Uso de la API

### Autenticación
Todos los endpoints (excepto `/health`) requieren el header:
```
X-API-Key: roa-dev-key-2024
```
Configura tus propias keys en `.env` con `ROA_API_KEYS`.

### Procesar un PDF (sincrónico)
```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "X-API-Key: roa-dev-key-2024" \
  -F "file=@mi_documento.pdf" \
  -F "lang=spa+eng" \
  -F "engine=auto" \
  -F "optimize=true" \
  --output mi_documento_mejorado.pdf
```

### Procesar en lote (upload multifile)
```bash
curl -X POST http://localhost:8000/api/v1/batch \
  -H "X-API-Key: roa-dev-key-2024" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "lang=spa+eng"
```

### Procesar por rutas locales (masivo)
```bash
curl -X POST http://localhost:8000/api/v1/batch/paths \
  -H "X-API-Key: roa-dev-key-2024" \
  -H "Content-Type: application/json" \
  -d '{
    "paths": [
      "C:\\PDFs\\documento1.pdf",
      "C:\\PDFs\\documento2.pdf"
    ],
    "options": { "lang": "spa+eng", "optimize": true }
  }'
```

### Consultar estado de un job
```bash
curl http://localhost:8000/api/v1/jobs/{job_id} \
  -H "X-API-Key: roa-dev-key-2024"
```

### Descargar resultado
```bash
curl http://localhost:8000/api/v1/jobs/{job_id}/download \
  -H "X-API-Key: roa-dev-key-2024" \
  --output resultado.pdf
```

### Health check (sin auth)
```bash
curl http://localhost:8000/api/v1/health
```

---

## Parámetros de procesamiento

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `lang` | string | `spa+eng` | Idioma(s) OCR. Ej: `spa+eng`, `fra`, `por+eng` |
| `engine` | enum | `auto` | Motor: `auto`, `acrobat`, `ocrmypdf`, `tesseract` |
| `dpi` | int | `300` | Resolución (72-600) |
| `skip_if_has_text` | bool | `true` | Omite OCR en páginas ya con texto |
| `run_correction` | bool | `true` | Corrección post-OCR |
| `optimize` | bool | `true` | Compresión/optimización |
| `compress_quality` | enum | `printer` | `screen`, `ebook`, `printer`, `prepress` |

---

## Motores OCR (en cascada)

| Motor | Precisión | Requisito | Descripción |
|---|---|---|---|
| **iDRS15 (Acrobat)** | 99%+ | Adobe Acrobat Pro | Motor comercial de máxima calidad |
| **ocrmypdf** | 97%+ | `pip install ocrmypdf` + Tesseract | Open-source, excelente calidad |
| **Tesseract directo** | 95%+ | Tesseract en PATH | Fallback siempre disponible |

El sistema detecta automáticamente el mejor motor disponible.

---

## Idiomas soportados

84 idiomas incluyendo:
- 🇪🇸 Español (`spa`) — modelo `spn.ilex`
- 🇺🇸 Inglés (`eng`) — modelo `eng.ilex`
- 🇫🇷 Francés (`fra`) — modelo `frn.ilex`
- 🇩🇪 Alemán (`grm`) — modelo `grm.ilex`
- 🇵🇹 Portugués (`por`) — modelo `prt.ilex`
- 🇷🇺 Ruso (`rus`) — modelo `rus.ilex`
- 🇨🇳 Chino simplificado — modelos `sch*.dic`
- 🇯🇵 Japonés — modelos `jap*.dic`
- 🇰🇷 Coreano — modelos `kor*.dic`
- Y 75 más...

---

## Integración con otras IAs

La API está diseñada para ser usada como **herramienta por otras IAs**:

```python
# Ejemplo: usar desde Python
import requests

def mejora_pdf(ruta_pdf: str, api_key: str = "roa-dev-key-2024") -> bytes:
    with open(ruta_pdf, "rb") as f:
        resp = requests.post(
            "http://localhost:8000/api/v1/process",
            headers={"X-API-Key": api_key},
            files={"file": f},
            data={"lang": "spa+eng", "optimize": "true"},
        )
    resp.raise_for_status()
    return resp.content  # PDF mejorado como bytes
```

```javascript
// Ejemplo: usar desde Node.js / JavaScript
const form = new FormData();
form.append("file", fs.createReadStream("documento.pdf"));
form.append("lang", "spa+eng");

const resp = await fetch("http://localhost:8000/api/v1/process", {
  method: "POST",
  headers: { "X-API-Key": "roa-dev-key-2024" },
  body: form,
});
const pdfBytes = await resp.arrayBuffer();
```

---

## Cola de producción (opcional)

Para procesar miles de PDFs, instala Redis y úsalo con Celery:

```bash
# 1. Instalar Redis (Windows)
winget install Redis.Redis

# 2. Iniciar Redis
redis-server

# 3. Iniciar worker Celery
celery -A worker.tasks worker --concurrency=4 --loglevel=info

# 4. El servidor FastAPI detecta Redis automáticamente
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Sin Redis, el sistema usa un ThreadPoolExecutor local (modo desarrollo).

---

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `ROA_API_KEYS` | `roa-dev-key-2024` | API Keys válidas (separadas por coma) |
| `ROA_ENGINE` | `auto` | Motor OCR preferido |
| `ROA_LANG` | `spa+eng` | Idioma por defecto |
| `ROA_PORT` | `8000` | Puerto del servidor |
| `ROA_MAX_MB` | `100` | Tamaño máximo de upload |
| `ROA_REDIS_URL` | `redis://localhost:6379/0` | URL Redis para Celery |
| `ROA_DPI` | `300` | DPI de procesamiento |
| `ROA_COMPRESS` | `true` | Comprimir output |

Ver `.env.example` para la lista completa.
