# Wrapper nativo de iDRS15

Este directorio contiene un ejemplo mínimo de wrapper en C/C++ para cargar [idrsocr15.dll](../idrsocr15.dll) y resolver exportaciones conocidas del motor OCR.

## Archivos
- [main.cpp](main.cpp): ejemplo de carga de la DLL y resolución de exportaciones.
- [CMakeLists.txt](CMakeLists.txt): configuración mínima para compilar el ejemplo.

## Compilar
```powershell
cd native-wrapper
cmake -S . -B build
cmake --build build
```

## Ejecutar
```powershell
cd native-wrapper\build
idrs_wrapper.exe
```

## Estado actual

El wrapper ya:
1. detecta automáticamente la DLL nativa [idrsocr15.dll](../idrsocr15.dll) aunque el ejecutable se lance desde la carpeta de compilación,
2. localiza los recursos del motor en [OCRResources](../OCRResources),
3. resuelve exportaciones principales del motor,
4. y queda preparado como base para completar el flujo de inicialización OCR real y la extracción de texto.

## Relación con el resto del proyecto

El wrapper nativo es la capa de integración más cercana al motor. Desde ahí se puede conectar el flujo de la demo .NET y la puerta COM, manteniendo el mismo objetivo: convertir documentos en texto y luego en Markdown.
