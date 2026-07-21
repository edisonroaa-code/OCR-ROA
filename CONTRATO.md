# 🐺 ROA OCR - Contrato del Sistema

## Visión General

Sistema de OCR masivo basado en el motor **ROAOCR (ER296)**,
con ingeniería inversa para crear un wrapper open-source.

## Arquitectura

```
ROA OCR/
│
├── ER296/                           ← Core OCR Engine (copia de trabajo)
│   ├── idrsocr15.dll                ← Motor principal de reconocimiento (15MB)
│   ├── idrskrn15.dll                ← Kernel de procesamiento
│   ├── idrsdocout15.dll             ← Generación de documento OCR
│   ├── idrsimp15.dll                ← Preprocesamiento de imagen
│   ├── idrsprepro15.dll             ← Preprocesamiento adicional
│   ├── idrsasian15.dll              ← Soporte asiático
│   ├── idrsasian215.dll             ← Asiático extendido
│   ├── idrsarabic15.dll             ← Soporte árabe
│   ├── idrslex15.dll                ← Análisis léxico
│   └── OCRResources/                ← Modelos de lenguaje (84 archivos)
│       ├── spn.ilex                 ← ESPAÑOL
│       ├── eng.ilex                 ← INGLÉS
│       ├── latin.ocr                ← Latino base
│       ├── handpr.ocr               ← Manuscrito
│       ├── cyrillic.ocr             ← Cirílico
│       ├── greek.ocr                ← Griego
│       ├── hebrew.ocr               ← Hebreo
│       └── +70 más...
│
├── Soporte/                         ← DLLs necesarios para el engine
│   ├── ACE.dll                      ← ROAOCR Core Engine
│   ├── AGM.dll                      ← ROAOCR Graphics Model
│   ├── AIDE.dll                     ← ROAOCR Image Data Engine
│   ├── AdobePDFL.dll                ← ROAOCR PDF Library
│   ├── CoolType.dll                 ← ROAOCR Font Engine
│   ├── AdobeLinguistic.dll          ← ROAOCR Linguistic
│   └── OCRLibraryInf.dll            ← Interfaz OCR Library
│
├── roa_ocr.py                       ← Wrapper Python (en desarrollo)
├── analizar_exports.py              ← Analizador de funciones DLL
├── analisis_profundo.py             ← Análisis de dependencias
│
└── docs/                            ← Documentación técnica
    └── reverse_engineering.md       ← Notas de ingeniería inversa
```

## Estado Actual

| Componente | Estado |
|-----------|--------|
| ✅ Extracción del Core OCR | COMPLETADO - 134MB copiados |
| ✅ Modelos de lenguaje | COMPLETADO - 84 idiomas/recursos |
| ✅ DLLs de soporte | COMPLETADO - 7 DLLs clave |
| 🔄 Wrapper Python/COM | EN DESARROLLO |
| ❌ Llamada directa a DLLs | BLOQUEADO (órdenes ordinales) |
| ❌ Ghidra/IDA reverso | PENDIENTE |

## Próximos Pasos

1. **FASE 2:** Probar el wrapper COM (roa_ocr.py)
2. **FASE 3:** Procesar 30,000 archivos de prueba
3. **FASE 4:** Ingeniería inversa con Ghidra (identificar funciones por ordinal)
4. **FASE 5:** Crear chimera open-source

## Métricas Objetivo

| Métrica | ROAOCR | Tesseract | ROAOCR (meta) |
|---------|----------------|-----------|----------------|
| Precisión latín | 99.2% | 97.5% | 99.2% |
| Precisión español | 98.8% | 96.0% | 98.8% |
| Manuscrito | 85% | 70% | 85% |
| Velocidad (pág/s) | 3 | 8 | 5 |

## Dependencias

- ROAOCR Engine (para el motor COM)
- Python 3.8+
- pywin32 (pip install pywin32)
- Windows (los DLLs son nativos de Windows)
