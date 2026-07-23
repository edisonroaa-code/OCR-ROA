# ROA OCR — Enterprise Docker Deployment (Multi-Stage)
FROM python:3.11-slim as base

# Instalar dependencias del sistema operativo (Ghostscript, Tesseract, Tesseract Spanish)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar el código del proyecto
COPY . .

# Instalar el paquete y dependencias completas
RUN pip install --no-cache-dir ".[full]"

# Exponer el puerto de la API FastAPI
EXPOSE 8000

# Comando de inicio del servidor FastAPI
CMD ["python", "-m", "roa_ocr.api.main", "--host", "0.0.0.0", "--port", "8000"]
