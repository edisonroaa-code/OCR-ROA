# 📋 ROA OCR — Registro de Cambios (Changelog)

Todos los cambios notables y mejoras de este proyecto están documentados en este archivo.

---

## [2.3.0] - 2026-07-23

### 🚀 Nuevas Características

- **MCP Server — Model Context Protocol ([`integrations/mcp_server.py`](integrations/mcp_server.py))**:
  - Servidor MCP completo (JSON-RPC 2.0 sobre stdio) para integración directa con IAs (Claude, Gemini, GPT, Cursor).
  - 4 tools expuestos: `ocr_to_markdown`, `ocr_to_chunks`, `ocr_enhance_pdf`, `ocr_engine_status`.
  - Configuración lista en [`mcp.json`](mcp.json).

- **Integración LangChain ([`integrations/langchain_loader.py`](integrations/langchain_loader.py))**:
  - `ROAOCRLoader` — Document Loader drop-in compatible con LangChain.
  - Modos `page` (un Document por página) y `single` (documento completo).
  - Metadata incluye: source, page, char_count, engine_used.

- **Integración LlamaIndex ([`integrations/llamaindex_reader.py`](integrations/llamaindex_reader.py))**:
  - `ROAOCRReader` — Reader compatible con LlamaIndex.
  - Soporte per-page y per-file con metadata extensible.

- **Soporte Multi-Formato ([`core/format_converter.py`](core/format_converter.py))**:
  - Conversión automática de DOCX, PPTX, XLSX, HTML, TXT, MD, CSV a PDF.
  - Extracción de tablas desde documentos Office.
  - Fallback PIL si reportlab no está disponible.

- **Table Parser v2 ([`core/table_parser.py`](core/table_parser.py))**:
  - Detección de tablas pipe-delimited (`| col | col |`).
  - Soporte CSV-style con detección automática de columnas.
  - Alineación inteligente de columnas con padding.
  - Manejo de celdas vacías y fusionadas.
  - Detección de filas separadoras Markdown existentes.

- **Framework de Benchmarks ([`benchmarks/benchmark.py`](benchmarks/benchmark.py))**:
  - Medición reproducible de CER (Character Error Rate) y WER (Word Error Rate).
  - Comparación contra archivos ground-truth (.txt).
  - Métricas de throughput (páginas/segundo).
  - Reporte JSON exportable.

- **CLI Moderna ([`roa_ocr.py`](roa_ocr.py))**:
  - Subcomandos: `process`, `markdown`, `chunks`, `status`, `serve`, `mcp`, `benchmark`.
  - Barra de progreso visual con porcentaje.
  - Salida coloreada para terminal.
  - Modo batch por defecto (retrocompatible).
  - Help text con ejemplos de uso.

- **Dashboard Profesional Rediseñado ([`dashboard/index.html`](dashboard/index.html))**:
  - Diseño premium inspirado en Vercel/Linear/Raycast.
  - Paleta warm amber, glassmorphism, tipografía Inter + JetBrains Mono.
  - Métricas en vivo, dropzone animado, barra de progreso real.
  - Panel de System Health con estado de 3 motores + cola.
  - Historial de procesamiento con timeline.
  - Responsive completo (desktop, tablet, mobile).
  - Zero emojis en UI — estética profesional, no "típica de IA".

- **Roadmap ([`ROADMAP.md`](ROADMAP.md))**:
  - Documentación de posicionamiento competitivo vs MinerU, Docling, Marker, Surya 2, olmOCR 2, Zerox.
  - Ventajas únicas, oportunidades perdidas, y plan de fases.

---

## [2.2.0] - 2026-07-23

### 🚀 Nuevas Características
- **Parser de Tablas a Markdown ([`core/table_parser.py`](file:///d:/APLICATIVOS/ROA%20OCR/core/table_parser.py))**:
  - Reconstrucción automática de datos tabulares y alineación de columnas a formato Markdown (`| Header 1 | Header 2 |`).
- **Segmentador RAG Nativo ([`core/rag_chunker.py`](file:///d:/APLICATIVOS/ROA%20OCR/core/rag_chunker.py))**:
  - Métodos `process_to_markdown()` y `process_to_chunks()` en `PDFPipeline`.
  - Generación de esquemas e indexación directa para **Qdrant** (`qdrant_payload`) y **Meilisearch** (`meilisearch_doc`) con metadatos por página.
- **Nuevos Endpoints API REST**:
  - `POST /api/v1/process/markdown`: Conversión de PDFs a Markdown estructurado con tablas.
  - `POST /api/v1/process/chunks`: Extracción de fragmentos de texto vectoriales.
- **Despliegue Docker**:
  - Inclusión de `Dockerfile` multi-etapa y `docker-compose.yml` para despliegue en servidores Linux y la Nube.
- **Rediseño del Dashboard Web**:
  - Interfaz limpia e intuitiva basada en intención (Markdown, RAG Chunks, PDF Buscable, Comprimir).
  - Menú de configuración avanzada desplegable (oculto por defecto con valores estándar automáticos).
  - Eliminación de etiquetas técnicas recargadas y paréntesis explicativos.
- **Preservación de Nombre Original**:
  - Los archivos exportados y descargados preservan el nombre de origen añadiendo el sufijo `-roaOcr` (ej: `recurso_de_reposicion-roaOcr.md`).

### 🐛 Correcciones de Errores y Rendimiento
- **Unwrapping Inteligente de Párrafos ([`core/corrector.py`](file:///d:/APLICATIVOS/ROA%20OCR/core/corrector.py))**:
  - Solucionado el problema de saltos de línea divididos entre palabras (`Abg. EDISON\nROA` ➔ `Abg. EDISON ROA`).
  - Corrección de confusión OCR de dígitos/letras en años y números (`2o26` ➔ `2026`, `2oo8` ➔ `2008`, `39o` ➔ `39°`).
- **Renderización PyMuPDF (`fitz`) sin Poppler**:
  - Reemplazada la dependencia binaria de `poppler` en Windows por `fitz` (PyMuPDF) para renderizado ultrarrápido de páginas.
- **Prevención de Bloqueos de Archivo en Windows ([WinError 32] PermissionError)**:
  - Cierre explícito de manejadores de archivo `doc.close()` en `core/pipeline.py` y desvinculación segura de temporales en los endpoints de FastAPI.

---

## [2.1.0] - 2026-07-22

### ⚡ Motor ER296 Nativo & Rebranding Completo
- Migración y renombrado completo de wrappers de motor nativo C/C++ a `ER296`.
- Parche en memoria en `[handle + 0x5058]` previendo `AccessViolationException` en arquitecturas x64.
- Implementación de servidor COM Automation C# (`Er296ComBridge.dll`) registrado con `regsvr32`.
- Creación del repositorio open source con licencia MIT y benchmarks E2E.
