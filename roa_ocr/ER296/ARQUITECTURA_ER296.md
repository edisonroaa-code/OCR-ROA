# Arquitectura funcional de ER296

## 2. Arquitectura y funcionamiento

ER296 es un motor OCR/ICR nativo de Windows, distribuido como bibliotecas DLL y recursos de idioma. No expone handlers HTTP ni endpoints REST en este workspace.

## Componentes principales

- [idrsocr15.dll](idrsocr15.dll): núcleo del motor OCR. Gestiona creación y destrucción del motor, carga de recursos, configuración del entorno y ejecución del reconocimiento.
- [idrskrn15.dll](idrskrn15.dll): runtime del motor. Proporciona la infraestructura interna para sesiones, zonas, resultados y operaciones del núcleo.
- [idrsprepro15.dll](idrsprepro15.dll): preprocesado de imagen. Ajusta contraste, umbrales, filtros y otras transformaciones sobre la imagen antes del análisis.
- [idrsimp15.dll](idrsimp15.dll): motor de reconocimiento interno.
- [idrsdocout15.dll](idrsdocout15.dll): módulo de salida. Permite formatear y exportar resultados a formatos de documento.
- [idrsasian215.dll](idrsasian215.dll), [idrsasian15.dll](idrsasian15.dll), [idrsarabic15.dll](idrsarabic15.dll), [idrslex15.dll](idrslex15.dll): módulos especializados para lenguaje y scripts específicos.
- [OCRResources](OCRResources): recursos lingüísticos y de modelos necesarios para reconocer texto.

## Flujo de procesamiento

1. Se crea una instancia del motor.
2. Se cargan los recursos y los entornos lingüísticos.
3. Se prepara la imagen.
4. Se ejecuta el reconocimiento.
5. Se extraen zonas, palabras, coordenadas y resultados.
6. Se exporta la salida final en un formato adecuado.

## Requisitos de entorno

- Windows x64.
- Acceso a los DLLs y recursos del directorio del proyecto.
- Dependencia de [OCRResources](OCRResources) para reconocer texto correctamente.
- Integración por interop nativo si se usa desde .NET o C++.

## Observación práctica

Este paquete se comporta como un motor local de OCR, no como un servicio web. La integración debe hacerse mediante llamadas a funciones exportadas desde las DLLs, normalmente a través de P/Invoke o un wrapper nativo.
