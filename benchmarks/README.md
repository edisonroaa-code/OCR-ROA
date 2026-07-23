# ROA OCR Benchmark Framework

Este framework permite medir la precisión del OCR y las mejoras de corrección de forma reproducible y automatizada, comparando los resultados contra un "ground truth" (texto de referencia).

## ¿Qué mide?
- **CER (Character Error Rate):** Tasa de error por carácter. Un CER bajo es crucial para tareas que dependen de IDs o números.
- **WER (Word Error Rate):** Tasa de error por palabra. Vital para comprensión semántica en RAG y LLMs.
- **Throughput:** Velocidad de procesamiento en páginas por segundo.

## ¿Cómo ejecutar el test de los 60 segundos?

1. **Prepara tu dataset de prueba:**
   - Crea un directorio `samples/` y coloca ahí tus PDFs o imágenes de prueba.
   - Crea un directorio `ground_truth/` y coloca ahí archivos `.txt` con exactamente el mismo nombre (ej. si tienes `factura_1.pdf`, debes tener `factura_1.txt`).

2. **Ejecuta el benchmark (CLI de ROA OCR):**
   ```bash
   roa-ocr benchmark samples/ -g ground_truth/ -o report.json
   ```
   
   O alternativamente:
   ```bash
   python benchmarks/benchmark.py --input samples/ --ground-truth ground_truth/
   ```

El resultado se imprimirá en la consola con promedios y se guardará un reporte detallado en `report.json` que puedes utilizar para automatizar umbrales en tu CI/CD.
